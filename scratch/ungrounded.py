"""Every ungrounded figure in a record, with the article's own words around it.

A figure that does not ground is not a wrong figure.  It is a figure the reading
does not contain, and the reasons are different in kind: the source spells the
number in words, the source prints a percentage and the record holds a count
computed from it, the record sums two printed rows into one, the extraction
split the digits, or the figure really is wrong.  Only the passage decides
which, so this puts the passage next to it.
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402

WORDS = ("zero one two three four five six seven eight nine ten eleven twelve "
         "thirteen fourteen fifteen sixteen seventeen eighteen nineteen "
         "twenty").split()


def main():
    for stem in sys.argv[1:]:
        record = json.load(open(os.path.join(BASE, "data", "json",
                                             stem + ".json"), encoding="utf-8"))
        text, source = layers.document_text(stem)
        print("=" * 76)
        print(stem, "|", source, "| ballots_cast", record.get("ballots_cast"))
        for e in record.get("elections") or []:
            for c in e.get("candidates") or []:
                v = layers.votes_of(c)
                if v is None or layers.figure_found(v, text):
                    continue
                name = layers.name_of(c)
                print("  UNGROUNDED  %-38s %-26s %s"
                      % (str(e.get("office_original"))[:38], name[:26], v))
                # the article around the candidate's name, which is where the
                # figure would be if it were printed at all
                key = name.split()[-1] if name else ""
                i = text.find(key) if key else -1
                if i >= 0:
                    a, b = max(0, i - 130), min(len(text), i + 170)
                    print("      near the name:", " ".join(text[a:b].split()))
                if 0 <= v < len(WORDS):
                    for m in re.finditer(r"\b" + WORDS[v] + r"\b", text, re.I):
                        a, b = max(0, m.start() - 90), min(len(text), m.end() + 90)
                        print(f"      spelled '{WORDS[v]}':",
                              " ".join(text[a:b].split()))
                        break
        print()


if __name__ == "__main__":
    main()
