"""Google News RSS sweep for 2026 municipal election results. Self-contained, stdlib only.

The site crawlers reach a town's own domain, but 102 of the 297 Massachusetts towns have
never yielded a document from one -- their results exist only as a local newspaper story
(Cape News, iBerkshires, the Vineyard Gazette, a Patch). Those towns need a different
angle, and Google News RSS gives one for free: no API key, no quota, plain XML.

One query per town per phrasing. A hit is kept only if the headline or description names
the town AND says something about results, and only if it is dated in 2026 -- the reused
slug is a known trap here, a "2021" article can serve the 2023 election, so publication
date is checked rather than trusted from the URL.

Run on a GitHub runner: this machine's IP is rate-limited by Google far sooner.

    python scripts/news_rss_2026.py --towns config/y2026_news_towns.csv \
        --shard 1/8 --out news_2026.jsonl
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
RESULT_RE = re.compile(r"result|elected|wins?\b|won\b|tally|unofficial|ousts|"
                       r"re-?elect|defeat|voters? (?:choose|pick|back)", re.I)
ELECTION_RE = re.compile(r"election|select ?board|selectmen|town clerk|"
                         r"school committee|ballot", re.I)
QUERIES = ('"{t}" town election results 2026',
           '"{t}" election results select board 2026',
           '{t} Massachusetts annual town election 2026')


def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                print(f"    [fail] {str(e)[:70]}", flush=True)
                return b""
            time.sleep(4 * (i + 1))
    return b""


def rss(query):
    q = urllib.parse.quote(query)
    return (f"https://news.google.com/rss/search?q={q}"
            f"&hl=en-US&gl=US&ceid=US:en")


ap = argparse.ArgumentParser()
ap.add_argument("--towns", required=True)
ap.add_argument("--shard", default=None, help="i/N")
ap.add_argument("--out", default="news_2026.jsonl")
ap.add_argument("--sleep", type=float, default=1.5)
a = ap.parse_args()

towns = list(csv.DictReader(open(a.towns, encoding="utf-8")))
if a.shard:
    i, n = (int(x) for x in a.shard.split("/"))
    towns = [t for j, t in enumerate(towns) if j % n == i - 1]

kept = seen = 0
with open(a.out, "w", encoding="utf-8") as out:
    for t in towns:
        muni = t["municipality"]
        for tmpl in QUERIES:
            body = fetch(rss(tmpl.format(t=muni)))
            time.sleep(a.sleep)
            if not body:
                continue
            try:
                root = ET.fromstring(body)
            except ET.ParseError:
                continue
            for item in root.iter("item"):
                seen += 1
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                src = (item.findtext("source") or "").strip()
                # published in 2026 -- the slug year lies, the feed date does not
                try:
                    year = parsedate_to_datetime(pub).year
                except Exception:
                    year = 0
                if year != 2026:
                    continue
                blob = f"{title} {src}"
                if muni.lower() not in blob.lower():
                    continue
                if not (RESULT_RE.search(title) and ELECTION_RE.search(blob)):
                    continue
                kept += 1
                out.write(json.dumps({
                    "municipality": muni, "url": link, "title": title,
                    "source": src, "published": pub,
                    "predicted_date": t.get("predicted_2026_date", ""),
                    "discovered_via": "news_rss"}, ensure_ascii=False) + "\n")
        print(f"  [OK] {muni:22s} kept={kept}", flush=True)

print(f"\n[done] {kept} articles kept from {seen} feed items "
      f"across {len(towns)} towns -> {a.out}")
