import json, re, sys, http.cookiejar, urllib.request
HOST=sys.argv[1] if len(sys.argv)>1 else "www.cityoflawrence.com"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); op.addheaders=[("User-Agent",UA)]
home=op.open(f"https://{HOST}/DocumentCenter",timeout=30).read().decode("utf-8","replace")
# all ids of various forms
print("View/{id}:", len(set(re.findall(r'/DocumentCenter/View/(\d+)',home))))
print("Index/{id} (folders):", sorted(set(int(x) for x in re.findall(r'/DocumentCenter/Index/(\d+)',home)))[:40])
print("documentID=:", len(set(re.findall(r'documentID=(\d+)',home,re.I))))
# embedded JSON tree? look for arrays with LoadOnDemand or ParentID or FolderID
for kw in ["LoadOnDemand","ParentID","FolderID","treeData","initialData","folderList","CategoryID"]:
    c=home.count(kw);
    if c: print(f"  home contains '{kw}' x{c}")
# find any large JSON-ish blob assigned in a <script>
for m in re.finditer(r'(\w+)\s*[:=]\s*(\[\{.{0,80})', home):
    print("  assign:", m.group(1), "=", m.group(2)[:80])
# the folder tree checkboxes: chkCategoryID like AgendaCenter? or data-id
print("\ndata-id attrs:", sorted(set(re.findall(r'data-(?:folder|id|node)\w*="(\d+)"',home)))[:20])
print("li/ul id folders:", sorted(set(re.findall(r'id="(?:node|folder|cat)(\d+)"',home)))[:20])
# dump the tree container HTML
m=re.search(r'(<ul[^>]*(?:tree|folder)[^>]*>.{0,600})',home,re.I)
if m: print("\ntree ul:", re.sub(r'\s+',' ',m.group(1))[:500])
# Any inline script var with folders
for m in re.finditer(r'<script[^>]*>([^<]{0,4000})</script>', home):
    s=m.group(1)
    if "folder" in s.lower() and ("[" in s or "{" in s):
        print("\ninline script w/ folder:", re.sub(r'\s+',' ',s)[:600]); break
