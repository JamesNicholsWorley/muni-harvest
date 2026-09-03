"""Date an article without opening it, by asking an archive when it first saw the URL.

WHY. CivicAtlasMA can only tie an article to an election year if it has a
publication date. Most dates come free -- from the URL path, a sitemap
`lastmod`, or the `<time>` tag printed beside the headline on the search page.
Some outlets give none of those: berkshireeagle.com yields a date for 8% of its
search results and salemnews.com for 18%, because their result markup carries no
date near the link. Fetching each article to read its date is expensive and runs
into paywalls.

An archive's index answers the same question for free and without opening
anything. A capture cannot precede publication, so the EARLIEST capture is an
upper bound on the publication date, and for a news URL crawled soon after
posting it is usually within days. That is accurate enough to place an article
in an election window, which is all this is for.

TWO INDEXES, BOTH FREE:
  * Wayback CDX  -- /cdx/search/cdx?output=json&fl=timestamp&limit=1
  * Common Crawl -- index.commoncrawl.org/<CRAWL>-index?output=json

MUST RUN ON A RUNNER. CivicAtlasMA's RUNBOOK-wayback-without-getting-blocked.md
is explicit: never query archive.org from the maintainer's machine, not even the
CDX index -- it 429s on a single request from that address while answering
reliably from a runner. That rule is the entire reason this script exists here
rather than in CivicAtlasMA/src.

THE BOUND IS RECORDED AS A BOUND. Output says `first_capture`, not
`published`, and carries which index answered. A consumer that treats an
upper bound as an exact publication date would be asserting more than the
evidence supports -- so the field is named for what it is.

Input:  a CSV of urls (one per line, or a `url` column)
Output: JSONL {"url":..,"first_capture":"YYYY-MM-DD","source":"wayback|cc","n":N}

    python scripts/cdx_article_dates.py --urls config/news_undated_urls.csv \
        --shard 1/8 --out article_dates.jsonl
"""
import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "CivicAtlasMA/1.0 (research; contact jamesnicholsworley@gmail.com)"
WAYBACK = "https://web.archive.org/cdx/search/cdx"
CC_INDEX = "https://index.commoncrawl.org/CC-MAIN-2025-08-index"
SLEEP = 1.0
TIMEOUT = 45


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            # 429 means slow down, not "no captures" -- back off and retry.
            if e.code in (429, 503) and i < tries - 1:
                time.sleep(5 * (i + 1))
                continue
            return e.code, ""
        except Exception:
            if i == tries - 1:
                return None, ""
            time.sleep(SLEEP * (i + 1))
    return None, ""


def wayback_first(url):
    """Earliest Wayback capture as YYYY-MM-DD, or ''."""
    q = ("%s?url=%s&output=json&fl=timestamp&filter=statuscode:200"
         "&collapse=timestamp:8&limit=1" % (WAYBACK, urllib.parse.quote(url, safe="")))
    st, body = get(q)
    if st != 200 or not body.strip():
        return "", st
    try:
        rows = json.loads(body)
    except Exception:
        return "", st
    # first row is the header ["timestamp"]
    for r in rows[1:]:
        ts = r[0] if isinstance(r, list) else str(r)
        if len(ts) >= 8:
            return "%s-%s-%s" % (ts[0:4], ts[4:6], ts[6:8]), st
    return "", st


def cc_first(url):
    """Earliest Common Crawl capture as YYYY-MM-DD, or ''."""
    q = "%s?url=%s&output=json&limit=5" % (CC_INDEX, urllib.parse.quote(url, safe=""))
    st, body = get(q)
    if st != 200 or not body.strip():
        return "", st
    best = ""
    for line in body.splitlines():
        try:
            o = json.loads(line)
        except Exception:
            continue
        ts = str(o.get("timestamp", ""))
        if len(ts) >= 8:
            d = "%s-%s-%s" % (ts[0:4], ts[4:6], ts[6:8])
            if not best or d < best:
                best = d
    return best, st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", required=True)
    ap.add_argument("--shard", default=None, help="i/N")
    ap.add_argument("--out", default="article_dates.jsonl")
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--no-cc", action="store_true")
    a = ap.parse_args()

    global SLEEP
    SLEEP = a.sleep

    urls = []
    with open(a.urls, encoding="utf-8", newline="") as fh:
        sniff = fh.readline()
        fh.seek(0)
        if "url" in sniff.lower() and "," in sniff:
            for row in csv.DictReader(fh):
                u = (row.get("url") or "").strip()
                if u:
                    urls.append(u)
        else:
            urls = [ln.strip() for ln in fh if ln.strip()]
    if a.shard:
        i, n = (int(x) for x in a.shard.split("/"))
        urls = [u for k, u in enumerate(urls) if k % n == (i - 1)]
    print("shard %s: %d urls" % (a.shard or "1/1", len(urls)), flush=True)

    found = 0
    with open(a.out, "w", encoding="utf-8") as out:
        for k, u in enumerate(urls, 1):
            d, st = wayback_first(u)
            src = "wayback"
            time.sleep(SLEEP)
            if not d and not a.no_cc:
                d, st = cc_first(u)
                src = "cc"
                time.sleep(SLEEP)
            if d:
                found += 1
            # An empty answer is recorded, not dropped: "no capture" and "never
            # asked" must stay distinguishable downstream.
            out.write(json.dumps({"url": u, "first_capture": d,
                                  "source": src if d else "",
                                  "status": st}) + "\n")
            if k % 50 == 0:
                print("  %d/%d, dated %d" % (k, len(urls), found), flush=True)
                out.flush()
    print("done: %d/%d dated -> %s" % (found, len(urls), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
