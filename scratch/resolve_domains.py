"""Resolve real municipal domains for the zero-node / missing towns by probing conventional
MA town URL patterns live. Reports the working domain + whether it's CivicPlus (DocumentCenter)
and has a sitemap — i.e. how well docsweep will do."""
import ssl, re, socket, urllib.request

TOWNS = {
    "Goshen": "goshen", "Gosnold": "gosnold", "Harwich": "harwich", "Monroe": "monroe",
    "North Andover": "northandover", "Norwood": "norwood", "Pelham": "pelham",
    "Petersham": "petersham", "Pittsfield": "pittsfield", "West Brookfield": "westbrookfield",
    "West Springfield": "westspringfield", "Weymouth": "weymouth", "Southampton": "southampton",
}
PATTERNS = [
    "{s}-ma.gov", "{s}ma.gov", "www.{s}-ma.gov", "www.{s}ma.gov",
    "townof{s}.org", "townof{s}.com", "cityof{s}.org", "cityof{s}.com",
    "town.{s}.ma.us", "ci.{s}.ma.us", "{s}.ma.us", "www.townof{s}ma.gov", "{s}-ma.org",
]
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (research; polite)"}

def probe(host):
    try: socket.gethostbyname(host)
    except Exception: return None
    for scheme in ("https", "http"):
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"{scheme}://{host}/", headers=UA),
                                       timeout=15, context=ctx)
            html = r.read(200000).decode("utf-8", "replace"); final = r.geturl()
            cms = "CivicPlus" if "DocumentCenter" in html or "civicplus" in html.lower() else \
                  ("Revize" if "revize" in html.lower() else "")
            return {"status": r.status, "final": final, "len": len(html), "cms": cms}
        except Exception:
            continue
    return None

def sitemap(host):
    try:
        r = urllib.request.urlopen(urllib.request.Request(f"https://{host}/sitemap.xml", headers=UA),
                                   timeout=15, context=ctx)
        return r.read(500000).decode("utf-8","replace").count("<loc>")
    except Exception:
        return 0

for name, s in TOWNS.items():
    found = None
    for pat in PATTERNS:
        host = pat.format(s=s)
        res = probe(host)
        if res and res["status"] == 200 and res["len"] > 3000:
            fh = re.match(r"https?://([^/]+)", res["final"])
            realhost = fh.group(1) if fh else host
            sm = sitemap(realhost)
            found = f"{realhost}  [{res['cms'] or 'plain'}, sitemap_locs={sm}]"
            break
    print(f"  {name:<18} -> {found or 'NO conventional domain resolved'}")
