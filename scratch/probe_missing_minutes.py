"""Decisive test for 'agendas missing minutes': for AgendaCenter meetings that have an
agenda but NO minutes in our corpus, construct the exact Minutes ViewFile URL (same
date+id) and probe the LIVE site. 200 => minutes exist on-site, we MISSED them (Wayback
gap). 404 => minutes were never posted (real town behavior)."""
from __future__ import annotations
import json, re, sys, time, urllib.request, urllib.error, ssl
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

NODES = Path(__file__).resolve().parents[1] / "data" / "discover" / "nodes.jsonl"
AC = re.compile(r"/AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{8})-(\d+)", re.I)

TOWNS = sys.argv[1:] or ["Concord", "Hingham", "Winchester", "Natick"]
TOWNSET = set(TOWNS)

# collect per town: agenda meetings (id->(host,date)), minutes ids
ag = defaultdict(dict)     # town -> {id: (host, mmddyyyy)}
mn = defaultdict(set)      # town -> {id}
for line in NODES.open(encoding="utf-8"):
    try: rec = json.loads(line)
    except Exception: continue
    if rec.get("kind") != "file": continue
    town = rec.get("municipality") or ""
    if town not in TOWNSET: continue
    m = AC.search(rec["url"])
    if not m: continue
    host = re.sub(r"^https?://", "", rec["url"]).split("/")[0]
    kind, date, mid = m.group(1).lower(), m.group(2), m.group(3)
    if kind == "agenda": ag[town][mid] = (host, date)
    else: mn[town].add(mid)

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {"User-Agent":"Mozilla/5.0 (research; polite probe)"}

def probe(url):
    try:
        req = urllib.request.Request(url, headers=UA, method="GET")
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            ct = r.headers.get("Content-Type","")
            body = r.read(4000)
            return r.status, len(body), ct
    except urllib.error.HTTPError as e:
        return e.code, 0, ""
    except Exception as e:
        return f"ERR:{type(e).__name__}", 0, ""

SAMPLE = 30
for town in TOWNS:
    agonly = [(mid, ag[town][mid]) for mid in ag[town] if mid not in mn[town]]
    # OLD meetings only (2019-2023): minutes, if ever posted, are certainly up by now.
    agonly = [x for x in agonly if x[1][1][-4:] in ("2019","2020","2021","2022","2023")]
    # spread the sample across years/months to avoid Jan-organizational-meeting bias
    agonly.sort(key=lambda x: (x[1][1][-4:], x[1][1][:4]))
    if len(agonly) > SAMPLE:
        step = len(agonly) / SAMPLE
        sample = [agonly[int(i*step)] for i in range(SAMPLE)]
    else:
        sample = agonly
    if not sample:
        print(f"\n### {town}: no agenda-only meetings"); continue
    host = sample[0][1][0]
    exist = notfound = other = 0
    details=[]
    for mid,(host,date) in sample:
        url = f"https://{host}/AgendaCenter/ViewFile/Minutes/_{date}-{mid}"
        st, n, ct = probe(url)
        ispdf = ("pdf" in ct.lower()) or n>1500
        if st==200 and ispdf: exist+=1; tag="EXISTS"
        elif st==200: exist+=1; tag=f"200({ct[:20]},{n}b)"
        elif st in (404,) : notfound+=1; tag="404"
        else: other+=1; tag=str(st)
        details.append((date,mid,tag))
        time.sleep(0.4)
    print(f"\n### {town} ({host}) — probed {len(sample)} agenda-only meetings (of {len(agonly)} total agenda-only)")
    print(f"   Minutes URL EXISTS live: {exist}   404 (never posted): {notfound}   other: {other}")
    for d,mid,tag in details[:12]:
        print(f"     {d[-4:]}-{d[:2]}/{d[2:4]}  id{mid:<6} -> {tag}")
