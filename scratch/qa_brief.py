"""One compact block per stem: what is held, and which names/figures fail."""
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import layers as L


def brief(stem):
    rec = json.load(open(os.path.join(L.BASE, "data/json", stem + ".json")))
    text, source = L.document_text(stem)
    pdf = os.path.join(L.BASE, "data/pdfs", stem + ".pdf")
    info = ""
    if os.path.exists(pdf):
        out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
        pg = re.search(r"Pages:\s+(\d+)", out)
        rot = re.search(r"Page rot:\s+(\d+)", out)
        info = f"{pg.group(1) if pg else '?'}p rot={rot.group(1) if rot else '?'}"
    else:
        info = "NO PDF"
    print(f"### {stem}  [{info}]  readings={source}  "
          f"ballots={rec.get('ballots_cast')}/{rec.get('ballots_cast_source')}")
    if text is None:
        print("    no reading held")
        return
    def nf(n):
        p = [x for x in re.split(r"[^A-Za-z]+", n) if len(x) > 2]
        return True if not p else all(re.search(re.escape(x), text, re.I) for x in p[:2])
    for e in rec.get("elections") or []:
        bad = [(L.name_of(c), L.votes_of(c)) for c in e.get("candidates") or []
               if L.name_of(c) and not L.is_tally_row(c) and not nf(L.name_of(c))]
        if bad:
            print(f"    [{e.get('office_original')}] seats={e.get('num_winners')} "
                  f"marks={L.marks_in(e)} -> {bad}")


for s in sys.argv[1:]:
    brief(s)
