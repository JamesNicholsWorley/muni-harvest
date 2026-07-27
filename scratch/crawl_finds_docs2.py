"""Drive from sitemap: fetch every election/clerk/voting page and extract DocumentCenter
doc links. Proves whether a proper crawl of content pages recovers the election PDFs."""
import re,sys,ssl,http.cookiejar,urllib.request
HOST=sys.argv[1] if len(sys.argv)>1 else "www.cityoflawrence.com"
TARGET=sys.argv[2] if len(sys.argv)>2 else "51303"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    urllib.request.HTTPSHandler(context=ctx)); op.addheaders=[("User-Agent",UA)]
def get(u):
    try:
        r=op.open(u,timeout=40); return r.read().decode("utf-8","replace")
    except Exception as e: return f"__ERR__{e}"
sm=get(f"https://{HOST}/sitemap.xml")
locs=re.findall(r'<loc>([^<]+)</loc>',sm)
elect=[u for u in locs if re.search(r'elect|voting|clerk|result|regist',u,re.I)]
print(f"sitemap: {len(locs)} pages; election/clerk/voting pages: {len(elect)}")
for u in elect: print("   ",u[len(f'https://{HOST}'):])
allids=set()
found_target=None
for u in elect:
    h=get(u)
    if h.startswith("__ERR__"): continue
    ids=set(re.findall(r'/DocumentCenter/View/(\d+)',h,re.I))|set(re.findall(r'documentID=(\d+)',h,re.I))
    allids|=ids
    if TARGET in ids: found_target=u
    if ids: print(f"   {u[len(f'https://{HOST}'):]:<45} -> {len(ids)} doc links")
print(f"\ntotal distinct doc ids linked from election pages: {len(allids)}")
print(f"target {TARGET} linked from a crawlable page? {'YES -> '+found_target if found_target else 'NO'}")
if allids: print("sample ids:", sorted(allids, key=lambda x:-int(x))[:15])
