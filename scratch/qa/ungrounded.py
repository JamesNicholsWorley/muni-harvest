"""Which names or figures in a record did not ground, and where they sit.

Read-only. The worklist says "23/36 names located"; this says WHICH thirteen,
in which contest, so a session knows which page to open.
"""
import json, os, re, sys
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
from qa import layers


def report(stem, what="names"):
    rec = json.load(open(os.path.join(BASE, "data", "json", stem + ".json"), encoding="utf-8"))
    text, source = layers.document_text(stem)
    print(f"== {stem}   reading: {source}   {len(text or '')} chars")
    print(f"   ballots_cast {rec.get('ballots_cast')} ({rec.get('ballots_cast_source')})")
    for ei, e in enumerate(rec.get("elections") or []):
        bad = []
        for ci, c in enumerate(e.get("candidates") or []):
            n = layers.name_of(c)
            v = layers.votes_of(c)
            tally = layers.is_tally_row(c)
            nb = (not tally) and n and not name_found(n, text)
            fb = v is not None and v > 0 and not layers.figure_found(v, text)
            if (what in ("names", "both") and nb) or (what in ("figures", "both") and fb):
                bad.append((ci, n, v, "NAME" if nb else "", "FIG" if fb else ""))
        if bad:
            marks = sum((layers.votes_of(c) or 0) for c in e.get("candidates") or [])
            print(f"  [{ei}] {e.get('office_original')!r} nw={e.get('num_winners')} "
                  f"scope={e.get('scope')} marks={marks}")
            for ci, n, v, a, b in bad:
                print(f"        {ci:>3} {n!r:<40} {v}   {a}{b}")


def name_found(n, text):
    parts = [p for p in re.split(r"[^A-Za-z]+", n) if len(p) > 2]
    if not parts:
        return True
    return all(re.search(re.escape(p), text, re.I) for p in parts[:2])


if __name__ == "__main__":
    for s in sys.argv[1:]:
        if s.startswith("--"):
            continue
        report(s, "figures" if "--figures" in sys.argv else
                  "both" if "--both" in sys.argv else "names")
