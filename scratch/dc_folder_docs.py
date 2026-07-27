"""Test the fix: walk folders via type=1 (structure), fetch each folder's DOCUMENTS via
type=2. Does this surface the high ids (51303) the old walk missed?"""
from __future__ import annotations
import json, re, sys, http.cookiejar, urllib.request
from collections import Counter

HOST = sys.argv[1] if len(sys.argv) > 1 else "www.cityoflawrence.com"
TARGET = sys.argv[2] if len(sys.argv) > 2 else "51303"
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders=[("User-Agent",UA)]
op.open(f"https://{HOST}/DocumentCenter",timeout=30).read()
tok=json.loads(op.open(f"https://{HOST}/antiforgery",timeout=30).read().decode()).get("token")

def call(fid,typ):
    body=json.dumps({"value":str(fid),"expandTree":False,"loadSource":7,"selectedFolder":int(fid)}).encode()
    req=urllib.request.Request(f"https://{HOST}/admin/DocumentCenter/Home/_AjaxLoadingReact?type={typ}",
        data=body,method="POST",headers={"User-Agent":UA,"Content-Type":"application/json",
        "RequestVerificationToken":tok,"X-Requested-With":"XMLHttpRequest"})
    try: return json.loads(op.open(req,timeout=30).read().decode("utf-8","replace")).get("Data",[]) or []
    except Exception as e: return []

# 1. collect ALL folder ids by walking type=1 (folders only)
folders={"1"}; stack=["1"]; seen=set()
while stack:
    fid=stack.pop()
    if fid in seen: continue
    seen.add(fid)
    for n in call(fid,1):
        if n.get("LoadOnDemand"):
            v=str(n.get("Value") or "")
            if v and v not in folders: folders.add(v); stack.append(v)
print(f"folders discovered (type=1 walk): {len(folders)}")

# 2. for each folder, list DOCUMENTS via type=2
docs_t2={}; docs_t1={}
for fid in folders:
    for n in call(fid,2):
        v=str(n.get("Value") or "")
        if not n.get("LoadOnDemand") and v.isdigit(): docs_t2[v]=(fid,n.get("Text",""))
    for n in call(fid,1):
        v=str(n.get("Value") or "")
        if not n.get("LoadOnDemand") and v.isdigit(): docs_t1[v]=(fid,n.get("Text",""))

def rng(d):
    ids=[int(x) for x in d]; return f"{min(ids) if ids else 0}..{max(ids) if ids else 0}"
print(f"documents via type=1 (old method): {len(docs_t1)}  range {rng(docs_t1)}")
print(f"documents via type=2 (new method): {len(docs_t2)}  range {rng(docs_t2)}")
union=set(docs_t1)|set(docs_t2)
print(f"UNION: {len(union)}  range {rng({k:1 for k in union})}")
print(f"target {TARGET} found? type1={'Y' if TARGET in docs_t1 else 'N'} type2={'Y' if TARGET in docs_t2 else 'N'}")
if TARGET in docs_t2: print("   ->", docs_t2[TARGET])
# how many folders actually yielded docs via type2 vs type1
