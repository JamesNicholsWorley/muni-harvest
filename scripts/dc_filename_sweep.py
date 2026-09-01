#!/usr/bin/env python3
r"""dc_filename_sweep.py -- read CivicPlus DocumentCenter filenames from the SERVER.

WHY THE EXISTING NEGATIVE IS NOT SAFE. CivicAtlasMA's round 9 enumerated ~40,000
DocumentCenter IDs across 38 CivicPlus towns and reported "ZERO gap-year election
result documents, under both 4-digit and 2-digit year matching". But a CivicPlus
URL is `/DocumentCenter/View/<id>/<slug>` and **the slug is decorative** -- the
server serves by ID and ignores it completely. Matching on a slug is matching on
text the caller wrote, not on anything the town did. (Proven the hard way the same
week: probing eight different dates against Middlefield returned eight identical
396,724-byte files.)

The town's own filename IS available, in the `content-disposition` header:

    GET /DocumentCenter/View/1538   ->  filename=May 6 2025 Warren Election Results.pdf
    GET /DocumentCenter/View/1956   ->  filename=May 5th Annual Election.pdf

Note the second one: "May 5th Annual Election.pdf" carries no year at all, so no
year-matching scheme of any kind would ever have found it. That is the class of
document this sweep exists for.

A ranged GET (`Range: bytes=0-511`) returns the header without the body, so a
full town costs kilobytes rather than gigabytes. It is still tens of thousands of
requests, which is why it runs here and not on the maintainer's machine.

Input  (default config/dc_gap_towns.csv): town,host,years,max_id
Output (default out/): dc_names_<shard>.csv  town,id,filename,ctype,bytes
                       dc_reach_<shard>.csv  town,host,probed,named,errors

`dc_reach` matters: a town whose probes all errored must not read as a town with
no election documents.

Run: python scripts/dc_filename_sweep.py --towns-csv config/dc_gap_towns.csv \
         --shard 1/8 --workers 8 --out out
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
RX_DISP = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', re.I)
LOCK = threading.Lock()


def probe(host, doc_id, tries=2):
    """(filename, content-type, length) for one DocumentCenter id, or None."""
    url = "https://%s/DocumentCenter/View/%d" % (host, doc_id)
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Range": "bytes=0-511"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                cd = r.headers.get("content-disposition", "") or ""
                m = RX_DISP.search(cd)
                if not m:
                    return None
                name = urllib.parse.unquote(m.group(1)).strip()
                return (name, (r.headers.get("content-type") or "")[:40],
                        r.headers.get("content-range", "") or "")
        except Exception:  # noqa: BLE001
            if attempt + 1 >= tries:
                return "ERR"
            time.sleep(1.0)
    return None


def shard_rows(rows, spec):
    if not spec:
        return rows
    i, n = (int(x) for x in spec.split("/"))
    return [r for k, r in enumerate(rows) if k % n == (i - 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--towns-csv", default="config/dc_gap_towns.csv")
    ap.add_argument("--shard", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="out")
    a = ap.parse_args()

    with open(a.towns_csv, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("host") or "").strip()]
    mine = shard_rows(rows, a.shard)
    os.makedirs(a.out, exist_ok=True)
    tag = (a.shard or "1_1").replace("/", "_")

    npath = os.path.join(a.out, "dc_names_%s.csv" % tag)
    rpath = os.path.join(a.out, "dc_reach_%s.csv" % tag)
    with open(npath, "w", encoding="utf-8", newline="") as nf, \
         open(rpath, "w", encoding="utf-8", newline="") as rf:
        nw, rw = csv.writer(nf), csv.writer(rf)
        nw.writerow(["town", "id", "filename", "ctype", "range"])
        rw.writerow(["town", "host", "probed", "named", "errors"])

        for r in mine:
            town, host = r["town"], r["host"].strip()
            top = int(r.get("max_id") or 3000)
            stats = {"probed": 0, "named": 0, "errors": 0}

            def one(i, town=town, host=host, nw=nw, stats=stats):
                res = probe(host, i)
                with LOCK:
                    stats["probed"] += 1
                    if res == "ERR":
                        stats["errors"] += 1
                    elif res:
                        stats["named"] += 1
                        nw.writerow([town, i, res[0], res[1], res[2]])

            t0 = time.time()
            with ThreadPoolExecutor(max_workers=a.workers) as ex:
                list(ex.map(one, range(1, top + 1)))
            nf.flush()
            rw.writerow([town, host, stats["probed"], stats["named"],
                         stats["errors"]])
            rf.flush()
            print("  %-18s %-26s probed=%d named=%d err=%d  %.0fs"
                  % (town, host, stats["probed"], stats["named"],
                     stats["errors"], time.time() - t0), flush=True)
    print("wrote %s and %s" % (npath, rpath))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
