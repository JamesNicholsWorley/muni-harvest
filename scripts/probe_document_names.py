"""Read the real filename of an anonymous municipal document, without downloading it.

THE PROBLEM. 170,175 DocumentCenter and ArchiveCenter items on the gap towns'
sites carry no anchor text at all -- they were found by id sweep, so
/DocumentCenter/View/262 says nothing about what it is or what year it covers.
That is the largest untapped pool in the project and it is entirely anonymous.

THE HANDLE. CivicPlus serves the true filename in a header:

    /DocumentCenter/View/262  ->  Content-Disposition: inline;
                                  filename=2021%20Annual%20Report.pdf

HEAD does not work -- CivicPlus answers it with a 404 -- and `Range` is ignored,
so a byte-range trick returns the whole file. But headers arrive BEFORE the
body, so opening the connection, reading the headers and closing without ever
calling read() gets the name and the size for roughly the cost of a TCP
handshake: 0.36s a probe, body never transferred.

That is strictly better than inferring from file size. Size alone separates
poorly -- documents carrying a local return are only 40% of PDFs over 2MB
against a 29% base rate -- while page count separates well (62% precision over
100 pages) but requires the download this is trying to avoid. The filename
settles it outright.

WHY THIS FINDS THINGS NOTHING ELSE DOES. Sweeping the id space reaches documents
no page links to any more. When a town redesigns its site the old annual reports
usually survive in DocumentCenter while every link to them disappears -- which
is exactly the pre-2021 material this project is short of.

Usage:
    python scripts/probe_document_names.py --items config/atr_probe_items.csv \
        --shard 1/20 --out out
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_atr_landings import is_town_report, years_in  # noqa: E402

UA = ("muni-harvest civic-document research crawler "
      "(personal academic use; contact jamesnicholsworley@gmail.com)")
DISP_RE = re.compile(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", re.I)


def probe(url, timeout=25):
    """-> (status, bytes, filename). Headers only; the body is never read."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    r = urllib.request.urlopen(req, timeout=timeout)
    try:
        h = dict(r.headers)
        name = ""
        disp = h.get("Content-Disposition") or ""
        m = DISP_RE.search(disp)
        if m:
            name = urllib.parse.unquote(m.group(1)).strip()
        if not name:
            # Some vendors redirect to a real filename instead of setting the
            # header; the final URL then carries the name.
            tail = urllib.parse.urlsplit(r.geturl()).path.rsplit("/", 1)[-1]
            if "." in tail:
                name = urllib.parse.unquote(tail)
        return r.status, h.get("Content-Length") or "", name
    finally:
        r.close()          # abort before the body transfers


def shard_by_host(rows, i, n):
    """One runner per host: the per-runner pace is then a real per-host pace."""
    by = {}
    for r in rows:
        h = urllib.parse.urlsplit(r["url"]).netloc.lower().replace("www.", "")
        by.setdefault(h, []).append(r)
    order = sorted(by, key=lambda h: (-len(by[h]), h))
    return [r for k, h in enumerate(order) if k % n == i - 1 for r in by[h]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="config/atr_probe_items.csv")
    ap.add_argument("--out", default="out")
    ap.add_argument("--shard", default="1/1")
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--per-minute", type=int, default=40)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--give-up-after", type=int, default=60,
                    help="stop a host after this many consecutive 404s")
    args = ap.parse_args()

    i, n = (int(x) for x in args.shard.split("/"))
    with open(args.items, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    mine = shard_by_host(rows, i, n)
    if args.limit:
        mine = mine[:args.limit]
    os.makedirs(args.out, exist_ok=True)
    print("[shard %d/%d] %d of %d items" % (i, n, len(mine), len(rows)), flush=True)

    gap = 60.0 / max(args.per_minute, 1)
    last = [0.0]

    def pace():
        dt = time.time() - last[0]
        if dt < gap:
            time.sleep(gap - dt)
        last[0] = time.time()

    fp = os.path.join(args.out, "probed_%d.csv" % i)
    hp = os.path.join(args.out, "probe_hosts_%d.csv" % i)
    stat = {}
    t0 = time.time()
    with open(fp, "w", newline="", encoding="utf-8") as ff:
        fw = csv.DictWriter(ff, ["municipality", "url", "status", "bytes",
                                 "filename", "year", "is_atr"])
        fw.writeheader()
        misses = {}
        for k, r in enumerate(mine, 1):
            host = urllib.parse.urlsplit(r["url"]).netloc.lower()
            s = stat.setdefault(host, {"host": host, "n": 0, "ok": 0,
                                       "named": 0, "atr": 0, "dead": 0})
            # A long run of 404s means the id space is exhausted; stop asking.
            if misses.get(host, 0) >= args.give_up_after:
                continue
            s["n"] += 1
            pace()
            try:
                st, ln, name = probe(r["url"], args.timeout)
                misses[host] = 0
                s["ok"] += 1
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    misses[host] = misses.get(host, 0) + 1
                    s["dead"] += 1
                continue
            except Exception:
                continue
            if not name:
                continue
            s["named"] += 1
            atr = is_town_report(name, r["url"], r.get("source_page", ""))
            if atr:
                s["atr"] += 1
            ys = years_in(name)
            fw.writerow({"municipality": r.get("municipality", ""),
                         "url": r["url"], "status": st, "bytes": ln,
                         "filename": name[:180],
                         "year": max(ys) if ys else "",
                         "is_atr": "yes" if atr else "no"})
            # Flush on a row count, NOT on hits. Keying the flush to annual-report
            # hits meant a shard that found none buffered everything and lost the
            # lot when the run was cut short -- 341 named files, zero on disk.
            if s["named"] % 25 == 0:
                ff.flush()
            if k % 200 == 0:
                ff.flush()
                el = time.time() - t0
                tot = sum(v["atr"] for v in stat.values())
                print("  %6d/%6d  %.0fs  %d named, %d annual-report hits"
                      % (k, len(mine), el,
                         sum(v["named"] for v in stat.values()), tot), flush=True)
    with open(hp, "w", newline="", encoding="utf-8") as hf:
        w = csv.DictWriter(hf, ["host", "n", "ok", "named", "atr", "dead"])
        w.writeheader()
        w.writerows(stat.values())
    print("[shard %d/%d] done in %.0fm: %d probed, %d named, %d annual reports"
          % (i, n, (time.time() - t0) / 60, sum(v["n"] for v in stat.values()),
             sum(v["named"] for v in stat.values()),
             sum(v["atr"] for v in stat.values())), flush=True)


if __name__ == "__main__":
    main()
