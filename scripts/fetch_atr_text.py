"""Fetch a shard of annual-town-report PDFs and return TEXT, not bytes.

WHY THIS EXISTS BESIDE fetch_url_batch.py. That script fetches from clean runner
IPs and hands back the raw files, which is right when you want the document. Here
we only want to know whether the document contains an election return and where,
so shipping 5-30MB PDFs through the artifact store to extract text locally is
pure waste -- ci_out/ at 530MB is the receipt for that. This extracts on the
runner and uploads a JSONL of text instead, the way discover/verify.py already
does for its 6-page verdicts.

THREE THINGS IT DOES THAT fetch_url_batch.py DOES NOT:

  1. Paces and retries. fetch_url_batch has no backoff and a flat 0.5s sleep
     between a row's two URL attempts, nothing between rows. HANDOFF.md is
     unambiguous that the throttle is per-IP CUMULATIVE volume, and that running
     hot from one IP produced 346 refused connections in a single run. At
     several thousand PDFs that matters, so this uses core/fetchio.fetch (4
     tries, honours Retry-After, exponential backoff) behind a per-host
     RateLimiter.

  2. Extracts COLUMN-AWARE. A plain page.get_text() on an election table emits
     the candidate names as one run and the vote column as another, so you get a
     list of names with no numbers -- useless for the thing we are looking for.
     Bucketing get_text("words") on the y coordinate puts a candidate back
     beside their votes. Same approach as the main project's
     src/recrop_ingest5_atrs.page_text.

  3. Reads the WHOLE document. verify.py caps at 6 pages because it only needs
     to know what a document is. The election return in an annual town report is
     typically 40-200 pages in, so a 6-page cap would find nothing.

Every outcome is written, including failures. An absence must be documented,
never silently asserted.

Usage: python scripts/fetch_atr_text.py --url-csv config/atr_pre2021_urls.csv \
           --shard 1/40 --out out
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

MAX_CHARS = 1_200_000     # a very long town report; guards the artifact size
MIN_SUBSTANCE = 2000      # below this the PDF has no usable text layer


def _is_pdf(data):
    return bool(data) and data[:4] == b"%PDF"


def _load_fetch():
    """Prefer the package's polite fetcher; fall back to stdlib if unavailable."""
    try:
        from muni_harvest.core.fetchio import fetch  # type: ignore
        return fetch
    except Exception:
        import urllib.request

        UA = ("muni-harvest civic-document research crawler "
              "(personal academic use; contact jamesnicholsworley@gmail.com)")

        def fetch(url, timeout=60, **kw):
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=timeout).read()
        return fetch


def _load_limiter(per_minute):
    try:
        from muni_harvest.core.rate_limit import RateLimiter  # type: ignore
        return RateLimiter(per_minute)
    except Exception:
        class _L:
            def __init__(self, pm):
                self.gap = 60.0 / max(pm, 1)
                self.last = 0.0

            def wait(self):
                dt = time.time() - self.last
                if dt < self.gap:
                    time.sleep(self.gap - dt)
                self.last = time.time()
        return _L(per_minute)


def page_lines(page):
    """Column-aware text for one page: bucket words on y, sort by x.

    A ~6pt band is the tolerance that keeps a candidate's name on the same line
    as their vote column without merging adjacent table rows.
    """
    buck = {}
    for w in page.get_text("words"):
        buck.setdefault(round(w[1] / 6.0), []).append((w[0], w[4]))
    return "\n".join(" ".join(x for _, x in sorted(v))
                     for _, v in sorted(buck.items()))


OCR_MAX_PAGES = 60        # beyond this, OCR belongs in the local staged pass
OCR_DPI = 250


def ocr_text(doc):
    """Rasterise and read with tesseract, in CI, where it is nearly free.

    40% of the town-website pool is scanned with no text layer at all -- and a
    great many of those are the two-page standalone "2014 Annual Town Election
    Results" PDFs that are exactly what we are looking for. Shipping them home
    to OCR one at a time would take days; forty runners do it in parallel in
    minutes. Long volumes are left alone, because a 200-page scan is a
    different job with a different cost.

    psm 6 treats the page as one uniform block, which keeps a table's rows
    intact; the default psm 3 re-orders columns and separates a candidate from
    their votes.
    """
    import fitz  # noqa: F401
    import pytesseract
    from PIL import Image
    out = []
    for i in range(min(doc.page_count, OCR_MAX_PAGES)):
        pix = doc[i].get_pixmap(dpi=OCR_DPI)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        out.append(pytesseract.image_to_string(img, config="--psm 6"))
    return "\x0c".join(out)


