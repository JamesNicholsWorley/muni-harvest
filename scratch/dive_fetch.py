"""Content-dive worker: for each missing town-year, fetch its best container doc(s), extract
text, and detect genuine MA municipal election-results content. Strong signal: an election
heading + 'Blanks' (every MA race lists Blanks) + vote tallies. Resumable; writes
dive_results.csv incrementally. Run: python dive_fetch.py [max_per_ty]"""
import csv, json, re, ssl, sys, io, time, urllib.request
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import fitz

HERE = Path(__file__).resolve().parent
MAXTRY = int(sys.argv[1]) if len(sys.argv) > 1 else 2      # candidates to try per town-year
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

cand = defaultdict(list)
for r in csv.DictReader(open(HERE/"dive_candidates.csv", encoding="utf-8")):
    cand[(r["municipality"], r["year"])].append(r)
for k in cand: cand[k].sort(key=lambda r: int(r["priority"]))

done = {}
outp = HERE/"dive_results.csv"
if outp.exists():
    for r in csv.DictReader(open(outp, encoding="utf-8")):
        done[(r["municipality"], r["year"])] = r["verdict"]

HEADING = re.compile(r"annual town election|town election|local election|municipal election|election results|state election", re.I)
BLANKS = re.compile(r"\bblanks?\b", re.I)
OFFICE = re.compile(r"selectman|select board|moderator|town clerk|assessor|school committee|"
                    r"board of health|constable|treasurer|tax collector|library trustee", re.I)
TALLY = re.compile(r"[A-Za-z][A-Za-z.\-' ]{3,40}\.{0,}\s+\d{1,5}\b")   # "Name .... 123"
ATTEST = re.compile(r"true copy attest|a true copy|town clerk", re.I)

def pdf_text(raw):
    d = fitz.open(stream=raw, filetype="pdf")
    return "".join(d[i].get_text() for i in range(min(len(d), 300))), len(d)

def html_text(raw):
    t = raw.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    return re.sub(r"<[^>]+>", " ", t), 0

def fetch(url):
    u = url
    if "drive.google.com" in u:
        m = re.search(r"[-\w]{25,}", u)
        if m: u = f"https://drive.google.com/uc?export=download&id={m.group(0)}"
    raw = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=35, context=ctx).read(30_000_000)
    if raw[:4] == b"%PDF" or url.lower().endswith(".pdf"):
        return pdf_text(raw)
    return html_text(raw)

def score(text, year):
    heads = len(HEADING.findall(text))
    blanks = len(BLANKS.findall(text))
    offices = len(set(OFFICE.findall(text.lower())))
    tallies = len(TALLY.findall(text))
    yr = year in text
    # genuine results: an election heading + Blanks(>=2, one per race) OR many tallies + offices
    strong = heads >= 1 and (blanks >= 2 or (offices >= 3 and tallies >= 8))
    maybe = heads >= 1 and (blanks >= 1 or offices >= 2)
    return ("RESULTS_FOUND" if strong else "MAYBE" if maybe else "NO_RESULTS"), \
           f"heads={heads},blanks={blanks},offices={offices},tallies={tallies},yr={yr}"

new = 0
with outp.open("a", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    if not done: w.writerow(["municipality", "year", "verdict", "signals", "url", "kind"]); f.flush()
    for (town, year), cs in sorted(cand.items()):
        if (town, year) in done: continue
        verdict, sig, url, kind = "NO_CANDIDATE", "", "", ""
        for c in cs[:MAXTRY]:
            try:
                text, npp = fetch(c["url"])
                v, s = score(text, year)
                if v in ("RESULTS_FOUND", "MAYBE") or verdict == "NO_CANDIDATE":
                    verdict, sig, url, kind = v, f"{s},pp={npp}", c["url"], c["kind"]
                if v == "RESULTS_FOUND": break
            except Exception as e:
                if verdict == "NO_CANDIDATE": verdict, sig, url, kind = "FETCH_FAIL", type(e).__name__, c["url"], c["kind"]
            time.sleep(0.3)
        w.writerow([town, year, verdict, sig, url, kind]); f.flush()
        new += 1
        print(f"  {town} {year}: {verdict}  [{sig}]", flush=True)
print(f"\nprocessed {new} new town-years")
