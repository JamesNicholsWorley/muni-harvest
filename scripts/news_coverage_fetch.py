"""Discovery half of the CivicAtlasMA news-coverage sweep. Runs on a runner IP.

WHAT THIS IS FOR. CivicAtlasMA links each municipal election to the journalism
about it -- previews, candidate profiles, candidates' nights, letters, results,
aftermath -- not only to the one story that happened to carry a tally. Finding
that is ~18,800 outlet queries across ~176 searchable Massachusetts outlets and
2,106 town-years: 6+ hours from one residential IP, and the surest way to get
that address rate-limited. Sharded across runners it is well under an hour.

WHAT THIS IS NOT. It does not decide whether an article is about an election.
That judgement lives in CivicAtlasMA's src/classify_news_relevance.py and runs
offline over this script's output, so the rules can be re-scored against the
whole corpus without re-fetching a single page, and a runner can never carry a
stale copy of them. This script only fetches and reports, including its failures.

THE ONE RULE IT MUST NOT BREAK. A silence is not a negative. Every outlet
attempt emits a `reach` record saying what happened -- ok, http_403, timeout,
truncated -- so the consumer can tell "searched, nothing there" from "never
actually asked". Emitting nothing for a failed outlet would let a rate-limited
runner look exactly like a town with no coverage.

Input:  config/news_coverage_worklist.json  (built by CivicAtlasMA's
        src/build_news_worklist.py; carries outlets, queries and date windows)
Output: JSONL, one object per line:
          {"t":"item","town":..,"year":..,"outlet":..,"channel":..,
           "url":..,"title":..,"snippet":..,"date":..}
          {"t":"reach","town":..,"year":..,"outlet":..,"channel":..,
           "status":..,"n":..,"note":..}

    python scripts/news_coverage_fetch.py --worklist config/news_coverage_worklist.json \
        --shard 1/16 --out news_coverage.jsonl
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# curl_cffi defeats TLS-fingerprint 403s; a runner often does not need it, so it
# is optional rather than a hard dependency.
try:
    from curl_cffi import requests as _rq
    _SESS = _rq.Session(impersonate="chrome124")
except Exception:
    _SESS = None

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
TIMEOUT = 40
PER_PAGE, MAX_PAGES = 100, 6
HTML_MAX_PAGES = 5
SITEMAP_FALLBACK_BELOW = 20
MAX_PER_OUTLET = 600

TAG = re.compile(r"<[^>]+>")
DATE_IN_URL = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/")
# NOTE the unquoted-href alternative. iberkshires.com writes its result links as
# <a href=/story/83744/Slug.html>, so a pattern demanding quotes matched only the
# site's navigation -- every search result from that outlet was silently dropped,
# and its dates with them.
ANCHOR = re.compile(
    r"""<a\b[^>]*?href=(?:"([^"]+)"|'([^']+)'|([^\s>]+))[^>]*>(.*?)</a>""",
    re.I | re.S)
LOC = re.compile(r"<loc>\s*([^<]+?)\s*</loc>", re.I)
LASTMOD = re.compile(r"<lastmod>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", re.I)
SLUG_ELECTION = re.compile(
    r"(?i)elect|ballot|candidat|vote|race|select-?board|town-meeting|"
    r"wins|seat|recount|override|primary")

# A search-results page prints the date beside each headline, so the publication
# date is free here -- no second request, and no opening the article. Worth doing
# well: an undated item cannot be tied to one election year, which is the main
# reason an article has to be escalated to a human at all.
TIME_TAG = re.compile(r'datetime="(\d{4}-\d{2}-\d{2})', re.I)
TEXT_DATE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+"
    r"(\d{1,2}),?\s+(20\d{2})\b", re.I)
_MON = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
     "nov", "dec"], 1)}

SLEEP = 1.2
_sitemaps = {}


def date_near(body, start, end, span=700):
    """The date printed nearest this anchor, or ''. Nearest wins, so a sidebar's
    date cannot be attached to a result in the main list."""
    lo, hi = max(0, start - span), min(len(body), end + span)
    chunk = body[lo:hi]
    anchor_at = start - lo
    best, bestd = "", 10 ** 9
    for m in TIME_TAG.finditer(chunk):
        d = abs(m.start() - anchor_at)
        if d < bestd:
            best, bestd = m.group(1), d
    for m in TEXT_DATE.finditer(chunk):
        d = abs(m.start() - anchor_at)
        if d < bestd:
            mon = _MON.get(m.group(1)[:3].lower())
            if mon:
                best, bestd = "%s-%02d-%02d" % (m.group(3), mon, int(m.group(2))), d
    return best


def fetch(url, tries=2):
    """(status, text). status None means the request never completed, which is
    NOT the same as a site that answered with nothing."""
    for i in range(tries):
        try:
            if _SESS is not None:
                r = _SESS.get(url, timeout=TIMEOUT, allow_redirects=True)
                return r.status_code, (r.text or "")
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception:
            if i == tries - 1:
                return None, ""
            time.sleep(SLEEP * (i + 1))
    return None, ""


