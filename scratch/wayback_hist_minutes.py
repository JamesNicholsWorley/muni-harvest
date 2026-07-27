"""For OLD agenda-only meetings, ask Wayback CDX whether the Minutes URL was EVER
archived. Snapshot exists => minutes existed, we missed it. No snapshot + agenda has one
=> minutes likely never posted."""
from __future__ import annotations
import re, ssl, sys, json, time, urllib.request, urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

HOST = sys.argv[1] if len(sys.argv) > 1 else "concordma.gov"
NODES = Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl"
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

AC = re.compile(r"/AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{8})-(\d+)", re.I)
ag, mn = {}, set()
for line in NODES.open(encoding="utf-8"):
    if "/AgendaCenter/ViewFile/" not in line or HOST.split(".")[0] not in line: continue
    try: rec = json.loads(line)
    except Exception: continue
    u = rec.get("url","")
    if HOST not in u: continue
    m = AC.search(u)
    if not m: continue
    typ, date, mid = m.group(1).lower(), m.group(2), m.group(3)
    if typ=="agenda": ag[mid]=date
    else: mn.add(mid)
# old agenda-only (2018-2021)
agold = [(mid,d) for mid,d in ag.items() if mid not in mn and d[-4:] in ("2018","2019","2020","2021")]
agold.sort(key=lambda x:x[1][-4:])
step=max(1,len(agold)//20); sample=[agold[i] for i in range(0,len(agold),step)][:20]
print(f"{HOST}: {len(ag)} agendas, {len(mn)} minutes in corpus; old agenda-only 2018-21: {len(agold)}")

def cdx(url):
    q = "https://web.archive.org/cdx/search/cdx?url=" + urllib.parse.quote(url,safe="") + "&output=json&limit=3"
    try:
        req=urllib.request.Request(q, headers={"User-Agent":"Mozilla/5.0 (research)"})
        data=json.loads(urllib.request.urlopen(req,timeout=40,context=ctx).read().decode())
        return len(data)-1 if data else 0
    except Exception as e:
        return f"ERR:{type(e).__name__}"

exists=noarch=0
for mid,date in sample:
    murl=f"https://{HOST}/AgendaCenter/ViewFile/Minutes/_{date}-{mid}"
    n=cdx(murl)
    tag = f"{n} snapshots" if isinstance(n,int) and n>0 else ("NO archive" if n==0 else n)
    if isinstance(n,int) and n>0: exists+=1
    elif n==0: noarch+=1
    print(f"   {date[-4:]}-{date[:2]}-{date[2:4]} id{mid:<6} minutes -> {tag}")
    time.sleep(1.0)
print(f"\nold agenda-only minutes EVER archived by Wayback: {exists}/{len(sample)}  |  never archived: {noarch}/{len(sample)}")
