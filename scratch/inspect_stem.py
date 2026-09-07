"""Show one town-year the way a reader needs it: findings, record, and the
document lines the failing check is about.

Read-only.  Written for the unattended QA loop -- `python -m qa.layers` says a
figure is not in the document, and the next question is always "which figure,
and what does the page say near it", which is two greps and a JSON dump every
single time.

    python scratch/inspect_stem.py Plainville2023
"""
import collections
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import layers

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def findings(stem):
    out = []
    with open(os.path.join(BASE, "qa", "layers_report.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["stem"] == stem and r["verdict"] in ("FAIL", "UNKNOWN", "NOTE"):
                out.append(r)
    return out


def main(stem, window=90):
    rec = json.load(open(os.path.join(BASE, "data", "json", stem + ".json"),
                        encoding="utf-8"))
    text, source = layers.document_text(stem)
    print(f"== {stem}   source: {source}   text: {len(text or '')} chars")
    for f in findings(stem):
        print(f"  {f['layer']} {f['check']:<26} {f['verdict']:<8} {f['evidence'][:120]}")
    print(f"\nballots_cast {rec.get('ballots_cast')} ({rec.get('ballots_cast_source')})")
    ungrounded = []
    for e in rec.get("elections") or []:
        marks = layers.marks_in(e)
        print(f"\n  {e.get('office_original')!r}  seats={e.get('num_winners')} "
              f"scope={layers.scope_of(e)} blanks={layers.blanks_printed(e)} marks={marks}")
        for c in e.get("candidates") or []:
            v = layers.votes_of(c)
            ok = "" if v is None or layers.figure_found(v, text or "") else "  <-- NOT IN TEXT"
            nm = layers.name_of(c)
            nok = "" if not nm or re.search(re.escape(nm.split()[-1]), text or "", re.I) else "  <-- NAME NOT IN TEXT"
            print(f"      {nm!r:<40} {v}{ok}{nok}")
            if ok:
                ungrounded.append((nm, v))
    if text:
        print("\n---- document windows ----")
        for nm, v in ungrounded[:12]:
            key = re.split(r"[^A-Za-z]+", nm)[-1] if nm else ""
            m = re.search(re.escape(key), text, re.I) if key else None
            if m:
                print(f"  {nm} / {v}: ...{text[max(0,m.start()-window):m.end()+window]}...")
            else:
                print(f"  {nm} / {v}: name not found in text")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 90)
