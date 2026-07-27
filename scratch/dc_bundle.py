import json,re,sys,http.cookiejar,urllib.request
HOST=sys.argv[1] if len(sys.argv)>1 else "www.cityoflawrence.com"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); op.addheaders=[("User-Agent",UA)]
op.open(f"https://{HOST}/DocumentCenter",timeout=30).read()
tok=json.loads(op.open(f"https://{HOST}/antiforgery",timeout=30).read().decode()).get("token")
js=op.open(f"https://{HOST}/Areas/DocumentCenter/Assets/Scripts/docCenterFrontendAndRelatedBidAndJobsApp.react.js",timeout=60).read().decode("utf-8","replace")
print(f"bundle {len(js)}b")
# any /admin/DocumentCenter/... or /DocumentCenter/... path literals
eps=sorted(set(re.findall(r'["\'`](/[A-Za-z0-9][A-Za-z0-9_/.-]*(?:DocumentCenter|ImageRepository|Document|Folder)[A-Za-z0-9_/.-]*)["\'`]',js)))
print(f"path literals ({len(eps)}):")
for e in eps: print("   ",e)
# fetch/ajax url building near 'AjaxLoadingReact'
i=js.find("AjaxLoadingReact")
print("\naround AjaxLoadingReact:", js[max(0,i-120):i+120] if i>0 else "n/a")
# 'type=' usages
print("\ntype= usages:", sorted(set(re.findall(r'AjaxLoadingReact\?type=(\d+)',js))))
print("loadSource usages:", sorted(set(re.findall(r'loadSource["\']?\s*[:=]\s*(\d+)',js)))[:10])

def post(path,body):
    req=urllib.request.Request(f"https://{HOST}{path}",data=json.dumps(body).encode(),method="POST",
        headers={"User-Agent":UA,"Content-Type":"application/json","RequestVerificationToken":tok,"X-Requested-With":"XMLHttpRequest"})
    try: return op.open(req,timeout=40).read().decode("utf-8","replace")
    except Exception as e: return f"__ERR__{e}"
def get(path):
    try: return op.open(f"https://{HOST}{path}",timeout=40).read().decode("utf-8","replace")
    except Exception as e: return f"__ERR__{e}"

print("\n/DocumentCenter/Archived ->", get("/DocumentCenter/Archived")[:120])
# FolderHeaderForReact for a folder gives folder metadata incl maybe doc count
print("FolderHeaderForReact(1) ->", post("/admin/DocumentCenter/Folder/FolderHeaderForReact",{"folderId":1,"selectedFolder":1})[:200])
