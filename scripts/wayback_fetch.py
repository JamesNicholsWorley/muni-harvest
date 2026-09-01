#!/usr/bin/env python3
r"""wayback_fetch.py -- pull specific Wayback captures, on a runner IP.

WHY THIS IS NOT DONE LOCALLY. archive.org throttles by cumulative per-IP volume,
and the maintainer's IP is already at the limit: two `web/<ts>id_/<url>` fetches
from it returned HTTP 429 with a 117-byte body. Not a CDX query, not a sweep --
two single-document retrievals. So retrieval moves here alongside enumeration.

Input CSV: name,timestamp,url
  `timestamp` is the 14-digit CDX capture stamp. The `id_` modifier is added
  here, which is what returns the ORIGINAL bytes rather than a rewritten page --
  without it a PDF comes back wrapped in the Wayback banner and a JPEG comes
  back as HTML.

Each row is written to out/<name>.<ext>, where the extension comes from the
source URL. A row that does not return the expected magic bytes is reported in
out/wayback_fetch_reach.csv with the status and byte count rather than being
written, because a 117-byte "file" that is really a throttle notice must never
enter the corpus as a document.

Run: python scripts/wayback_fetch.py --csv config/wb_fetch.csv --out out
"""
from __future__ import annotations

import argparse
import csv
import os
import time
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

MAGIC = {
    "pdf": (b"%PDF",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG",),
    "docx": (b"PK\x03\x04",),
    "xlsx": (b"PK\x03\x04",),
    "doc": (b"\xd0\xcf\x11\xe0", b"PK\x03\x04"),
    "xls": (b"\xd0\xcf\x11\xe0", b"PK\x03\x04"),
}


def ext_of(url):
    tail = url.split("?")[0].rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[-1].lower() if "." in tail else "bin"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="config/wb_fetch.csv")
    ap.add_argument("--out", default="out")
    ap.add_argument("--sleep", type=float, default=6.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    with open(a.csv, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("url") or "").strip()]

    rp = os.path.join(a.out, "wayback_fetch_reach.csv")
    with open(rp, "w", encoding="utf-8", newline="") as rf:
        rw = csv.writer(rf)
        rw.writerow(["name", "timestamp", "url", "status", "bytes", "magic",
                     "written"])
        for r in rows:
            name = r["name"].strip()
            ts = r["timestamp"].strip()
            url = r["url"].strip()
            ext = ext_of(url)
            wb = "https://web.archive.org/web/%sid_/%s" % (ts, url)
            status, body = 0, b""
            for attempt in range(3):
                try:
                    req = urllib.request.Request(wb, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=180) as resp:
                        status = resp.status
                        body = resp.read()
                    break
                except Exception as exc:  # noqa: BLE001
                    status = getattr(exc, "code", 0) or 0
                    body = b""
                    time.sleep(10.0 * (attempt + 1))
            head = body[:4]
            want = MAGIC.get(ext)
            ok = bool(body) and (want is None
                                 or any(body.startswith(m) for m in want))
            if ok:
                with open(os.path.join(a.out, "%s.%s" % (name, ext)), "wb") as fh:
                    fh.write(body)
            rw.writerow([name, ts, url, status, len(body), repr(head),
                         "yes" if ok else "no"])
            rf.flush()
            print("  %-26s HTTP%-4s %9d bytes  %-12r %s"
                  % (name, status, len(body), head,
                     "written" if ok else "NOT WRITTEN -- wrong magic"),
                  flush=True)
            time.sleep(a.sleep)
    print("wrote %s" % rp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
