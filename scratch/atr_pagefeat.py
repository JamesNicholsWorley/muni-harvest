"""Measure what separates a return page from the pages the locator mistook for one.

The 317 sections holding no contest are a labelled set and so are the 581 that
published: for one group the page the locator scored highest was a warrant, a
contents page or an officers directory, and for the other it was the return.
Both are on this disk. So the question of what the locator should have scored
can be asked of the corpus rather than guessed.
"""
import collections
import glob
import json
import os
import re
import statistics
import sys

import pymupdf

pymupdf.TOOLS.mupdf_display_errors(False)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.atr_sections import HEAD, BALLOT, OFFICE            # noqa: E402

INT = re.compile(r"(?<![\d.,])\d{1,5}(?![\d.,])")
ARTICLE = re.compile(r"\bARTICLE\s+\d|\bVOTED\b|\bMOTION\b|so\s+voted|"
                     r"\bmoved\s+(by|and)\b|to\s+see\s+if\s+the\s+town", re.I)
LEADER = re.compile(r"\.{4,}")
STATE = re.compile(r"(GOVERNOR|LIEUTENANT\s+GOVERNOR|PRESIDENT|SENATOR\s+IN\s+"
                   r"CONGRESS|REPRESENTATIVE\s+IN\s+CONGRESS|COUNCILLOR|"
                   r"REGISTER\s+OF\s+PROBATE|DISTRICT\s+ATTORNEY|SHERIFF|"
                   r"ATTORNEY\s+GENERAL|SECRETARY\s+OF\s+STATE|"
                   r"STATE\s+(PRIMARY|ELECTION))", re.I)
# A person's name as a return prints it: two or more capitalised words, no
# lower-case sentence around them.
NAME = re.compile(r"^[^a-z]*\b([A-Z][A-Za-z'’.-]+\s+){1,4}[A-Z][A-Za-z'’.-]+"
                  r"[^a-z]*$")


def features(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    prose = statistics.mean([len(l) for l in lines]) if lines else 0
    ints = len(INT.findall(text))
    names = sum(1 for l in lines if NAME.match(l))
    return {
        "h": len(HEAD.findall(text)),
        "b": len(BALLOT.findall(text)),
        "o": len(OFFICE.findall(text)),
        "prose": round(prose, 1),
        "ints": ints,
        "names": names,
        "article": len(ARTICLE.findall(text)),
        "leader": len(LEADER.findall(text)),
        "state": len(STATE.findall(text)),
        "lines": len(lines),
    }


def main():
    out = {}
    for label, stems in (("return", sys.argv[1]), ("not", sys.argv[2])):
        for stem in open(stems).read().split():
            p = "/tmp/sections/%s_atr.pdf" % stem
            if not os.path.exists(p):
                continue
            try:
                texts = [pg.get_text() for pg in pymupdf.open(p)]
            except Exception:
                continue
            if not any(t.strip() for t in texts):
                continue
            out.setdefault(label, {})[stem] = [features(t) for t in texts]
    json.dump(out, open(sys.argv[3], "w"))
    for label, d in out.items():
        print(label, len(d), "sections",
              sum(len(v) for v in d.values()), "pages")


if __name__ == "__main__":
    main()
