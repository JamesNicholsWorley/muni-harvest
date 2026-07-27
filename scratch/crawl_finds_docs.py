"""Test the universal fix: does crawling the town's content pages surface the election
PDFs (DocumentCenter/View/{id})? Fetch the Voting&Elections page + sitemap, extract doc
links, check for the target id. If yes, a proper deep crawl recovers them (no CMS auth)."""
import re,sys,ssl,http.cookiejar,urllib.request
HOST=sys.argv[1] if len(sys.argv)>1 else "www.cityoflawrence.com"
PAGES=sys.argv[2:] or ["/235","/Voting-Elections","/elections"]
TARGET="51303"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    urllib.request.HTTPSHandler(context=ctx)); op.addheaders=[("User-Agent",UA)]
def get(path):
    try:
        r=op.open(f"https://{HOST}{path}" if path.startswith("/") else path,timeout=40)
        return r.read().decode("utf-8","replace"), r.geturl()
    except Exception as e: return f"__ERR__{e}",""
def doclinks(html):
    ids=set(re.findall(r'/DocumentCenter/View/(\d+)',html,re.I))
    img=set(re.findall(r'/ImageRepository/Document\?documentID=(\d+)',html,re.I))
    return ids,img

# 1. content pages
for p in PAGES:
    h,u=get(p)
    if h.startswith("__ERR__"): print(f"{p}: {h[:40]}"); continue
    ids,img=doclinks(h)
    print(f"{p} ({u[-40:]}) {len(h)}b: {len(ids)} View links, {len(img)} ImageRepo; target in page: {'YES' if TARGET in ids|img else 'no'}")
    for i in sorted(ids)[:6]: print("    View/"+i)

# 2. sitemap(s) — CivicPlus often lists everything
print("\nsitemaps:")
for sm in ["/sitemap.xml","/Sitemap.xml","/sitemap_index.xml"]:
    h,u=get(sm)
    if h.startswith("__ERR__") or "<" not in h[:200]: print(f"  {sm}: {h[:40]}"); continue
    subs=re.findall(r'<loc>([^<]+)</loc>',h)
    dc=[s for s in subs if "DocumentCenter/View" in s]
    print(f"  {sm}: {len(subs)} locs, {len(dc)} DocumentCenter docs; target: {'YES' if any(TARGET in s for s in dc) else 'no'}")
    for s in subs[:4]: print("     ",s[-70:])
