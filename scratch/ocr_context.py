"""What the held reading says where a figure should be, and where to look.

An ungrounded figure on a scan is nearly always a legible figure the OCR lost.
The OCR still gets the NAME, most of the time, so the row it mangled is
findable -- and what it put there instead is the best clue to which page and
which band of it to render.
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402


def main():
    for stem in sys.argv[1:]:
        record = json.load(open(os.path.join(BASE, "data", "json",
                                             stem + ".json"), encoding="utf-8"))
        text, source = layers.document_text(stem)
        text = text or ""
        print("=" * 76)
        print(stem, "|", source, "| ballots_cast", record.get("ballots_cast"))
        for e in record.get("elections") or []:
            ung = [c for c in e.get("candidates") or []
                   if layers.votes_of(c) is not None
                   and not layers.figure_found(layers.votes_of(c), text)]
            if not ung:
                continue
            seats = e.get("num_winners") or 1
            print("  %s  (%d seats, %s) marks=%d"
                  % (e.get("office_original"), seats, layers.scope_of(e),
                     layers.marks_in(e)))
            for c in e.get("candidates") or []:
                v = layers.votes_of(c)
                mark = "  <-- UNGROUNDED" if c in ung else ""
                print("      %-34s %s%s" % (layers.name_of(c)[:34], v, mark))
            for c in ung:
                key = (layers.name_of(c).split()[-1]
                       if layers.name_of(c) else "")
                i = text.find(key) if key else -1
                if i >= 0:
                    a, b = max(0, i - 90), min(len(text), i + 150)
                    print("      OCR near %r: %s"
                          % (key, " ".join(text[a:b].split())))


if __name__ == "__main__":
    main()
