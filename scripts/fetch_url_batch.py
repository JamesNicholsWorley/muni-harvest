#!/usr/bin/env python3
r"""
fetch_url_batch.py -- self-contained sharded URL fetcher for GitHub Actions.

Purpose: download a list of election-results document URLs from a CLEAN runner IP
(the CivicAtlasMA maintainer's local IP is tar-pitted by many MA municipal WAFs;
GitHub Actions runner IPs are not). Saves raw bytes so CivicAtlasMA can host+parse.

Zero dependency on the muni_harvest package. Uses stdlib urllib first, then
curl_cffi (TLS-impersonation, beats fingerprinting WAFs) if installed. The workflow
`pip install curl_cffi` makes the fallback available.

Input CSV (default config/election_urls.csv): municipality,year,url[,alt_url]
Output (default out/): {Municipality}{Year}.{pdf|xlsx|html} + manifest_<shard>.csv

Run:  python scripts/fetch_url_batch.py --url-csv config/election_urls.csv \
          --shard 1/8 --out out
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import os
import sys
import time
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _kind(data: bytes) -> str:
    if not data:
        return "none"
    if data[:5].startswith(b"%PDF"):
        return "pdf"
    if data[:4] == b"PK\x03\x04":
        return "xlsx"
    head = data[:400].lstrip().lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html") or b"<html" in head:
        return "html"
    return "none"


def _urllib_get(url: str, timeout: int = 40) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def _curl_get(url: str, timeout: int = 40) -> bytes | None:
    try:
        from curl_cffi import requests as cf
        r = cf.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True)
        return r.content if r.status_code == 200 else None
    except Exception:
        return None


def fetch(url: str, timeout: int = 40):
    """(data, kind). Try urllib, then curl_cffi. Retry curl for a doc endpoint that
    urllib served as an HTML WAF challenge."""
    data = _urllib_get(url, timeout)
    k = _kind(data)
    if k in ("pdf", "xlsx"):
        return data, k
    d2 = _curl_get(url, timeout)
    if d2:
        k2 = _kind(d2)
        if k2 != "none":
            return d2, k2
    return (data, k) if data else (None, "none")


def shard_rows(rows, shard):
    if not shard:
        return rows
    i, n = shard.split("/")
    i, n = int(i), int(n)
    return [r for idx, r in enumerate(rows) if idx % n == (i - 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url-csv", default="config/election_urls.csv")
    ap.add_argument("--out", default="out")
    ap.add_argument("--shard", default=None, help="i/N (1-indexed)")
    ap.add_argument("--timeout", type=int, default=40)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rows = list(csv.DictReader(open(args.url_csv, encoding="utf-8")))
    rows = shard_rows(rows, args.shard)
    tag = (args.shard or "1/1").replace("/", "of")
    manifest = os.path.join(args.out, f"manifest_{tag}.csv")
    print(f"[fetch] shard={args.shard or 'all'} rows={len(rows)}", flush=True)

    with open(manifest, "w", newline="", encoding="utf-8") as mf:
        w = csv.writer(mf)
        w.writerow(["municipality", "year", "url", "kind", "status", "bytes",
                    "sha1", "filename"])
        for r in rows:
            muni, year = r["municipality"].strip(), r["year"].strip()
            stem = muni.replace(" ", "") + year
            urls = [u for u in (r.get("url"), r.get("alt_url")) if (u or "").strip()]
            got = None
            html_fallback = None
            for u in urls:
                data, kind = fetch(u.strip(), args.timeout)
                if kind in ("pdf", "xlsx"):
                    got = (u.strip(), data, kind)
                    break
                if kind == "html" and html_fallback is None:
                    html_fallback = (u.strip(), data, kind)  # keep an HTML page (news/results) as fallback
                time.sleep(0.5)
            if not got and html_fallback:
                got = html_fallback
            if not got:
                w.writerow([muni, year, urls[0] if urls else "", "none",
                            "fail", 0, "", ""])
                print(f"  [fail] {stem}", flush=True)
                continue
            u, data, kind = got
            fn = f"{stem}.{kind}"
            with open(os.path.join(args.out, fn), "wb") as fo:
                fo.write(data)
            sha = hashlib.sha1(data).hexdigest()[:16]
            w.writerow([muni, year, u, kind, "ok", len(data), sha, fn])
            print(f"  [ok] {stem} {kind} {len(data)//1024}KB", flush=True)

    print(f"[done] manifest -> {manifest}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
