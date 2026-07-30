"""For the still-unrepresented rotted URLs, ask Wayback whether an archived snapshot
exists (and is retrievable) — the last fallback for a link-rotted document."""
import json, ssl, urllib.request, urllib.parse, time
from pathlib import Path
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (research; polite)"}
rows = [json.loads(l) for l in open(Path(__file__).resolve().parent/"rotted_still.jsonl", encoding="utf-8") if l.strip()]

def cdx(url):
    q = ("https://web.archive.org/cdx/search/cdx?url=" + urllib.parse.quote(url, safe="") +
         "&output=json&limit=5&filter=statuscode:200")
    try:
        req = urllib.request.Request(q, headers=UA)
        data = json.loads(urllib.request.urlopen(req, timeout=40, context=ctx).read().decode())
        return data[1:] if len(data) > 1 else []
    except Exception as e:
        return f"ERR:{type(e).__name__}"

arch = 0
for r in rows:
    snaps = cdx(r["native_url"])
    if isinstance(snaps, str):
        tag = snaps
    elif snaps:
        arch += 1
        ts = snaps[0][1]
        tag = f"ARCHIVED ({len(snaps)}+ snaps, e.g. https://web.archive.org/web/{ts}/{r['native_url'][:60]})"
    else:
        tag = "no wayback snapshot"
    print(f"  {r['municipality']} {r['year']}: {tag}")
    time.sleep(1.0)
print(f"\narchived in Wayback: {arch}/{len(rows)}")
