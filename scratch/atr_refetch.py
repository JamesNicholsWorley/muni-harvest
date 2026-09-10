"""Fetch the full Annual Town Report for the town-years whose cut held no return.

The cut is what failed, not the report. `tools/atr_sections.py` keeps only the
pages it chose and throws the report away, so a re-cut has to fetch again.

Everything is fetched from archive.org or the State Library. A URL already
pointing at an archive is used as it stands; a municipal URL is resolved to a
Wayback snapshot of that same URL through the CDX index, because a datacenter
IP is the wrong client for a town's own web server and this run is not the
discovery project.
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse

ARCHIVE = {"web.archive.org", "archives.lib.state.ma.us", "archive.org",
           "storage.googleapis.com", "drive.google.com", "docs.google.com"}
OUT = "/tmp/reports"


def curl(url, dest=None, timeout=120):
    """(status, bytes). Plain curl: the proxy re-terminates TLS and an
    impersonated ClientHello is reset by it, while curl reads the CA bundle."""
    cmd = ["curl", "-sSL", "--max-time", str(timeout), "-w", "%{http_code}"]
    cmd += ["-o", dest] if dest else ["-o", "-"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=(dest is not None))
    if dest:
        code = (r.stdout or "").strip()[-3:]
        return code, os.path.getsize(dest) if os.path.exists(dest) else 0
    body = r.stdout
    return body[-3:].decode("ascii", "replace"), body[:-3]


def snapshot_for(url):
    """The closest Wayback capture of this exact URL, or None."""
    q = ("https://web.archive.org/cdx/search/cdx?url=%s&output=json"
         "&filter=statuscode:200&limit=8"
         % urllib.parse.quote(url, safe=""))
    code, body = curl(q, timeout=90)
    if code != "200" or not body:
        return None
    try:
        rows = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return None
    if len(rows) < 2:
        return None
    ts, orig = rows[-1][1], rows[-1][2]
    return "https://web.archive.org/web/%sid_/%s" % (ts, orig)


def main():
    targets = json.load(open(sys.argv[1]))
    os.makedirs(OUT, exist_ok=True)
    log = {}
    for i, (stem, url) in enumerate(sorted(targets.items())):
        dest = os.path.join(OUT, stem + ".pdf")
        if os.path.exists(dest) and os.path.getsize(dest) > 20000:
            log[stem] = ["cached", os.path.getsize(dest), url]
            continue
        host = urllib.parse.urlparse(url).netloc
        use = url
        if host not in ARCHIVE:
            use = snapshot_for(url)
            if not use:
                log[stem] = ["no_snapshot", 0, url]
                print("  no_snapshot %s" % stem, flush=True)
                time.sleep(1.0)
                continue
        code, n = curl(use, dest)
        ok = code == "200" and n > 20000
        if ok:
            with open(dest, "rb") as fh:
                ok = fh.read(5).startswith(b"%PDF")
        if not ok and os.path.exists(dest):
            os.remove(dest)
        log[stem] = ["ok" if ok else "http_" + code, n, use]
        print("  %-12s %-22s %8d  (%d/%d)"
              % (log[stem][0], stem, n, i + 1, len(targets)), flush=True)
        time.sleep(1.5)
    json.dump(log, open(sys.argv[2], "w"), indent=1)
    got = sum(1 for v in log.values() if v[0] in ("ok", "cached"))
    print("\n%d/%d reports in hand" % (got, len(log)))


if __name__ == "__main__":
    main()
