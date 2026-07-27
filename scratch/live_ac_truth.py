"""Ground truth: fetch a town's LIVE AgendaCenter page(s) and read how agendas &
minutes actually relate, per board (category). No Wayback, no URL-guessing — parse
what the town actually publishes right now, including per-year views."""
from __future__ import annotations
import re, ssl, sys, time, urllib.request, urllib.error
from collections import defaultdict

HOST = sys.argv[1] if len(sys.argv) > 1 else "concordma.gov"
YEARS = sys.argv[2:] or ["2023", "2024"]

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {"User-Agent":"Mozilla/5.0 (research; polite)"}

def get(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
            return r.read().decode("utf-8", "replace"), r.status
    except urllib.error.HTTPError as e:
        return "", e.code
    except Exception as e:
        return "", str(e)

# category legend: chkCategoryID value + label
CID_LABEL = re.compile(r'name="chkCategoryID"\s+value="(\d+)"[^>]*>\s*([^<]{2,70})')
# section markers id="catN" and ViewFile links
WALK = re.compile(r'id="cat(\d+)"|/AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{8})-(\d+)', re.I)

# First fetch the base page to get the category legend (board names).
base, st = get(f"https://{HOST}/AgendaCenter")
print(f"GET /AgendaCenter -> {st}, {len(base)} bytes")
cid_label = {cid: re.sub(r"\s+"," ",lbl).strip() for cid,lbl in CID_LABEL.findall(base)}
print(f"categories (boards) on live page: {len(cid_label)}")
for cid,lbl in list(cid_label.items())[:20]:
    print(f"   cat{cid}: {lbl}")

# AgendaCenter lets you request a year view via ?_MMDDYYYY... actually via changeArchiveYear;
# the full listing for a category+year is /AgendaCenter/Category/ViewFile ... but the base page
# already contains many rows. We'll also try the per-category "Previous Versions" by year param.
def analyze(html, tag):
    # meeting_id -> {board_cid, has_agenda, has_minutes}
    perid = defaultdict(lambda: {"cid": None, "a": False, "m": False, "date": None})
    cur = None
    for m in WALK.finditer(html):
        if m.group(1):
            cur = m.group(1)
        else:
            typ, date, mid = m.group(2).lower(), m.group(3), m.group(4)
            rec = perid[mid]
            rec["date"] = date
            if rec["cid"] is None: rec["cid"] = cur
            if typ == "agenda": rec["a"] = True
            else: rec["m"] = True
    both = sum(1 for r in perid.values() if r["a"] and r["m"])
    aonly = sum(1 for r in perid.values() if r["a"] and not r["m"])
    monly = sum(1 for r in perid.values() if r["m"] and not r["a"])
    print(f"\n[{tag}] meetings={len(perid)}  both={both}  agenda_only={aonly}  minutes_only={monly}")
    return perid

allids = analyze(base, "base view")

# try to pull year-specific archives: AgendaCenter uses /AgendaCenter with POST changeArchiveYear,
# but many render year links as /AgendaCenter/Search or the base already lists all. Try the
# undocumented year query used by CivicPlus: ?_=<year> rarely works; instead fetch the RSS which
# lists everything: /AgendaCenter/RSS/ or the print view. Try a couple.
for path in [f"https://{HOST}/AgendaCenter/Search/?term=&CIDs=all&startDate=&endDate=",
             f"https://{HOST}/AgendaCenter/RSS.aspx"]:
    h, s = get(path)
    if s == 200 and "ViewFile" in h:
        analyze(h, path.split(HOST)[1][:40])
    else:
        print(f"\n(skip {path.split(HOST)[1][:40]} -> {s}, ViewFile={'ViewFile' in h})")
    time.sleep(0.5)

# Show a concrete sample: 12 agenda-only meetings with their board + date, so we can eyeball.
print("\nSample agenda_only meetings on the LIVE base page (board / date / id):")
n=0
for mid,r in allids.items():
    if r["a"] and not r["m"]:
        d=r["date"]; board=cid_label.get(r["cid"],"?")
        print(f"   {board[:34]:<34} {d[4:]}-{d[:2]}-{d[2:4]}  id{mid}")
        n+=1
        if n>=12: break
