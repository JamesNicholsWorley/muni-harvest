import csv, ssl, time, urllib.request, urllib.error, random
from collections import Counter
from pathlib import Path
rows = [r for r in csv.DictReader(open(Path(__file__).resolve().parent/"election_seed_verified.csv", encoding="utf-8"))
        if r["capture_status"].startswith("MISS")]
random.seed(7); random.shuffle(rows); sample = rows[:30]
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {"User-Agent":"Mozilla/5.0 (research; polite)"}
cnt = Counter()
for r in sample:
    u = r["native_url"]
    try:
        req = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(req, timeout=25, context=ctx) as resp:
            ct = resp.headers.get("Content-Type",""); body = resp.read(2000)
            live = "PDF" if "pdf" in ct.lower() else ("HTML" if "html" in ct.lower() else ct[:15])
            cnt[f"200 {live}"] += 1; tag = f"200 {live} ({len(body)}b)"
    except urllib.error.HTTPError as e:
        cnt[f"HTTP {e.code}"] += 1; tag = f"HTTP {e.code}"
    except Exception as e:
        cnt[type(e).__name__] += 1; tag = type(e).__name__
    print(f"  {r['municipality']:<15}{r['year']}  {tag:<22}{u[:70]}")
    time.sleep(0.3)
print("\nsummary:", dict(cnt.most_common()))
live = sum(v for k,v in cnt.items() if k.startswith("200"))
print(f"live/fetchable now: {live}/{len(sample)} = {live/len(sample):.0%}")
