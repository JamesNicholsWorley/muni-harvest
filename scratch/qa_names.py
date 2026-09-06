"""Compact: for each stem, the names that do not ground, and how much reading is held."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import layers as L

for stem in sys.argv[1:]:
    rec = json.load(open(os.path.join(L.BASE, "data/json", stem + ".json")))
    text, source = L.document_text(stem)
    if text is None:
        print(f"{stem}: NO READING")
        continue
    def nf(n):
        parts = [p for p in re.split(r"[^A-Za-z]+", n) if len(p) > 2]
        return True if not parts else all(
            re.search(re.escape(p), text, re.I) for p in parts[:2])
    bad, tot = [], 0
    for e in rec.get("elections") or []:
        for c in e.get("candidates") or []:
            n = L.name_of(c)
            if n and not L.is_tally_row(c):
                tot += 1
                if not nf(n):
                    bad.append(n)
    print(f"{stem}: {len(bad)}/{tot} ungrounded | {source} {L.readable_chars(text)}ch")
    for n in bad:
        print(f"    {n}")
