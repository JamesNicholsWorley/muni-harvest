"""Find the true DocumentCenter API/root. Inspect /DocumentCenter page bootstrap + JS,
and locate which folder id 51303 lives in by trying the classic non-React listing."""
from __future__ import annotations
import json, re, sys, http.cookiejar, urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "www.cityoflawrence.com"
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders=[("User-Agent",UA)]
def get(path):
    try:
        r=op.open(f"https://{HOST}{path}",timeout=30); return r.read().decode("utf-8","replace"), r.geturl()
    except Exception as e: return f"__ERR__{e}",""

home,_=get("/DocumentCenter")
print(f"/DocumentCenter -> {len(home)}b")
# bootstrap json / config
for pat in [r'rootFolder\w*"?\s*[:=]\s*"?(\d+)', r'"FolderId"\s*:\s*(\d+)',
            r'selectedFolder"?\s*[:=]\s*"?(\d+)', r'data-folder-?id="(\d+)"',
            r'defaultFolder\w*"?\s*[:=]\s*"?(\d+)']:
    m=re.findall(pat,home)
    if m: print(f"  {pat[:30]:<32} -> {m[:8]}")
# all api-ish endpoints in the page + linked JS
eps=sorted(set(re.findall(r'"(/[A-Za-z0-9_./-]*?(?:Document|Folder|Repository|ajax|Ajax)[A-Za-z0-9_./-]*)"',home)))
print("  endpoints referenced:")
for e in eps[:30]: print("     ",e)
# linked JS bundles
js=re.findall(r'src="([^"]+\.js[^"]*)"',home)
print(f"  {len(js)} js bundles; sample:", js[:5])

# classic (non-react) folder listing often at /DocumentCenter/Index/{fid} or /documentcenterii
for path in ["/DocumentCenterii","/DocumentCenter/Index","/documentcenter","/DocumentCenter/Home"]:
    h,u=get(path); print(f"  {path} -> {len(h) if not h.startswith('__ERR__') else h[:40]}b final={u[-50:]}")

# Try to locate folder of 51303 via View page meta / breadcrumb
v,u=get("/DocumentCenter/View/51303")
# View returns the pdf; instead try the 'Index' with a search
# CivicPlus has a search: /DocumentCenter/Home/Search?searchPhrase=
for path in ["/admin/DocumentCenter/Home/Search?searchPhrase=results",
             "/DocumentCenter/Home/Index"]:
    h,u=get(path); print(f"  {path} -> {(len(h) if not h.startswith('__ERR__') else h[:50])}")

# Dump a slice of home around 'folder' to eyeball the bootstrap
idx=home.lower().find("folder")
print("\n--- home slice around first 'folder' ---")
print(home[max(0,idx-200):idx+400])