def untag(s):
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", s or ""))).strip()


def paged(url, n):
    """WordPress paginates search as /page/N/?s=... ; others take &page=N."""
    if "?" in url:
        head, qs = url.split("?", 1)
        head = head.rstrip("/")
        if re.search(r"[?&]?s=", "?" + qs):
            return "%s/page/%d/?%s" % (head, n, qs)
        return "%s?%s&page=%d" % (head, qs, n)
    return "%s/page/%d/" % (url.rstrip("/"), n)


def ch_wpjson(host, q, after, before):
    out = []
    for page in range(1, MAX_PAGES + 1):
        url = ("https://%s/wp-json/wp/v2/posts?search=%s&after=%sT00:00:00"
               "&before=%sT23:59:59&per_page=%d&page=%d&orderby=date&order=asc"
               "&_fields=date,link,title,excerpt"
               % (host, urllib.parse.quote_plus(q), after, before, PER_PAGE, page))
        st, body = fetch(url)
        if st != 200 or not body.strip().startswith("["):
            return (out, "ok") if page > 1 else (None, "http_%s" % st)
        try:
            posts = json.loads(body)
        except Exception:
            break
        out += [{"url": p.get("link", ""),
                 "title": untag((p.get("title") or {}).get("rendered", "")),
                 "snippet": untag((p.get("excerpt") or {}).get("rendered", ""))[:400],
                 "date": (p.get("date") or "")[:10]} for p in posts]
        if len(posts) < PER_PAGE:
            return out, "ok"
        time.sleep(SLEEP)
    return out, "ok_TRUNCATED_at_%d" % len(out)


def ch_query_s(host, endpoint, href_rx, q, after, before):
    tmpl = endpoint or ("https://%s/?s={q}" % host)
    base = tmpl.replace("{q}", urllib.parse.quote_plus(q))
    bodies = []
    for page in range(1, HTML_MAX_PAGES + 1):
        url = base if page == 1 else paged(base, page)
        st, body = fetch(url)
        if page == 1 and st != 200:
            return None, "http_%s" % st
        if st != 200 or not body:
            break
        bodies.append(body)
        if page < HTML_MAX_PAGES:
            time.sleep(SLEEP)
    body = "\n".join(bodies)
    items, seen = [], set()
    for _m in ANCHOR.finditer(body):
        href = _m.group(1) or _m.group(2) or _m.group(3) or ""
        text = _m.group(4)
        if href.startswith("#") or href.startswith("javascript"):
            continue
        if href_rx and not re.search(href_rx, href):
            continue
        if not href_rx and not (DATE_IN_URL.search(href) or "/story/" in href
                                or len(href.strip("/").split("/")[-1]) > 20):
            continue
        full = href if href.startswith("http") else (
            "https://%s%s" % (host, href if href.startswith("/") else "/" + href))
        t = untag(text)
        if not t or len(t) < 12 or full in seen:
            continue
        seen.add(full)
        m = DATE_IN_URL.search(full)
        d = "%s-%s-%s" % m.groups() if m else date_near(body, _m.start(), _m.end())
        if d and not (after <= d <= before):
            continue
        items.append({"url": full, "title": t, "snippet": "", "date": d})
        if len(items) >= MAX_PER_OUTLET:
            break
    return items, "ok"


def sitemap_urls(host, max_maps=12):
    """Fallback for a site whose search cannot be paginated. Cached per host."""
    if host in _sitemaps:
        return _sitemaps[host]
    seen, out, queue = set(), [], ["https://%s/sitemap.xml" % host]
    st, body = fetch("https://%s/robots.txt" % host)
    if st == 200:
        queue += re.findall(r"(?im)^\s*sitemap:\s*(\S+)", body)
    while queue and len(seen) < max_maps:
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        st, body = fetch(u)
        time.sleep(SLEEP)
        if st != 200 or "<" not in body:
            continue
        locs, mods = LOC.findall(body), LASTMOD.findall(body)
        if "<sitemapindex" in body.lower():
            queue += [l for l in locs if l.endswith(".xml")][:max_maps]
            continue
        for i, l in enumerate(locs):
            out.append({"url": l, "lastmod": mods[i] if i < len(mods) else ""})
    _sitemaps[host] = out
    return out


def ch_sitemap(host, town, after, before):
    urls = sitemap_urls(host)
    if not urls:
        return None, "no_sitemap"
    tslug = re.sub(r"[^a-z0-9]+", "-", town.lower())
    items = []
    for u in urls:
        loc, mod = u["url"], u.get("lastmod", "")
        if mod and not (after <= mod <= before):
            continue
        slug = loc.rsplit("/", 1)[-1]
        if not (SLUG_ELECTION.search(slug) or tslug in loc.lower()):
            continue
        m = DATE_IN_URL.search(loc)
        d = "%s-%s-%s" % m.groups() if m else mod
        if d and not (after <= d <= before):
            continue
        items.append({"url": loc, "title": slug.replace("-", " ").strip(),
                      "snippet": "", "date": d})
        if len(items) >= MAX_PER_OUTLET:
            break
    return items, "ok"


