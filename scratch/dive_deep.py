"""Deep-dig pass: for town-years still NO_RESULTS / FETCH_FAIL / MAYBE, gather a MUCH broader
candidate set from the corpus (all town/annual reports any-year + clerk/election/warrant/
town-meeting/results files year+/-1 + election pages) and fetch untried ones, with a browser
cookie-lift fallback for WAF. Updates dive_results.csv (best verdict wins)."""
import csv, json, re, ssl, sys, time, urllib.request, urllib.parse
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import norm_host
import fitz

HERE = Path(__file__).resolve().parent
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
def norm(s): return re.sub(r"[^a-z]", "", s.lower())

# host->town for attribution
host2town = {}
for r in csv.DictReader(open(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\sources\towns_websites.csv", encoding="utf-8")):
    w=(r["Website"] or "").strip().lower()
    if w: host2town[norm_host(re.sub(r"^https?://","",w).strip("/").split("/")[0])]=norm(r["Municipality"])
for h,t in {"pelhamma.gov":"Pelham","townofpetersham.gov":"Petersham","pittsfieldma.gov":"Pittsfield",
            "norwoodma.gov":"Norwood","weymouth.ma.us":"Weymouth","northandoverma.gov":"North Andover",
            "wbrookfield.com":"West Brookfield","townofsavoy.com":"Savoy","goshen-ma.us":"Goshen",
            "gosnold-ma.gov":"Gosnold","harwich-ma.gov":"Harwich","townofsouthampton.org":"Southampton",
            "townofwestspringfield.org":"West Springfield"}.items():
    host2town[h]=norm(t)

prev = {(r["municipality"], r["year"]): r for r in csv.DictReader(open(HERE/"dive_results.csv", encoding="utf-8"))}
targets = {k for k, v in prev.items() if v["verdict"] in ("NO_RESULTS", "FETCH_FAIL", "MAYBE")}
tgt_towns = {norm(t) for t, _ in targets}
print(f"deep-dig targets: {len(targets)} town-years across {len(tgt_towns)} towns")

# broad candidate gather
REPORT = re.compile(r"annual.?(town.?)?report|town.?report", re.I)
ACFR = re.compile(r"\bacfr\b|comprehensive.?annual|audited.?financial", re.I)
DOCY = re.compile(r"election|result|canvass|warrant|town.?meeting|clerk|\bate\b|town.?election|tally|precinct", re.I)
ELPAGE = re.compile(r"/elections?|election|voting|town.?clerk|/results?", re.I)
cand = defaultdict(list)
NODES = Path(__file__).resolve().parents[1]/"data/discover/nodes.jsonl"
for line in NODES.open(encoding="utf-8"):
    try: r = json.loads(line)
    except Exception: continue
    t = norm(r.get("municipality") or "") or host2town.get(norm_host(r.get("seed_host","")), "")
    if t not in tgt_towns: continue
    u = r["url"]; hay = u + " " + (r.get("anchor") or ""); low = hay.lower()
    isfile = r.get("kind") == "file"
    yrs = set(int(y) for y in re.findall(r"(20[12]\d)", hay))
    if isfile and REPORT.search(low) and not ACFR.search(low):
        for Y in range(2021, 2026):
            if not yrs or Y in yrs or (Y-1) in yrs:      # report yr ~ election yr
                cand[(t, str(Y))].append((1, "annual_report", u))
    if isfile and DOCY.search(low):
        for Y in yrs:
            if 2021 <= Y <= 2025: cand[(t, str(Y))].append((2, "election_doc", u))
    if not isfile and ELPAGE.search(low):
        for Y in range(2021, 2026): cand[(t, str(Y))].append((3, "election_page", u))

HEADING = re.compile(r"annual town election|town election|local election|municipal election|election results", re.I)
BLANKS = re.compile(r"\bblanks?\b", re.I)
OFFICE = re.compile(r"selectman|select board|moderator|town clerk|assessor|school committee|board of health|constable|treasurer|library trustee", re.I)
TALLY = re.compile(r"[A-Za-z][A-Za-z.\-' ]{3,40}\s+\d{1,5}\b")
def enc(u):
    p = urllib.parse.urlsplit(u); return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(p.path),urllib.parse.quote(p.query,safe="=&?"),""))
def textify(raw, u):
    if raw[:4]==b"%PDF" or u.lower().endswith(".pdf"):
        d=fitz.open(stream=raw,filetype="pdf"); return "".join(d[i].get_text() for i in range(min(len(d),300)))
    tx=raw.decode("utf-8","replace"); tx=re.sub(r"(?is)<(script|style).*?</\1>"," ",tx); return re.sub(r"<[^>]+>"," ",tx)
_sess={}
def fetch(u):
    uu=enc(u)
    if "drive.google.com" in uu:
        m=re.search(r"[-\w]{25,}",u); uu=f"https://drive.google.com/uc?export=download&id={m.group(0)}" if m else uu
    try:
        raw=urllib.request.urlopen(urllib.request.Request(uu,headers=UA),timeout=35,context=ctx).read(30_000_000)
    except urllib.error.HTTPError as e:
        if e.code in (403,406,429,503):
            from muni_harvest.fetchers.waf_session import mint_session
            h=urllib.parse.urlsplit(uu).netloc
            if h not in _sess: _sess[h]=mint_session(f"https://{h}/") or None
            if not _sess[h]: raise
            raw=_sess[h].get(uu,timeout=35,verify=False).content
        else: raise
    return textify(raw,u)
def score(text):
    heads=len(HEADING.findall(text)); blanks=len(BLANKS.findall(text)); offices=len(set(OFFICE.findall(text.lower()))); tallies=len(TALLY.findall(text))
    strong=heads>=1 and (blanks>=2 or (offices>=3 and tallies>=8))
    return ("RESULTS_FOUND" if strong else "MAYBE" if (heads>=1 and (blanks>=1 or offices>=2)) else "NO_RESULTS"), f"heads={heads},blanks={blanks},offices={offices},tallies={tallies}"

rank={"NO_CANDIDATE":0,"FETCH_FAIL":1,"NO_RESULTS":2,"MAYBE":3,"RESULTS_FOUND":4}
upgraded=0
for (t,y) in sorted(targets):
    tn=norm(t)
    cs=sorted(set(cand.get((tn,y),[])), key=lambda x:x[0])[:8]
    cur=prev[(t,y)]; best=(cur["verdict"],cur["signals"],cur["url"],cur["kind"])
    tried={cur["url"]}
    for pr,kind,u in cs:
        if u in tried: continue
        tried.add(u)
        try: v,s=score(fetch(u))
        except Exception as e: v,s=("FETCH_FAIL",type(e).__name__)
        if rank[v]>rank[best[0]]: best=(v,s,u,kind)
        if v=="RESULTS_FOUND": break
        time.sleep(0.25)
    if rank[best[0]]>rank[cur["verdict"]]:
        upgraded+=1; print(f"  UP {t} {y}: {cur['verdict']} -> {best[0]}  [{best[1]}]",flush=True)
    prev[(t,y)]={"municipality":t,"year":y,"verdict":best[0],"signals":best[1],"url":best[2],"kind":best[3]}

with (HERE/"dive_results.csv").open("w",encoding="utf-8",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["municipality","year","verdict","signals","url","kind"]); w.writeheader()
    for k in sorted(prev): w.writerow(prev[k])
from collections import Counter
print(f"\nupgraded {upgraded} town-years. final:", dict(Counter(v['verdict'] for v in prev.values())))
