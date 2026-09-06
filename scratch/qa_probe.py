"""Read-only helper: which names/figures in a record fail to ground, and where.

Not part of qa/ tooling -- a scratch lens on the same functions, so a session can
see WHICH name failed rather than only the count.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import layers as L


def probe(stem):
    rec = json.load(open(os.path.join(L.BASE, "data/json", stem + ".json")))
    text, source = L.document_text(stem)
    print(f"== {stem}  readings: {source}")
    if text is None:
        print("   no reading held")
        return
    def name_found(n):
        parts = [p for p in re.split(r"[^A-Za-z]+", n) if len(p) > 2]
        if not parts:
            return True
        return all(re.search(re.escape(p), text, re.I) for p in parts[:2])
    for e in rec.get("elections") or []:
        off = e.get("office_original") or e.get("office")
        head = f"  [{off}] seats={e.get('num_winners')} scope={L.scope_of(e)}"
        lines = []
        for c in e.get("candidates") or []:
            n = L.name_of(c)
            v = L.votes_of(c)
            bad = []
            if n and not L.is_tally_row(c) and not name_found(n):
                bad.append("NAME")
            if v is not None and v > 0 and not L.figure_found(v, text):
                bad.append("FIG")
            if bad:
                lines.append(f"      {'+'.join(bad):9s} {n!r} = {v}")
        if lines:
            print(head)
            print("\n".join(lines))


if __name__ == "__main__":
    for s in sys.argv[1:]:
        probe(s)