def pdf_text(data, allow_ocr=False):
    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        out, n = [], 0
        for i in range(doc.page_count):
            t = page_lines(doc[i])
            out.append(t)
            n += len(t)
            if n > MAX_CHARS:
                out.append("\n[TRUNCATED at %d chars, %d/%d pages]"
                           % (n, i + 1, doc.page_count))
                break
        txt = "\x0c".join(out)
        if allow_ocr and len(txt.strip()) < MIN_SUBSTANCE \
                and doc.page_count <= OCR_MAX_PAGES:
            try:
                o = ocr_text(doc)
                if len(o.strip()) > len(txt.strip()):
                    return o, doc.page_count, "ocr"
            except Exception:
                pass
        return txt, doc.page_count, "text"
    finally:
        doc.close()


CDX = ("https://web.archive.org/cdx/search/cdx?url=%s&output=json"
       "&filter=statuscode:200&limit=6&collapse=timestamp:6")


def wayback_url(url, year, fetch, timeout=60):
    """Nearest archived snapshot of a dead URL, preferring the target year.

    WHY THIS IS NOT A CONSOLATION PRIZE. 4,198 of the first pass's 6,900 URLs
    returned 404 -- but 1,532 of them were DISCOVERED in the Wayback Machine in
    the first place, by this repo's own wayback sweep. A town reorganising its
    website breaks the live URL and changes nothing about whether the document
    exists. Asking the archive that supplied the URL for the bytes it already
    holds is the obvious second question, and it is free.

    `id_` on the timestamp asks for the ORIGINAL bytes rather than the rewritten
    page -- without it the archive injects its toolbar and the PDF check fails.
    """
    try:
        raw = fetch(CDX % urllib.parse.quote(url, safe=""), timeout=timeout)
        rows = json.loads(raw.decode("utf-8", "replace") or "[]")
    except Exception:
        return ""
    if len(rows) < 2:
        return ""
    stamps = [r[1] for r in rows[1:] if len(r) > 1]
    if not stamps:
        return ""
    try:
        want = int(str(year)[:4])
        stamps.sort(key=lambda s: abs(int(s[:4]) - want))
    except (TypeError, ValueError):
        pass
    return "https://web.archive.org/web/%sid_/%s" % (stamps[0], url)


