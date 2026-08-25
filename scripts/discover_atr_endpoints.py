"""Live discovery of a town's annual-report documents, aimed at the actual gap.

WHY NOT MORE LANDING PAGES. The corpus-derived landing-page sweep found 1,149
documents across 98 towns and only EIGHTEEN of them landed on a town-year we did
not already hold. That is not a failure of the scraper; it is selection bias in
its input. The corpus knows most about the towns it already crawled well, which
are the same towns DSpace already covers. Mining it again asks the same towns
the same question.

So this starts from the GAP instead: the 20 towns with no DSpace volume in the
window at all, and the towns where DSpace simply lacks specific years. For each
it goes at the site directly, by four routes that do not depend on what the
corpus happens to know:

  1. sitemap.xml (and sitemap indexes) -- the site's own list of its pages.
  2. The CivicPlus / Revize / Drupal document modules by id sweep:
     Archive.aspx?AMID=n enumerates an archive TYPE and lists every year of it,
     which is exactly the shape an annual report series has.
     DocumentCenter/Index/n does the same for folders.
  3. The site's own search, where it has one.
  4. Common landing-page slugs -- /annual-reports, /town-reports, /176/Annual-Report.

Everything found is filtered by the same town-versus-department test the landing
scraper uses, because "Annual Report" on its own is the fire department's just as
often as the town's.

Usage: python scripts/discover_atr_endpoints.py --towns config/atr_gap_towns.csv \
           --shard 1/20 --out out
"""
from __future__ import annotations

import argparse
import csv
import html
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrape_atr_landings import (  # noqa: E402
    A_RE, DOC_RE, UA, is_town_report, links, load_fetch, text_of, years_in)

# Slugs a town's annual-report page is actually called, worth trying blind.
SLUGS = ["/annual-reports", "/annual-report", "/town-reports", "/town-report",
         "/annual-town-report", "/annual-town-reports", "/reports",
         "/documentcenter", "/Archive.aspx", "/town-clerk/annual-reports",
         "/departments/town-clerk/annual-reports"]
SITEMAPS = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml",
            "/wp-sitemap.xml", "/sitemap.xml.gz"]
LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
ATR_URL_RE = re.compile(
    r"annual[-_/]*(?:town[-_/]*)?report|town[-_/]*report|annualreport", re.I)


def norm_host(h):
    h = (h or "").strip().rstrip("/")
    h = re.sub(r"^https?://", "", h, flags=re.I)
    return h


def try_get(fetch, url, timeout, pace):
    pace()
    try:
        data = fetch(url, timeout=timeout)
        if not data or data[:4] == b"%PDF":
            return None
        return data.decode("utf-8", "replace")
    except Exception:
        return None


def from_sitemap(fetch, base, timeout, pace, out, muni, seen):
    """The site's own index of itself. Cheapest complete list there is."""
    for sm in SITEMAPS:
        doc = try_get(fetch, base + sm, timeout, pace)
        if not doc:
            continue
        locs = LOC_RE.findall(doc)
        # A sitemap index points at more sitemaps; follow one level.
        subs = [u for u in locs if u.lower().endswith((".xml", ".xml.gz"))][:8]
        for s in subs:
            d2 = try_get(fetch, s, timeout, pace)
            if d2:
                locs += LOC_RE.findall(d2)
        hits = 0
        for u in locs:
            if not ATR_URL_RE.search(u):
                continue
            if u in seen:
                continue
            seen.add(u)
            ys = years_in(u)
            kind = "document" if DOC_RE.search(u) else "page"
            out.append({"municipality": muni, "year": max(ys) if ys else "",
                        "url": u, "anchor": "", "found_by": "sitemap",
                        "kind": kind})
            hits += 1
        if hits:
            return hits
    return 0


SUBPAGE_RE = {
    "AMID": re.compile(r"/Archive\.aspx\?AMID=\d+", re.I),
    "Index": re.compile(r"/DocumentCenter/Index/\d+", re.I),
}


