"""Stage 2 (topic+vote screen) for the MBTA Communities Act 3A vote finder.

Reads scratch/mbtac_candidates.csv, fetches each candidate doc (fitz for PDF page-by-page,
HTML-strip otherwise; WAF cookie-lift fallback), and scores it against three INDEPENDENT
regex sets. A doc is CONFIRMED only if TOPIC and VOTE and BODY all fire; PROBABLE if TOPIC
plus one of the others. Records the PDF pages where the 3A TOPIC appears so Stage 3 extraction
can jump straight to them.

Fetch helpers are copied (not imported) from dive_fetch2.py, because importing that module
would run its election-recovery pass as a side effect.

Output: scratch/mbtac_screen.csv
  town, town_norm, community_type, priority, board, doctype, year, verdict,
  topic_hits, vote_hits, body_hits, topic_pages, npages, url, kind, err

Usage: mbtac_screen.py [max_per_town] [workers]   (defaults: 8, 8)
ASCII-only, explicit UTF-8 I/O.
"""
import csv
import re
import ssl
import sys
import urllib.request
import urllib.parse
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
import fitz

CAND = HERE / "mbtac_candidates.csv"
OUT = HERE / "mbtac_screen.csv"

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

# --- signal sets --------------------------------------------------------------
# TOPIC: MBTA Communities / Section 3A / 3A district / multifamily overlay.
# Polysemy guard: a bare "3A" only counts when qualified (district/zoning/overlay/40A/section).
TOPIC = re.compile(
    r"mbta[ _-]?communit\w*"
    r"|section[ _-]?3a\b"
    r"|(?<![\w])(?:g\.?l\.?\s*c\.?\s*)?40a[, ]*(?:\xa7|section)?\s*3a\b"
    r"|\b3a[ _-]?(?:district|zoning|overlay|compliance|requirement)"
    r"|multi[ _-]?family[ _-]?(?:overlay|zoning[ _-]?district|district|zoning)"
    r"|compliance guidelines for multi", re.I)
VOTE = re.compile(
    r"\bvoted?\b|\bmotion\b|moved[ ,]|seconded|in favor|opposed|\byea?s?\b|\bnays?\b"
    r"|two[ -]?thirds|2/3|\barticle\s+\d+|\bpassed\b|\badopted\b|\bcarried\b"
    r"|\bfailed\b|\bdefeated\b|\btabled\b|\bcontinued\b|declared", re.I)
BODY = re.compile(
    r"planning board|select ?board|selectmen|city council|town council|common council"
    r"|town meeting|representative town meeting", re.I)


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def enc(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path),
                                    urllib.parse.quote(p.query, safe="=&?"), ""))


_sessions = {}
_sess_lock = Lock()


def waf_get(url):
    from muni_harvest.fetchers.waf_session import mint_session
    host = urllib.parse.urlsplit(url).netloc
    with _sess_lock:
        if host not in _sessions:
            _sessions[host] = mint_session(f"https://{host}/") or None
        s = _sessions[host]
    if not s:
        raise RuntimeError("no session")
    return s.get(url, timeout=35, verify=False).content


def fetch_raw(url):
    u = enc(url)
    if "drive.google.com" in u:
        m = re.search(r"[-\w]{25,}", url)
        if m:
            u = f"https://drive.google.com/uc?export=download&id={m.group(0)}"
    try:
        return urllib.request.urlopen(urllib.request.Request(u, headers=UA),
                                      timeout=35, context=ctx).read(30_000_000)
    except urllib.error.HTTPError as e:
        if e.code in (403, 406, 429, 503):
            return waf_get(u)
        raise


def pages_text(raw, url):
    """Return (list_of_page_texts, npages). HTML collapses to a single 'page'."""
    if raw[:4] == b"%PDF" or url.lower().endswith(".pdf"):
        d = fitz.open(stream=raw, filetype="pdf")
        n = min(len(d), 400)
        return [d[i].get_text() for i in range(n)], len(d)
    t = raw.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return [t], 0


def score(pages):
    topic_pages = [i + 1 for i, p in enumerate(pages) if TOPIC.search(p)]
    full = "\n".join(pages)
    topic = len(TOPIC.findall(full))
    vote = len(VOTE.findall(full))
    body = len(BODY.findall(full))
    if topic >= 1 and vote >= 1 and body >= 1:
        verdict = "CONFIRMED"
    elif topic >= 1 and (vote >= 1 or body >= 1):
        verdict = "PROBABLE"
    elif topic >= 1:
        verdict = "TOPIC_ONLY"
    else:
        verdict = "NO"
    return verdict, topic, vote, body, topic_pages


def screen_one(row):
    try:
        raw = fetch_raw(row["url"])
        pages, npp = pages_text(raw, row["url"])
        verdict, topic, vote, body, tpages = score(pages)
        err = ""
    except Exception as e:
        verdict, topic, vote, body, tpages, npp = "FETCH_FAIL", 0, 0, 0, [], 0
        err = type(e).__name__
    return {**row, "verdict": verdict, "topic_hits": topic, "vote_hits": vote,
            "body_hits": body, "topic_pages": ",".join(map(str, tpages[:20])),
            "npages": npp, "err": err}


def main():
    max_per_town = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None   # town_norm filter

    by_town = defaultdict(list)
    for r in csv.DictReader(CAND.open(encoding="utf-8")):
        if only and r["town_norm"] not in only:
            continue
        by_town[r["town_norm"]].append(r)
    work = []
    for tn, rows in by_town.items():
        # Topic-hint docs (URL/anchor already names MBTA/3A) are the dedicated
        # materials -- always screen them first, then by board priority.
        rows.sort(key=lambda r: (0 if r.get("topic_hint") == "1" else 1, int(r["priority"])))
        work.extend(rows[:max_per_town])
    print(f"screening {len(work)} candidate docs "
          f"(<= {max_per_town}/town) across {len(by_town)} towns, {workers} workers")

    fields = ["town", "town_norm", "community_type", "priority", "board", "doctype",
              "year", "verdict", "topic_hits", "vote_hits", "body_hits", "topic_pages",
              "npages", "url", "kind", "err"]
    done = 0
    counts = defaultdict(int)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for res in ex.map(screen_one, work):
                w.writerow(res); f.flush()
                counts[res["verdict"]] += 1
                done += 1
                if res["verdict"] in ("CONFIRMED", "PROBABLE"):
                    print(f"  [{res['verdict']}] {res['town']} {res['board']}/{res['doctype']} "
                          f"{res['year']} t={res['topic_hits']} v={res['vote_hits']} "
                          f"b={res['body_hits']} pp={res['topic_pages']}", flush=True)
                if done % 200 == 0:
                    print(f"  ... {done}/{len(work)}  {dict(counts)}", flush=True)
    print(f"\ndone. verdicts: {dict(counts)}")
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