def shard_by_host(rows, i, n):
    """Split by HOST, so exactly one runner ever talks to a given town's server.

    The obvious split -- rows[i-1::n] -- is wrong here and quietly so. It spreads
    one host's URLs across every shard, so a small town's web server would face
    40 runner IPs at once while each runner's RateLimiter reported itself
    perfectly well behaved: the limiter is per process, and nothing is per host.
    Sharding on the host instead makes the per-runner pace an actual per-host
    pace. Hosts are dealt largest-first round-robin so no shard draws all the
    heavy ones, the same reasoning as archive/wayback.py::shard_hosts.
    """
    by_host = {}
    for r in rows:
        h = urllib.parse.urlsplit((r.get("url") or "").strip()).netloc.lower()
        by_host.setdefault(h.replace("www.", ""), []).append(r)
    order = sorted(by_host, key=lambda h: (-len(by_host[h]), h))
    mine = []
    for k, h in enumerate(order):
        if k % n == i - 1:
            mine.extend(by_host[h])
    return mine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url-csv", default="config/atr_pre2021_urls.csv")
    ap.add_argument("--out", default="out")
    ap.add_argument("--shard", default="1/1", help="i/N, 1-indexed")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--per-minute", type=int, default=30)
    ap.add_argument("--ocr", action="store_true",
                    help="OCR a short PDF that has no text layer (needs tesseract)")
    ap.add_argument("--wayback-first", action="store_true",
                    help="go to the archive before the live host (retry lists)")
    ap.add_argument("--wayback", action="store_true",
                    help="on a failed/no-PDF fetch, retry via the Wayback Machine")
    args = ap.parse_args()

    i, n = (int(x) for x in args.shard.split("/"))
    with open(args.url_csv, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    mine = shard_by_host(rows, i, n)
    os.makedirs(args.out, exist_ok=True)
    print("[shard %d/%d] %d of %d rows" % (i, n, len(mine), len(rows)),
          flush=True)

    fetch = _load_fetch()
    limiter = _load_limiter(args.per_minute)
    tp = os.path.join(args.out, "atr_text_%d.jsonl" % i)
    mp = os.path.join(args.out, "manifest_%d.csv" % i)
    t0 = time.time()

    with open(tp, "w", encoding="utf-8") as tf, \
            open(mp, "w", newline="", encoding="utf-8") as mf:
        w = csv.DictWriter(mf, ["municipality", "year", "url", "kind", "pool",
                                "status", "via", "extract", "http_bytes",
                                "pages", "chars", "detail"])
        w.writeheader()
        for k, r in enumerate(mine, 1):
            url = (r.get("url") or "").strip()
            rec = {"municipality": r.get("municipality", ""), "year": r.get("year", ""),
                   "url": url, "kind": r.get("kind", ""), "pool": r.get("pool", ""),
                   "status": "", "via": "", "extract": "", "http_bytes": 0,
                   "pages": 0, "chars": 0, "detail": ""}
            if not url:
                rec["status"] = "NO_URL"
                w.writerow(rec)
                continue
            limiter.wait()
            attempt_url, via, data = url, "live", None
            # RE-ASKING A URL THAT IS ALREADY KNOWN DEAD IS THE EXPENSIVE
            # MISTAKE. On a retry list every row failed once already, and the
            # polite fetcher spends four tries with exponential backoff and a
            # 60s timeout apiece before giving up -- minutes per URL, on a
            # question that was answered in the previous pass. --wayback-first
            # goes straight to the archive and only falls back to the live host
            # if the archive has nothing.
            if not args.wayback_first:
                try:
                    data = fetch(url, timeout=args.timeout)
                except Exception as e:
                    data, rec["detail"] = None, repr(e)[:180]
            if args.wayback and not _is_pdf(data):
                wb = wayback_url(url, r.get("year", ""), fetch, args.timeout)
                if wb:
                    limiter.wait()
                    try:
                        d2 = fetch(wb, timeout=args.timeout)
                        if _is_pdf(d2):
                            data, attempt_url, via = d2, wb, "wayback"
                    except Exception as e:
                        rec["detail"] = ("wayback: " + repr(e))[:180]
            if args.wayback_first and not _is_pdf(data):
                # The archive had nothing; the live host is now worth the one
                # attempt it was skipped for.
                try:
                    data = fetch(url, timeout=args.timeout)
                    via = "live"
                except Exception as e:
                    data, rec["detail"] = None, repr(e)[:180]
            rec["via"] = via
            rec["url"] = attempt_url if via == "wayback" else url
            try:
                rec["http_bytes"] = len(data or b"")
                if not data:
                    rec["status"] = "ERROR" if rec["detail"] else "EMPTY"
                elif not _is_pdf(data):
                    # A WAF interstitial or a 200-with-HTML redirect page. Not a
                    # PDF, so not silently treated as one.
                    rec["status"] = "NOT_PDF"
                    rec["detail"] = data[:60].decode("utf-8", "replace").replace("\n", " ")
                else:
                    txt, pages, how = pdf_text(data, allow_ocr=args.ocr)
                    rec["extract"] = how
                    rec["pages"] = pages
                    rec["chars"] = len(txt)
                    if len(txt.strip()) < MIN_SUBSTANCE:
                        rec["status"] = "NEEDS_OCR"
                        rec["detail"] = "text layer under %d chars" % MIN_SUBSTANCE
                    else:
                        rec["status"] = "OK"
                    tf.write(json.dumps({
                        "municipality": rec["municipality"], "year": rec["year"],
                        "url": rec["url"], "via": via, "pool": rec["pool"],
                        "extract": rec.get("extract", ""), "pages": pages,
                        "status": rec["status"], "text": txt}) + "\n")
            except Exception as e:
                rec["status"] = "ERROR"
                rec["detail"] = repr(e)[:180]
            w.writerow(rec)
            if k % 20 == 0:
                el = time.time() - t0
                print("  %4d/%4d  %.0fs elapsed, eta %.0fm"
                      % (k, len(mine), el, (el / k) * (len(mine) - k) / 60), flush=True)
                mf.flush()
                tf.flush()
    print("[shard %d/%d] done in %.0fm" % (i, n, (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
