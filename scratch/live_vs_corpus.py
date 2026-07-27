"""Decisive: take the LIVE AgendaCenter minutes URLs for a town and check how many are
in our corpus. High miss => we failed to capture minutes the town clearly publishes."""
from __future__ import annotations
import re, ssl, sys, json, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import urlkey, norm_host

HOST = sys.argv[1] if len(sys.argv) > 1 else "concordma.gov"
NODES = Path(__file__).resolve().parents[1] / "data/discover/nodes.jsonl"

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
req = urllib.request.Request(f"https://{HOST}/AgendaCenter", headers={"User-Agent":"Mozilla/5.0 (research)"})
html = urllib.request.urlopen(req, timeout=40, context=ctx).read().decode("utf-8","replace")

VF = re.compile(r'/AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{8})-(\d+)', re.I)
live_min, live_ag = set(), set()
for typ, date, mid in VF.findall(html):
    u = f"https://{HOST}/AgendaCenter/ViewFile/{typ}/_{date}-{mid}"
    (live_min if typ.lower()=="minutes" else live_ag).add(urlkey(u))
print(f"LIVE {HOST}: {len(live_ag)} agenda URLs, {len(live_min)} minutes URLs")

# build corpus urlkey set for this host (any AgendaCenter ViewFile)
nb = norm_host(HOST)
corp = set()
corp_min = corp_ag = 0
for line in NODES.open(encoding="utf-8"):
    if "/AgendaCenter/ViewFile/" not in line: continue
    if nb not in line: continue
    try: rec = json.loads(line)
    except Exception: continue
    u = rec.get("url","")
    if norm_host(re.match(r"https?://([^/]+)",u).group(1)) != nb: continue
    k = urlkey(u); corp.add(k)
    if "/Minutes/" in u or "/minutes/" in u.lower(): corp_min+=1
    else: corp_ag+=1
print(f"CORPUS {HOST}: {corp_ag} agenda nodes, {corp_min} minutes nodes ({len(corp)} unique AC urlkeys)")

min_in = sum(1 for k in live_min if k in corp)
ag_in  = sum(1 for k in live_ag if k in corp)
print(f"\nLIVE minutes URLs present in corpus: {min_in}/{len(live_min)} = {min_in/max(len(live_min),1):.0%}")
print(f"LIVE agenda  URLs present in corpus: {ag_in}/{len(live_ag)} = {ag_in/max(len(live_ag),1):.0%}")
print(f"\n=> {len(live_min)-min_in} minutes the town publishes RIGHT NOW are NOT in our corpus")
# show a few missed live minutes
missed = [k for k in live_min if k not in corp][:10]
print("sample missed live minutes urlkeys:")
for k in missed: print("   ", k)
