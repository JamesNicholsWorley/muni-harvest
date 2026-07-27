"""Reverse-engineer the REAL per-folder document listing. The tree (_AjaxLoadingReact
type=1) under-returns docs. Inspect /DocumentCenter/Index/{fid} HTML + find the AJAX
endpoint the React app uses to list a folder's documents (with the high ids)."""
from __future__ import annotations
import json, re, sys, http.cookiejar, urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "www.cityoflawrence.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36")
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders=[("User-Agent",UA)]
op.open(f"https://{HOST}/DocumentCenter",timeout=30).read()
tok=json.loads(op.open(f"https://{HOST}/antiforgery",timeout=30).read().decode()).get("token")

def get(path):
    try: return op.open(f"https://{HOST}{path}",timeout=30).read().decode("utf-8","replace")
    except Exception as e: return f"__ERR__{e}"
def post(path,body,ctype="application/json"):
    data = json.dumps(body).encode() if ctype=="application/json" else urllib.parse.urlencode(body).encode()
    req=urllib.request.Request(f"https://{HOST}{path}",data=data,method="POST",
        headers={"User-Agent":UA,"Content-Type":ctype,"RequestVerificationToken":tok,
                 "X-Requested-With":"XMLHttpRequest"})
    try: return op.open(req,timeout=30).read().decode("utf-8","replace")
    except Exception as e: return f"__ERR__{e}"
import urllib.parse

# 1. Root index HTML — find document ids + folder ids + any data-* attrs + JS endpoints
html = get("/DocumentCenter/Index/1")
print(f"/DocumentCenter/Index/1 -> {len(html)}b")
docids = sorted(set(int(x) for x in re.findall(r'/DocumentCenter/View/(\d+)', html)), )
viewids = sorted(set(int(x) for x in re.findall(r'documentID["\']?[=:]\s*["\']?(\d+)', html)))
folderids = sorted(set(int(x) for x in re.findall(r'/DocumentCenter/Index/(\d+)', html)))
print(f"  View/{{id}} links: {len(docids)}  range {docids[:1]}..{docids[-1:]}" )
print(f"  documentID refs: {len(viewids)}  range {viewids[:1]}..{viewids[-1:]}")
print(f"  Index/{{folder}} links: {len(folderids)}  e.g. {folderids[:15]}")
# endpoints referenced in the html/js
eps = sorted(set(re.findall(r'(/[A-Za-z0-9_/]*DocumentCenter[A-Za-z0-9_/]*)', html)))
print("  DocumentCenter endpoints in page:")
for e in eps[:25]: print("     ", e)
# look for AJAX urls (Home/xxx)
homeeps = sorted(set(re.findall(r'(/admin/DocumentCenter/Home/[A-Za-z0-9_]+)', html)))
print("  Home/* AJAX endpoints:", homeeps)

# 2. Try the folder-documents endpoints with a high-id folder if any
print("\nProbing folder-doc endpoints (looking for high ids ~40000-55000):")
for fid in (folderids[:1] or [1]):
    for path, body, ct in [
        ("/admin/DocumentCenter/Home/_AjaxLoadingDocuments", {"folderId":fid,"selectedFolder":fid,"page":1,"pageSize":500}, "application/json"),
        ("/admin/DocumentCenter/Home/GetFolderDocuments", {"folderId":fid}, "application/json"),
        ("/admin/DocumentCenter/Home/DocumentsList", {"folderId":fid,"page":1,"pageSize":500}, "application/json"),
        ("/admin/DocumentCenter/Home/_AjaxLoadingReact?type=2", {"value":str(fid),"selectedFolder":fid,"loadSource":7}, "application/json"),
    ]:
        r=post(path,body,ct)
        ids=re.findall(r'"(?:documentID|Value|DocumentID|Id)"\s*:\s*(\d+)', r)
        print(f"   {path[:55]:<55} -> {len(r)}b ids={len(ids)} {r[:70]!r}")

# 3. Does View/{highid} resolve (302 -> ImageRepository)? confirms high ids are real docs
for tid in ("51303","44049"):
    try:
        req=urllib.request.Request(f"https://{HOST}/DocumentCenter/View/{tid}",headers={"User-Agent":UA})
        resp=op.open(req,timeout=30)
        print(f"\nView/{tid}: HTTP {resp.status}  final={resp.geturl()[:80]}  ctype={resp.headers.get('Content-Type','')[:30]}")
    except Exception as e:
        print(f"\nView/{tid}: {e}")
