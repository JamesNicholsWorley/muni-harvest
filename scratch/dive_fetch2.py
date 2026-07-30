"""Retry pass for the content-dive: re-process town-years NOT already RESULTS_FOUND with
(1) proper URL-encoding (fixes InvalidURL), (2) up to 4 candidates, (3) a WAF cookie-lift
fallback (mint_session) for HTTPError hosts. Merges into dive_results.csv (best verdict)."""
import csv, json, re, ssl, sys, time, urllib.request, urllib.parse
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import fitz

HERE = Path(__file__).resolve().parent
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

cand = defaultdict(list)
for r in csv.DictReader(open(HERE/"dive_candidates.csv", encoding="utf-8")):
    cand[(r["municipality"], r["year"])].append(r)
for k in cand: cand[k].sort(key=lambda r: int(r["priority"]))

prev = {}
for r in csv.DictReader(open(HERE/"dive_results.csv", encoding="utf-8")):
    prev[(r["municipality"], r["year"])] = r
keep = {k: v for k, v in prev.items() if v["verdict"] == "RESULTS_FOUND"}
retry = [k for k in prev if k not in keep]
print(f"keeping {len(keep)} RESULTS_FOUND; retrying {len(retry)} town-years")

HEADING = re.compile(r"annual town election|town election|local election|municipal election|election results|state election", re.I)
BLANKS = re.compile(r"\bblanks?\b", re.I)
OFFICE = re.compile(r"selectman|select board|moderator|town clerk|assessor|school committee|board of health|constable|treasurer|tax collector|library trustee", re.I)
TALLY = re.compile(r"[A-Za-z][A-Za-z.\-' ]{3,40}\s+\d{1,5}\b")

def enc(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path), urllib.parse.quote(p.query, safe="=&?"), ""))

def textify(raw, url):
    if raw[:4] == b"%PDF" or url.lower().endswith(".pdf"):
        d = fitz.open(stream=raw, filetype="pdf")
        return "".join(d[i].get_text() for i in range(min(len(d), 300))), len(d)
    t = raw.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    return re.sub(r"<[^>]+>", " ", t), 0

_sessions = {}
def waf_get(url):
    """Cookie-lift the host once, then fetch bytes past the WAF."""
    from muni_harvest.fetchers.waf_session import mint_session
    host = urllib.parse.urlsplit(url).netloc
    if host not in _sessions:
        _sessions[host] = mint_session(f"https://{host}/") or None
    s = _sessions[host]
    if not s: raise RuntimeError("no session")
    return s.get(url, timeout=35, verify=False).content

def fetch(url):
    u = enc(url)
    if "drive.google.com" in u:
        m = re.search(r"[-\w]{25,}", url)
        if m: u = f"https://drive.google.com/uc?export=download&id={m.group(0)}"
    try:
        raw = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=35, context=ctx).read(30_000_000)
    except urllib.error.HTTPError as e:
        if e.code in (403, 406, 429, 503):
            raw = waf_get(u)          # WAF cookie-lift fallback
        else:
            raise
    return textify(raw, url)

def score(text, year):
    heads = len(HEADING.findall(text)); blanks = len(BLANKS.findall(text))
    offices = len(set(OFFICE.findall(text.lower()))); tallies = len(TALLY.findall(text))
    strong = heads >= 1 and (blanks >= 2 or (offices >= 3 and tallies >= 8))
    maybe = heads >= 1 and (blanks >= 1 or offices >= 2)
    return ("RESULTS_FOUND" if strong else "MAYBE" if maybe else "NO_RESULTS"), \
           f"heads={heads},blanks={blanks},offices={offices},tallies={tallies}"

merged = dict(keep)
for (town, year) in retry:
    best = ("NO_CANDIDATE", "", "", "")
    rank = {"NO_CANDIDATE":0,"FETCH_FAIL":1,"NO_RESULTS":2,"MAYBE":3,"RESULTS_FOUND":4}
    for c in cand.get((town, year), [])[:4]:
        try:
            text, npp = fetch(c["url"]); v, s = score(text, year)
        except Exception as e:
            v, s = "FETCH_FAIL", type(e).__name__; npp = 0
        if rank[v] > rank[best[0]]:
            best = (v, f"{s},pp={npp}", c["url"], c["kind"])
        if v == "RESULTS_FOUND": break
        time.sleep(0.25)
    merged[(town, year)] = {"municipality": town, "year": year, "verdict": best[0],
                            "signals": best[1], "url": best[2], "kind": best[3]}
    print(f"  {town} {year}: {best[0]}  [{best[1]}]", flush=True)

out = HERE/"dive_results.csv"
with out.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["municipality","year","verdict","signals","url","kind"])
    w.writeheader()
    for k in sorted(merged): w.writerow(merged[k])
from collections import Counter
print("\nfinal verdicts:", dict(Counter(v["verdict"] for v in merged.values())))
