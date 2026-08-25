"""Scrape a town's annual-report landing pages for the documents they link to.

WHY THIS EXISTS. The URL corpus knows about 1.14M DocumentCenter items and 79K
ArchiveCenter items, and almost none of them carry a title -- they were found by
ID sweep, so /ArchiveCenter/ViewFile/Item/231 says nothing about what it is or
what year it covers. The page that LINKS to it says both. Ashburnham's annual
reports hang off /612/Archived-Town-Reports, Ayer's off /176/Annual-Report, and
the anchor text on those pages is "2014 Annual Town Report".

So this walks the other way round: start from the landing page, read the links,
and let the page's own words supply the year that the document's URL never did.

THREE THINGS IT COLLECTS

  1. Direct document links -- PDFs, DocumentCenter/View, ArchiveCenter/ViewFile.
  2. OFFSITE storage, which is where a surprising number of small towns keep
     their reports: Google Drive appears on 166 of the 260 gap towns' sites,
     Dropbox on 29, S3 on 24. A link that leaves the municipal domain is still
     the town's annual report.
  3. One level of indirection. A landing page often links not to documents but
     to a folder -- DocumentCenter/Index/341, Archive.aspx?AMID=37 -- so those
     are followed once. Only once: this is a targeted harvest, not a crawler.

THE YEAR COMES FROM THE LINK TEXT FIRST. "2014 Annual Town Report" is a
statement; a numeric document id is not. Two-digit fiscal forms (FY05, FY-13)
are read as well, because a filename like fy_05_town_report.pdf is exactly the
case the URL-year regexes have already been caught missing.

Usage: python scripts/scrape_atr_landings.py --pages config/atr_landing_pages.csv \
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

UA = ("muni-harvest civic-document research crawler "
      "(personal academic use; contact jamesnicholsworley@gmail.com)")

A_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                  re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")

# A link worth keeping: a document, or somewhere documents are kept.
DOC_RE = re.compile(
    r"\.pdf(?:$|[?#])|/DocumentCenter/View/|/ArchiveCenter/ViewFile/|"
    r"drive\.google\.com|docs\.google\.com|dropbox\.com|amazonaws\.com|\.s3\.|"
    r"box\.com|onedrive|sharepoint", re.I)
# A link worth following ONE step, because it lists documents.
FOLDER_RE = re.compile(
    r"/DocumentCenter/Index/|/Archive\.aspx\?AMID=|/ArchiveCenter/?$|"
    r"drive\.google\.com/drive/folders", re.I)

# "ANNUAL REPORT" ON ITS OWN IS AMBIGUOUS AND THAT IS THE WHOLE PROBLEM.
# A town's own volume is labelled every which way -- "2014 Annual Town Report",
# "Annual Report 2014", "Report of the Town Officers", "2014 Town Report" -- so
# the bare form has to be accepted. But the fire department, the library and the
# school all publish something they also call an Annual Report, and on a shared
# documents page they sit in the same list. So the bare form is accepted ONLY
# when nothing in the link names a department, and the page it hangs off is
# itself about town reports.
UNAMBIGUOUS_RE = re.compile(
    r"annual[-_\s]*town[-_\s]*report|town[-_\s]*report|"
    r"report[-_\s]*of[-_\s]*the[-_\s]*town(?:\s*officers?)?|"
    r"town[-_\s]*of[-_\s]*[a-z]+[-_\s]*annual[-_\s]*report", re.I)
BARE_ATR_RE = re.compile(r"annual[-_\s]*report|annualreport", re.I)
ATR_RE = re.compile(
    r"annual[-_\s]*(?:town[-_\s]*)?report|town[-_\s]*report|annualreport|"
    r"report[-_\s]*of[-_\s]*the[-_\s]*town", re.I)

# Anything naming a department, board or office is that body's report, not the
# town's. Kept deliberately wide: a false skip costs one document, a false keep
# puts the fire department's annual report in the election-results pipeline.
_DEPT = (r"police|fire|librar|school|water|sewer|dpw|public\s*works|health|"
         r"conservation|planning|assessor|treasurer|collector|retirement|"
         r"zoning|housing|cemetery|recreation|park|harbor|shellfish|veteran|"
         r"council\s*on\s*aging|historic|cultural|agricultur|wetland|"
         r"emergency|ambulance|highway|building|animal|tree|energy|"
         r"finance\s*committee|capital|personnel|licens")
# \w* after each department stem so "librar" reaches "Library" and "assessor"
# reaches "Assessors". Without it "2016 Library Annual Report" reads as the
# town's own volume -- exactly the confusion this list exists to prevent.
NOT_ATR_RE = re.compile(
    r"budget|acfr|\bcafr\b|audit|financial\s*statement|warrant|minutes|agenda|"
    r"(?:" + _DEPT + r")\w*[-_\s]*(?:dep(?:t|artment)|comm(?:ission|ittee)|board|"
    r"district|division|authority|office)?[-_\s]*annual[-_\s]*report|"
    r"annual[-_\s]*report[-_\s]*(?:of|for)?[-_\s]*(?:the[-_\s]*)?(?:" + _DEPT + r")\w*|"
    r"(?:" + _DEPT + r")\w*\W{0,3}\breport\b", re.I)


def is_town_report(anchor, href, page_url):
    """Is this link the TOWN's annual report, and not some department's?"""
    blob = (anchor or "") + " " + (href or "")
    if NOT_ATR_RE.search(blob):
        return False
    if UNAMBIGUOUS_RE.search(blob):
        return True
    # Bare "Annual Report": only from a page that is itself about town reports.
    if BARE_ATR_RE.search(blob):
        return bool(ATR_RE.search(page_url or "")
                    and not NOT_ATR_RE.search(page_url or ""))
    return False

YEAR4_RE = re.compile(r"(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)")
# FY05 / FY-13 / FY 2005 -- the two-digit fiscal form a plain \d{4} scan misses.
YEAR2_RE = re.compile(r"(?i)\bfy[\s_-]*(\d{2})(?!\d)")


def text_of(frag):
    return html.unescape(TAG_RE.sub(" ", frag or "")).strip()


def years_in(s):
    out = {int(y) for y in YEAR4_RE.findall(s or "")}
    for m in YEAR2_RE.finditer(s or ""):
        n = int(m.group(1))
        out.add(2000 + n if n <= 49 else 1900 + n)
    return sorted(out)


def load_fetch():
    try:
        from muni_harvest.core.fetchio import fetch  # type: ignore
        return fetch
    except Exception:
        import urllib.request

        def fetch(url, timeout=45, **kw):
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=timeout).read()
        return fetch


def get_html(fetch, url, timeout):
    data = fetch(url, timeout=timeout)
    if not data:
        return ""
    if data[:4] == b"%PDF":
        return ""
    return data.decode("utf-8", "replace")


def links(base, page):
    for m in A_RE.finditer(page):
        href = html.unescape(m.group(1)).strip()
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        yield urllib.parse.urljoin(base, href), text_of(m.group(2))[:160]


def shard_by_host(rows, i, n):
    """One runner per host, so the per-runner pace is a real per-host pace."""
    by = {}
    for r in rows:
        h = urllib.parse.urlsplit(r["url"]).netloc.lower().replace("www.", "")
        by.setdefault(h, []).append(r)
    order = sorted(by, key=lambda h: (-len(by[h]), h))
    return [r for k, h in enumerate(order) if k % n == i - 1 for r in by[h]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default="config/atr_landing_pages.csv")
    ap.add_argument("--out", default="out")
    ap.add_argument("--shard", default="1/1")
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--per-minute", type=int, default=20)
    args = ap.parse_args()

    i, n = (int(x) for x in args.shard.split("/"))
    with open(args.pages, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    mine = shard_by_host(rows, i, n)
    os.makedirs(args.out, exist_ok=True)
    print("[shard %d/%d] %d of %d landing pages" % (i, n, len(mine), len(rows)),
          flush=True)

    fetch = load_fetch()
    gap = 60.0 / max(args.per_minute, 1)
    last = [0.0]

    def pace():
        dt = time.time() - last[0]
        if dt < gap:
            time.sleep(gap - dt)
        last[0] = time.time()

    fp = os.path.join(args.out, "atr_found_%d.csv" % i)
    lp = os.path.join(args.out, "landing_log_%d.csv" % i)
    seen = set()
    found = 0
    with open(fp, "w", newline="", encoding="utf-8") as ff, \
            open(lp, "w", newline="", encoding="utf-8") as lf:
        fw = csv.DictWriter(ff, ["municipality", "year", "url", "anchor",
                                 "source_page", "via", "offsite"])
        fw.writeheader()
        lw = csv.DictWriter(lf, ["municipality", "page", "status", "links",
                                 "kept", "detail"])
        lw.writeheader()

        for k, r in enumerate(mine, 1):
            muni, page = r["municipality"], r["url"]
            queue, depth, kept = [(page, "landing")], 0, 0
            visited = set()
            while queue and depth <= 1:
                nxt = []
                for u, via in queue:
                    if u in visited:
                        continue
                    visited.add(u)
                    pace()
                    try:
                        doc = get_html(fetch, u, args.timeout)
                    except Exception as e:
                        lw.writerow({"municipality": muni, "page": u,
                                     "status": "ERROR", "links": 0, "kept": 0,
                                     "detail": repr(e)[:120]})
                        continue
                    if not doc:
                        lw.writerow({"municipality": muni, "page": u,
                                     "status": "NO_HTML", "links": 0, "kept": 0,
                                     "detail": ""})
                        continue
                    nlink = 0
                    for href, txt in links(u, doc):
                        nlink += 1
                        blob = href + " " + txt
                        if DOC_RE.search(href):
                            if not is_town_report(txt, href, page):
                                continue
                            if href in seen:
                                continue
                            seen.add(href)
                            ys = years_in(txt) or years_in(href)
                            host = urllib.parse.urlsplit(href).netloc.lower()
                            base = urllib.parse.urlsplit(u).netloc.lower()
                            fw.writerow({
                                "municipality": muni,
                                "year": max(ys) if ys else "",
                                "url": href, "anchor": txt,
                                "source_page": u, "via": via,
                                "offsite": "yes" if host and host != base else "no"})
                            kept += 1
                            found += 1
                        elif depth == 0 and FOLDER_RE.search(href):
                            if ATR_RE.search(blob) or ATR_RE.search(page):
                                nxt.append((href, "folder"))
                    lw.writerow({"municipality": muni, "page": u, "status": "OK",
                                 "links": nlink, "kept": kept, "detail": via})
                queue, depth = nxt[:12], depth + 1
            if k % 10 == 0:
                print("  %4d/%4d pages, %d documents found"
                      % (k, len(mine), found), flush=True)
                ff.flush()
                lf.flush()
    print("[shard %d/%d] done: %d documents" % (i, n, found), flush=True)


if __name__ == "__main__":
    main()
