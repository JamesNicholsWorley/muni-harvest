"""Per-board agenda-only breakdown from the LIVE AgendaCenter — which boards drive the
missing-minutes gap? (Hypothesis: Select Board is near-complete; minor committees aren't.)"""
import re, ssl, sys, urllib.request
HOST=sys.argv[1] if len(sys.argv)>1 else "concordma.gov"
UA="Mozilla/5.0 (research; polite)"
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
def get(u): return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":UA}),timeout=40,context=ctx).read().decode("utf-8","replace")
html=get(f"https://{HOST}/AgendaCenter")
CID=re.compile(r'name="chkCategoryID"\s+value="(\d+)"[^>]*>\s*([^<]{2,70})')
cid_label={c:re.sub(r"\s+"," ",l).strip() for c,l in CID.findall(html)}
WALK=re.compile(r'id="cat(\d+)"|/AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{8})-(\d+)',re.I)
cur=None
from collections import defaultdict
ag=defaultdict(dict); mn=defaultdict(set)
for m in WALK.finditer(html):
    if m.group(1): cur=m.group(1)
    else:
        typ,date,mid=m.group(2).lower(),m.group(3),m.group(4)
        # only settled years
        if date[-4:] not in ("2020","2021","2022","2023","2024"): continue
        if typ=="agenda": ag[cur][mid]=date
        else: mn[cur].add(mid)
rows=[]
for c,label in cid_label.items():
    a=ag[c]; m=mn[c]
    both=len([1 for i in a if i in m]); aonly=len([1 for i in a if i not in m])
    if a or m: rows.append((label,len(a),len(m),both,aonly))
rows.sort(key=lambda r:-r[4])
print(f"{HOST} — per-board (2020-24 settled meetings), sorted by agenda-only gap:")
print(f"  {'board':<44}{'ag':>5}{'min':>5}{'both':>6}{'ag_only':>8}")
tot_a=tot_ao=0
for label,a,m,both,aonly in rows:
    print(f"  {label[:44]:<44}{a:>5}{m:>5}{both:>6}{aonly:>8}")
    tot_a+=a; tot_ao+=aonly
print(f"  {'TOTAL':<44}{tot_a:>5}{'':>5}{'':>6}{tot_ao:>8}  ({tot_ao/tot_a:.0%} agenda-only)")