def ch_gnews(town, year, after, before):
    out, seen = [], set()
    for q in ("%s Massachusetts town election" % town,
              "%s MA election candidates" % town,
              "%s MA election results %s" % (town, year)):
        url = ("https://news.google.com/rss/search?q=%s&hl=en-US&gl=US&ceid=US:en"
               % urllib.parse.quote_plus(q))
        st, body = fetch(url)
        time.sleep(SLEEP)
        if st != 200 or not body:
            continue
        try:
            root = ET.fromstring(body.encode("utf-8"))
        except Exception:
            continue
        for it in root.iter("item"):
            link = (it.findtext("link") or "").strip()
            if not link or link in seen:
                continue
            seen.add(link)
            d = ""
            pub = it.findtext("pubDate") or ""
            try:
                d = time.strftime("%Y-%m-%d", time.strptime(pub[5:16], "%d %b %Y"))
            except Exception:
                pass
            if d and not (after <= d <= before):
                continue
            src = it.find("{*}source")
            out.append({"url": link, "title": (it.findtext("title") or "").strip(),
                        "snippet": untag(it.findtext("description") or "")[:400],
                        "date": d, "source": src.text if src is not None else ""})
    return out, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worklist", default="config/news_coverage_worklist.json")
    ap.add_argument("--shard", default=None, help="i/N")
    ap.add_argument("--out", default="news_coverage.jsonl")
    ap.add_argument("--sleep", type=float, default=1.2)
    ap.add_argument("--no-gnews", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    global SLEEP
    SLEEP = a.sleep

    with open(a.worklist, encoding="utf-8") as fh:
        jobs = json.load(fh)["jobs"]
    if a.shard:
        i, n = (int(x) for x in a.shard.split("/"))
        jobs = [j for k, j in enumerate(jobs) if k % n == (i - 1)]
    if a.limit:
        jobs = jobs[:a.limit]
    print("shard %s: %d town-years" % (a.shard or "1/1", len(jobs)), flush=True)

    n_item = 0
    with open(a.out, "w", encoding="utf-8") as out:
        def emit(o):
            out.write(json.dumps(o, ensure_ascii=False) + "\n")

        for k, job in enumerate(jobs, 1):
            town, year = job["town"], job["year"]
            after, before = job["after"], job["before"]
            for host in job.get("not_asked", []):
                emit({"t": "reach", "town": town, "year": year, "outlet": host,
                      "channel": "-", "status": "not_asked", "n": 0,
                      "note": "beyond max_outlets cap"})
            for o in job["outlets"]:
                host, kind = o["host"], o["kind"]
                got, notes, dead = [], [], 0
                qs = o["queries"] if kind == "wp_json" else \
                    [q for q in o["queries"] if q][:2] or [town]
                for q in qs:
                    if kind == "wp_json":
                        items, note = ch_wpjson(host, q, after, before)
                    else:
                        items, note = ch_query_s(host, o["endpoint"], o["href"],
                                                 q, after, before)
                    time.sleep(SLEEP)
                    if items is None:
                        dead += 1
                    else:
                        got += items
                    notes.append(note)
                emit({"t": "reach", "town": town, "year": year, "outlet": host,
                      "channel": kind,
                      "status": "unreachable" if dead == len(qs) else "ok",
                      "n": len(got),
                      "note": "%d queries; %s" % (len(qs), ";".join(sorted(set(notes))[:3]))})
                for it in got:
                    it.update(t="item", town=town, year=year, outlet=host,
                              channel=kind)
                    emit(it)
                    n_item += 1

                # A thin search result is not proof of a thin archive.
                if len(got) < SITEMAP_FALLBACK_BELOW:
                    sm, smnote = ch_sitemap(host, town, after, before)
                    emit({"t": "reach", "town": town, "year": year, "outlet": host,
                          "channel": "sitemap",
                          "status": "ok" if sm is not None else "unreachable",
                          "n": len(sm or []),
                          "note": "%s; fallback after %d" % (smnote, len(got))})
                    for it in (sm or []):
                        it.update(t="item", town=town, year=year, outlet=host,
                                  channel="sitemap")
                        emit(it)
                        n_item += 1

            if not a.no_gnews:
                items, note = ch_gnews(town, year, after, before)
                emit({"t": "reach", "town": town, "year": year,
                      "outlet": "news.google.com", "channel": "gnews",
                      "status": "ok" if items is not None else "unreachable",
                      "n": len(items or []), "note": note})
                for it in (items or []):
                    it.update(t="item", town=town, year=year,
                              outlet=it.get("source") or "news.google.com",
                              channel="gnews")
                    emit(it)
                    n_item += 1

            if k % 25 == 0:
                print("  %d/%d town-years, %d items" % (k, len(jobs), n_item),
                      flush=True)
                out.flush()
    print("done: %d town-years, %d items -> %s" % (len(jobs), n_item, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
