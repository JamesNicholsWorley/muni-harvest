"""Manual investigation: for a real board's agenda-only meetings, READ the agenda PDF
(board, date, items) and surface identifiers to search for the meeting / its minutes."""
import re, ssl, sys, io, urllib.request
HOST=sys.argv[1] if len(sys.argv)>1 else "concordma.gov"
BOARD_RX=sys.argv[2] if len(sys.argv)>2 else "select"
UA="Mozilla/5.0 (research; polite)"
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":UA}),timeout=40,context=ctx)
html=get(f"https://{HOST}/AgendaCenter").read().decode("utf-8","replace")
# category legend
CID=re.compile(r'name="chkCategoryID"\s+value="(\d+)"[^>]*>\s*([^<]{2,70})')
cid_label={c:re.sub(r"\s+"," ",l).strip() for c,l in CID.findall(html)}
target_cids={c for c,l in cid_label.items() if re.search(BOARD_RX,l,re.I)}
print("matched boards:", {c:cid_label[c] for c in target_cids})
# walk sections id=catN, assign ViewFile to current cid; collect agenda & minutes ids
WALK=re.compile(r'id="cat(\d+)"|/AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{8})-(\d+)',re.I)
cur=None; ag={}; mn=set()
for m in WALK.finditer(html):
    if m.group(1): cur=m.group(1)
    else:
        typ,date,mid=m.group(2).lower(),m.group(3),m.group(4)
        if cur in target_cids:
            if typ=="agenda": ag[mid]=date
            else: mn.add(mid)
agonly=[(mid,d) for mid,d in ag.items() if mid not in mn and d[-4:] in ("2020","2021","2022","2023")]
agonly.sort(key=lambda x:x[1][-4:])
print(f"{HOST} board~/{BOARD_RX}/: {len(ag)} agendas, {len(mn)} minutes on live page; agenda-only(2020-23): {len(agonly)}")

import fitz
for mid,date in agonly[:3]:
    url=f"https://{HOST}/AgendaCenter/ViewFile/Agenda/_{date}-{mid}"
    try:
        raw=get(url).read()
        doc=fitz.open(stream=raw,filetype="pdf")
        txt=doc[0].get_text()[:1500]
    except Exception as e:
        txt=f"(couldn't read: {e})"
    print(f"\n===== AGENDA {date[-4:]}-{date[:2]}-{date[2:4]} id{mid} =====\n{url}")
    print(re.sub(r'\n{2,}','\n',txt).strip()[:1200])
    # does a Minutes file exist live? (confirm the gap)
    murl=f"https://{HOST}/AgendaCenter/ViewFile/Minutes/_{date}-{mid}"
    try:
        r=get(murl); ct=r.headers.get("Content-Type",""); ok="pdf" in ct.lower()
        print(f"[minutes probe] {murl} -> {r.status} {ct[:20]} {'HAS MINUTES' if ok else ''}")
    except Exception as e:
        print(f"[minutes probe] {murl} -> {e}")
