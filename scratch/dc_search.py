import json, re, sys, http.cookiejar, urllib.request, urllib.parse
HOST=sys.argv[1] if len(sys.argv)>1 else "www.cityoflawrence.com"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); op.addheaders=[("User-Agent",UA)]
home=op.open(f"https://{HOST}/DocumentCenter",timeout=30).read().decode("utf-8","replace")
tok=json.loads(op.open(f"https://{HOST}/antiforgery",timeout=30).read().decode()).get("token")

ids=sorted(set(int(x) for x in re.findall(r'documentID=(\d+)',home,re.I)))
print(f"home documentID ids: n={len(ids)} range {ids[:1]}..{ids[-1:]}  sample {ids[-8:]}")

# find the <form> that wraps the search (StartDate/cbDocuments)
for m in re.finditer(r'<form([^>]*)>(.*?)</form>', home, re.S|re.I):
    attrs, inner = m.group(1), m.group(2)
    if "cbDocuments" in inner or "StartDate" in inner or "earch" in inner:
        act=re.search(r'action="([^"]*)"',attrs); meth=re.search(r'method="([^"]*)"',attrs,re.I)
        print(f"\nSEARCH FORM action={act.group(1) if act else '?'} method={meth.group(1) if meth else 'GET'}")
        names=re.findall(r'name="([^"]+)"',inner)
        print("  fields:", names[:30])
        break

# The docCenter react app: search likely posts to /admin/DocumentCenter/Home/_AjaxLoadingReact?type=?
# with a date range or searchPhrase. Try search-style bodies looking for high ids.
def post(path,body):
    req=urllib.request.Request(f"https://{HOST}{path}",data=json.dumps(body).encode(),method="POST",
        headers={"User-Agent":UA,"Content-Type":"application/json","RequestVerificationToken":tok,"X-Requested-With":"XMLHttpRequest"})
    try: return op.open(req,timeout=40).read().decode("utf-8","replace")
    except Exception as e: return f"__ERR__{e}"

print("\nprobing search-style AjaxLoadingReact bodies:")
for typ in (3,4,5,6):
    r=post(f"/admin/DocumentCenter/Home/_AjaxLoadingReact?type={typ}",
           {"value":"1","selectedFolder":1,"loadSource":7,"searchPhrase":"",
            "startDate":"01/01/2015","endDate":"12/31/2025","searchDocuments":True,"searchFolders":False})
    got=re.findall(r'"Value":"(\d+)"',r)
    hi=max((int(x) for x in got),default=0)
    print(f"  type={typ}: {len(r)}b values={len(got)} maxid={hi} {r[:70]!r}")

# Also try the classic GET search results page with querystring
qs=urllib.parse.urlencode({"cbDocuments":"true","StartDate":"01/01/2015","EndDate":"12/31/2025","searchPhrase":""})
for path in [f"/DocumentCenter?{qs}", f"/DocumentCenter/Home?{qs}"]:
    try:
        h=op.open(f"https://{HOST}{path}",timeout=40).read().decode("utf-8","replace")
        vids=sorted(set(int(x) for x in re.findall(r'documentID=(\d+)',h,re.I)))
        print(f"  GET {path[:40]} -> {len(h)}b docids={len(vids)} range {vids[:1]}..{vids[-1:]}")
    except Exception as e: print(f"  GET {path[:40]} -> {e}")
