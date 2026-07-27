"""Decisive minutes test: for OLD agenda-only meetings, probe BOTH agenda and minutes
URL (same id). agenda=200 & minutes=404 => minutes genuinely never posted. both 404 =>
meeting aged out (inconclusive). minutes=200 => we missed existing minutes."""
from __future__ import annotations
import re, ssl, sys, json, time, urllib.request, urllib.error
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

TOWNS = sys.argv[1:] or ["concordma.gov","hingham-ma.gov","natickma.gov"]
NODES = Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl"
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA={"User-Agent":"Mozilla/5.0 (research; polite)"}
AC = re.compile(r"/AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{8})-(\d+)", re.I)

def load(host):
    ag,mn={},set()
    key=host.split(".")[0]
    for line in NODES.open(encoding="utf-8"):
        if "/AgendaCenter/ViewFile/" not in line or key not in line: continue
        try: rec=json.loads(line)
        except: continue
        u=rec.get("url","")
        if host not in u: continue
        m=AC.search(u)
        if not m: continue
        t,d,i=m.group(1).lower(),m.group(2),m.group(3)
        if t=="agenda": ag[i]=d
        else: mn.add(i)
    return ag,mn

def head(url):
    try:
        req=urllib.request.Request(url,headers=UA)
        with urllib.request.urlopen(req,timeout=20,context=ctx) as r:
            ct=r.headers.get("Content-Type","");ln=len(r.read(1500))
            return 200 if ("pdf" in ct.lower() or ln>1200) else 204
    except urllib.error.HTTPError as e: return e.code
    except Exception: return 0

for host in TOWNS:
    ag,mn=load(host)
    agold=[(i,d) for i,d in ag.items() if i not in mn and d[-4:] in ("2019","2020","2021")]
    agold.sort(key=lambda x:x[1][-4:])
    step=max(1,len(agold)//18); sample=[agold[i] for i in range(0,len(agold),step)][:18]
    c=Counter()
    for i,d in sample:
        a=head(f"https://{host}/AgendaCenter/ViewFile/Agenda/_{d}-{i}")
        m=head(f"https://{host}/AgendaCenter/ViewFile/Minutes/_{d}-{i}")
        if a==200 and m==200: c["BOTH exist (we missed minutes)"]+=1
        elif a==200 and m!=200: c["agenda live, minutes 404 (never posted)"]+=1
        elif a!=200 and m==200: c["minutes live, agenda gone"]+=1
        else: c["both gone (aged out - inconclusive)"]+=1
        time.sleep(0.3)
    print(f"\n### {host} — {len(sample)} old agenda-only meetings probed (of {len(agold)})")
    for k,v in c.most_common(): print(f"    {v:>3}  {k}")
