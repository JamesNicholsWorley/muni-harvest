"""Empirically probe a live CivicPlus DocumentCenter to find WHY the tree walk misses
in-range documents (e.g. Lawrence id 51303). Walk the tree, count docs/folders, look for
the target id, and test whether GetDocumentsForAFolder / paging reveals more."""
from __future__ import annotations
import json, sys, http.cookiejar, urllib.request
from collections import Counter

HOST = sys.argv[1] if len(sys.argv) > 1 else "www.cityoflawrence.com"
TARGET = sys.argv[2] if len(sys.argv) > 2 else "51303"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36")

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", UA)]
op.open(f"https://{HOST}/DocumentCenter", timeout=30).read()
tok = json.loads(op.open(f"https://{HOST}/antiforgery", timeout=30).read().decode()).get("token")
print(f"session token: {str(tok)[:20]}...")

def post(path, body):
    req = urllib.request.Request(f"https://{HOST}{path}", data=json.dumps(body).encode(),
        method="POST", headers={"User-Agent":UA,"Content-Type":"application/json",
        "RequestVerificationToken":tok,"X-Requested-With":"XMLHttpRequest"})
    try:
        return op.open(req, timeout=30).read().decode("utf-8","replace")
    except Exception as e:
        return f"__ERR__{type(e).__name__}:{e}"

def children(fid):
    raw = post("/admin/DocumentCenter/Home/_AjaxLoadingReact?type=1",
               {"value":str(fid),"expandTree":False,"loadSource":7,"selectedFolder":int(fid)})
    if raw.startswith("__ERR__"): return None, raw
    try: return json.loads(raw).get("Data",[]) or [], None
    except Exception: return None, raw[:200]

# Full tree walk with diagnostics
stack=[("1",[])]; seen=set(); docs={}; folders=0; empty_folders=[]; errors=0
maxnodes=200000
while stack and len(docs)<maxnodes:
    fid,path=stack.pop()
    if fid in seen: continue
    seen.add(fid); folders+=1
    ch,err=children(fid)
    if err: errors+=1; continue
    nfold=ndoc=0
    for n in ch:
        val=str(n.get("Value") or ""); text=(n.get("Text") or "").strip()
        if n.get("LoadOnDemand"): stack.append((val,path+[text])); nfold+=1
        elif val.isdigit(): docs[val]={"title":text,"path":" / ".join(path)}; ndoc+=1
    if nfold==0 and ndoc==0:
        empty_folders.append((fid," / ".join(path)))
print(f"\nTREE WALK: {folders} folders visited, {len(docs)} documents, {errors} errors, {len(empty_folders)} empty folders")
print(f"target id {TARGET} in tree docs? {'YES' if TARGET in docs else 'NO'}")
if TARGET in docs: print("   ->", docs[TARGET])
mx=max((int(d) for d in docs), default=0); mn=min((int(d) for d in docs), default=0)
print(f"doc id range found: {mn}..{mx}   (target {TARGET} {'IN' if mn<=int(TARGET)<=mx else 'OUT of'} range)")

# Show a few 'empty' folders — these are the suspects (docs hidden behind GetDocumentsForAFolder)
print(f"\nSample folders that returned NO children via tree (candidates for hidden docs):")
for fid,p in empty_folders[:10]:
    print(f"   folder {fid}: {p}")

# Try alternate endpoints on an empty folder to see if docs are hidden
if empty_folders:
    fid,p=empty_folders[0]
    print(f"\nProbing hidden-doc endpoints on empty folder {fid} ({p}):")
    for path,body in [
        ("/admin/DocumentCenter/Home/GetDocumentsForAFolder", {"folderId":int(fid),"selectedFolder":int(fid)}),
        (f"/DocumentCenter/Index/{fid}", None),
        ("/admin/DocumentCenter/Home/_AjaxLoadingReact?type=0", {"value":str(fid),"selectedFolder":int(fid),"loadSource":7}),
    ]:
        if body is None:
            try: r=op.open(f"https://{HOST}{path}",timeout=30).read().decode("utf-8","replace")
            except Exception as e: r=f"__ERR__{e}"
        else:
            r=post(path,body)
        marker = "ImageRepository" in r or "documentID" in r or "\"Data\"" in r
        print(f"   {path[:60]:<60} -> {len(r)}b  docs_marker={marker}  {r[:80]!r}")
