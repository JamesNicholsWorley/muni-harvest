import json,re,sys,http.cookiejar,urllib.request
HOST=sys.argv[1] if len(sys.argv)>1 else "www.cityoflawrence.com"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); op.addheaders=[("User-Agent",UA)]
home=op.open(f"https://{HOST}/DocumentCenter",timeout=30).read().decode("utf-8","replace")
tok=json.loads(op.open(f"https://{HOST}/antiforgery",timeout=30).read().decode()).get("token")
# context around a recent documentID
i=home.find("documentID=48816")
if i<0:
    m=re.search(r'documentID=(\d+)',home); i=m.start() if m else 0
print("--- context around recent doc ---")
print(re.sub(r'\s+',' ',home[max(0,i-400):i+200]))
# context around 'Election'
j=home.lower().find("election")
print("\n--- context around 'Election' ---")
print(re.sub(r'\s+',' ',home[max(0,j-250):j+250]) if j>0 else "no 'election' on landing")
# The react app calls an endpoint to populate. grep the react js bundle for endpoints.
jsurl=None
for u in re.findall(r'src="([^"]*docCenter[^"]*\.js[^"]*)"',home):
    jsurl=u if u.startswith("http") else f"https://{HOST}{u}"; break
if jsurl:
    try:
        js=op.open(jsurl,timeout=40).read().decode("utf-8","replace")
        print(f"\nreact bundle {jsurl[-50:]} {len(js)}b")
        eps=sorted(set(re.findall(r'["\'](/[A-Za-z0-9_/]*(?:DocumentCenter|ImageRepository|Home)/[A-Za-z0-9_]+)["\']',js)))
        for e in eps[:40]: print("   ",e)
        # url template strings
        tmpls=sorted(set(re.findall(r'["\'](/admin/DocumentCenter/[A-Za-z0-9_/]+)["\']',js)))
        print("  admin templates:",tmpls[:20])
    except Exception as e: print("js err",e)
