#!/usr/bin/env python3
r"""cdx_fullsweep.py -- sharded, ALL-MIMETYPE Wayback CDX enumeration for Actions.

Why this exists alongside `muni-harvest wayback`. That command enumerates a host
but filters `mimetype:application/pdf`. A municipal election return published as
an HTML page, a legacy .doc, or a spreadsheet is invisible to it -- and several
of the town-years still open in CivicAtlasMA were published exactly that way
(East Brookfield's returns, which search engines still index by title, were HTML
pages on the pre-CivicPlus site).

Why it runs here and not on the maintainer's machine. archive.org throttles by
cumulative per-IP volume. A full-host enumeration of 50-odd towns is thousands of
CDX rows per host; doing it locally is what got that IP 429'd before. Sharding it
over N runner IPs keeps every IP far under the limit and finishes in parallel.

Input  (default config/cdx_gap_hosts.csv):  town,host,years   (years pipe-joined)
Output (default out/): cdx_hits_<shard>.csv  town,year,url,timestamp,mimetype,why
                       cdx_hosts_<shard>.csv town,host,status,n_urls,n_hits

`cdx_hosts` is not optional bookkeeping: without it a host that was never
successfully enumerated is indistinguishable from a town that genuinely has
nothing archived, which is the exact error this project keeps paying for.

Run: python scripts/cdx_fullsweep.py --hosts-csv config/cdx_gap_hosts.csv \
         --shard 1/8 --out out
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request

CDX = "https://web.archive.org/cdx/search/cdx"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

ELECTION = re.compile(
    r"election|result|canvass|precinct|tally|ballot|town.?clerk|vote", re.I)
DOCEXT = re.compile(r"\.(pdf|doc|docx|xls|xlsx|csv)(\?|$)", re.I)
# Events that share the vocabulary but are NOT the annual town election.
NOTOURS = re.compile(
    r"state.?(election|primary)|presidential|primary|special.?(state|district)"
    r"|caucus|warrant|schedule|calendar|absentee|early.?vot|registration"
    r"|nomination|candidate.?(info|packet)|poll.?worker", re.I)


def cdx(host, tries=5):
    out, resume, seen = [], None, set()
    for _ in range(24):
        p = [("url", host), ("matchType", "host"), ("filter", "statuscode:200"),
             ("collapse", "urlkey"), ("output", "json"), ("limit", "5000"),
             ("showResumeKey", "true"), ("fl", "original,timestamp,mimetype")]
        if resume:
            p.append(("resumeKey", resume))
        url = CDX + "?" + urllib.parse.urlencode(p)
        rows = None
        for attempt in range(1, tries + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=180) as fh:
                    rows = json.loads(fh.read().decode("utf-8", "replace") or "[]")
                break
            except Exception as exc:  # noqa: BLE001
                if attempt >= tries:
                    raise
                bad = any(s in str(exc).lower() for s in
                          ("429", "too many", "refused", "reset", "timed out"))
                time.sleep((45 * attempt if bad else 2 ** attempt)
                           + random.uniform(0, 10))
        if not rows or len(rows) < 2:
            break
        body = rows[1:]
        resume = None
        if body and (not body[-1] or len(body[-1]) == 1):
            if body[-1] and body[-1][0]:
                resume = body[-1][0]
            body = [r for r in body if r and len(r) >= 2]
        for r in body:
            if r[0] in seen:
                continue
            seen.add(r[0])
            out.append((r[0], r[1], r[2] if len(r) > 2 else ""))
        if not resume:
            break
        time.sleep(1.0)
    return out


def why(url, year):
    """Does this URL name the gap year and read like that year's town election?"""
    u = url.lower()
    yy = year[2:]
    if not (year in u or "/" + yy in u or "-" + yy in u
            or yy + "-" in u or yy + "." in u or "_" + yy in u):
        return None
    if not ELECTION.search(u):
        return None
    tag = "doc" if DOCEXT.search(u) else "page"
    # Kept, but labelled -- a state-election file under a gap year is a near-miss
    # worth seeing, not a hit worth fetching first.
    return ("offevent:" if NOTOURS.search(u) else "") + tag


def shard(rows, spec):
    if not spec:
        return rows
    i, n = (int(x) for x in spec.split("/"))
    return [r for k, r in enumerate(rows) if k % n == (i - 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts-csv", default="config/cdx_gap_hosts.csv")
    ap.add_argument("--shard", default=None)
    ap.add_argument("--out", default="out")
    ap.add_argument("--dump-raw", action="store_true",
                    help="also write cdx_raw_<shard>.csv: EVERY enumerated url, "
                         "unfiltered. The `why` classifier is where recall is "
                         "lost -- Merrimac's May-2022 local return sits at a "
                         "DocumentCenter id whose slug the classifier does not "
                         "recognise, so it never reached cdx_hits. Keeping the "
                         "raw enumeration means the next question can be asked "
                         "of the data instead of of archive.org again.")
    a = ap.parse_args()

    with open(a.hosts_csv, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("host") or "").strip()]
    mine = shard(rows, a.shard)
    os.makedirs(a.out, exist_ok=True)
    tag = (a.shard or "1/1").replace("/", "_")

    hp = os.path.join(a.out, "cdx_hits_%s.csv" % tag)
    sp = os.path.join(a.out, "cdx_hosts_%s.csv" % tag)
    with open(hp, "w", encoding="utf-8", newline="") as hf, \
         open(sp, "w", encoding="utf-8", newline="") as sf:
        hw, sw = csv.writer(hf), csv.writer(sf)
        hw.writerow(["town", "year", "url", "timestamp", "mimetype", "why"])
        sw.writerow(["town", "host", "status", "n_urls", "n_hits"])
        for k, r in enumerate(mine, 1):
            town, host = r["town"], r["host"].strip()
            years = [y for y in (r.get("years") or "").split("|") if y]
            try:
                urls = cdx(host)
            except Exception as exc:  # noqa: BLE001
                sw.writerow([town, host, "ERR:" + str(exc)[:80], 0, 0])
                sf.flush()
                print("  %-18s %-32s ERR %s" % (town, host, str(exc)[:60]),
                      flush=True)
                continue
            n = 0
            if rrw:
                for u, ts, mime in urls:
                    rrw.writerow([town, host, u, ts, mime])
                rf.flush()
            for u, ts, mime in urls:
                for y in years:
                    w = why(u, y)
                    if w:
                        hw.writerow([town, y, u, ts, mime, w])
                        n += 1
                        break
            hf.flush()
            sw.writerow([town, host, "OK", len(urls), n])
            sf.flush()
            print("  [%2d/%2d] %-18s %-32s %6d urls -> %3d hits"
                  % (k, len(mine), town, host, len(urls), n), flush=True)
            time.sleep(1.0)
    if rf:
        rf.close()
        print("  raw enumeration written to %s" % rp)
    print("wrote %s and %s" % (hp, sp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