def sweep_module(fetch, base, timeout, pace, out, muni, seen, index_url, tag):
    """Enumerate a vendor module FROM ITS OWN INDEX, not by guessing ids.

    The first version swept AMID=1..45 and found nothing anywhere, which looked
    like the module being absent. It is not: /Archive.aspx returns 200 and a
    full Archive Center, while /Archive.aspx?AMID=1 is a 404. The ids are
    arbitrary, not sequential -- Athol's are 37, 39, 40 -- so guessing them
    finds nothing however many you try. The index page lists the real ones.

    An Archive.aspx?AMID=n page is a series listing: every year of one recurring
    document type on a single page, which is exactly the shape of an annual
    report run. That is what makes this route worth taking at all.
    """
    idx = try_get(fetch, index_url, timeout, pace)
    if not idx:
        return 0
    subs = []
    for href, txt in links(index_url, idx):
        if SUBPAGE_RE[tag].search(href) and href not in subs:
            # Only open the archives that sound like town reports.
            if ATR_URL_RE.search(href + " " + txt):
                subs.append(href)
    found = 0
    for u in subs[:12]:
        doc = try_get(fetch, u, timeout, pace)
        if not doc:
            continue
        title = ""
        m = re.search(r"<title>(.*?)</title>", doc, re.S | re.I)
        if m:
            title = text_of(m.group(1))[:120]
        page_is_atr = bool(ATR_URL_RE.search(title + " " + u))
        for href, txt in links(u, doc):
            if not DOC_RE.search(href) or href in seen:
                continue
            if not (is_town_report(txt, href, u)
                    or (page_is_atr and not re.search(
                        r"budget|audit|warrant|minutes|agenda", txt, re.I))):
                continue
            seen.add(href)
            ys = years_in(txt) or years_in(href)
            out.append({"municipality": muni, "year": max(ys) if ys else "",
                        "url": href, "anchor": txt[:160],
                        "found_by": "%s:%s" % (tag, title[:40]),
                        "kind": "document"})
            found += 1
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--towns", default="config/atr_gap_towns.csv")
    ap.add_argument("--out", default="out")
    ap.add_argument("--shard", default="1/1")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--per-minute", type=int, default=25)
    ap.add_argument("--amid-max", type=int, default=45)
    ap.add_argument("--index-max", type=int, default=30)
    args = ap.parse_args()

    i, n = (int(x) for x in args.shard.split("/"))
    with open(args.towns, encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("website")]
    mine = [r for k, r in enumerate(rows) if k % n == i - 1]
    os.makedirs(args.out, exist_ok=True)
    print("[shard %d/%d] %d of %d towns" % (i, n, len(mine), len(rows)), flush=True)

    fetch = load_fetch()
    gap = 60.0 / max(args.per_minute, 1)
    last = [0.0]

    def pace():
        dt = time.time() - last[0]
        if dt < gap:
            time.sleep(gap - dt)
        last[0] = time.time()

    fp = os.path.join(args.out, "endpoints_%d.csv" % i)
    lp = os.path.join(args.out, "discover_log_%d.csv" % i)
    with open(fp, "w", newline="", encoding="utf-8") as ff, \
            open(lp, "w", newline="", encoding="utf-8") as lf:
        fw = csv.DictWriter(ff, ["municipality", "year", "url", "anchor",
                                 "found_by", "kind"])
        fw.writeheader()
        lw = csv.DictWriter(lf, ["municipality", "base", "sitemap", "amid",
                                 "index", "slugs", "total"])
        lw.writeheader()
        for k, r in enumerate(mine, 1):
            muni = r["municipality"]
            host = norm_host(r["website"])
            out, seen = [], set()
            base = None
            for scheme in ("https://", "http://"):
                if try_get(fetch, scheme + host + "/", args.timeout, pace) is not None:
                    base = scheme + host
                    break
            if base is None:
                lw.writerow({"municipality": muni, "base": host,
                             "sitemap": "", "amid": "", "index": "",
                             "slugs": "", "total": "SITE_UNREACHABLE"})
                continue
            n_sm = from_sitemap(fetch, base, args.timeout, pace, out, muni, seen)
            # FINDING THE PAGE IS NOT FINDING THE DOCUMENTS. The sitemap route
            # surfaces /387/Annual-Reports, /321/Annual-Town-Reports,
            # /1222/Annual-Reports -- the right pages, and nothing behind them.
            # Every one has to be opened and read, which is the whole point of
            # having found it.
            n_pg = 0
            for row in [r2 for r2 in list(out) if r2["kind"] == "page"]:
                doc = try_get(fetch, row["url"], args.timeout, pace)
                if not doc:
                    continue
                for href, txt in links(row["url"], doc):
                    if not DOC_RE.search(href) or href in seen:
                        continue
                    if not is_town_report(txt, href, row["url"]):
                        continue
                    seen.add(href)
                    ys = years_in(txt) or years_in(href)
                    out.append({"municipality": muni,
                                "year": max(ys) if ys else "", "url": href,
                                "anchor": txt[:160],
                                "found_by": "page:" + row["url"][-48:],
                                "kind": "document"})
                    n_pg += 1
            n_sm += n_pg
            n_am = sweep_module(fetch, base, args.timeout, pace, out, muni,
                                seen, base + "/Archive.aspx", "AMID")
            n_ix = sweep_module(fetch, base, args.timeout, pace, out, muni,
                                seen, base + "/DocumentCenter", "Index")
            n_sl = 0
            for slug in SLUGS:
                doc = try_get(fetch, base + slug, args.timeout, pace)
                if not doc:
                    continue
                for href, txt in links(base + slug, doc):
                    if not DOC_RE.search(href) or href in seen:
                        continue
                    if not is_town_report(txt, href, base + slug):
                        continue
                    seen.add(href)
                    ys = years_in(txt) or years_in(href)
                    out.append({"municipality": muni,
                                "year": max(ys) if ys else "", "url": href,
                                "anchor": txt[:160], "found_by": "slug" + slug,
                                "kind": "document"})
                    n_sl += 1
            fw.writerows(out)
            lw.writerow({"municipality": muni, "base": base, "sitemap": n_sm,
                         "amid": n_am, "index": n_ix, "slugs": n_sl,
                         "total": len(out)})
            ff.flush()
            lf.flush()
            print("  %3d/%3d %-20s sitemap=%-4d amid=%-4d index=%-4d slug=%-4d"
                  % (k, len(mine), muni[:20], n_sm, n_am, n_ix, n_sl), flush=True)
    print("[shard %d/%d] done" % (i, n), flush=True)


if __name__ == "__main__":
    main()
