"""One worksheet per news-sourced town-year, so a session can read it.

Everything a resolution needs and nothing a model has to invent: what the record
holds, which contests qualify for the ballot derivation and why the rest do not,
which figures failed to ground and where in the article they do or do not
appear, and a bounded verbatim window around each.  The arithmetic is done here
rather than by a model, which is the project's rule.
"""

import csv
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402


def why_not_qualifying(e):
    bad = []
    if layers.scope_of(e) != "at_large":
        bad.append("scope " + layers.scope_of(e))
    if (e.get("num_winners") or 1) != 1:
        bad.append("%d seats" % (e.get("num_winners") or 1))
    if not layers.blanks_printed(e):
        bad.append("no blanks row")
    if not layers.has_ballot_candidate(e):
        bad.append("no candidate on the ballot")
    return ", ".join(bad) or "qualifies"


def window(text, needle, pad=55):
    i = text.find(needle)
    if i < 0:
        return None
    a, b = max(0, i - pad), min(len(text), i + len(needle) + pad)
    return " ".join(text[a:b].split())


def worksheet(stem, findings):
    p = os.path.join(BASE, "data", "json", stem + ".json")
    record = json.load(open(p, encoding="utf-8"))
    text, source = layers.document_text(stem)
    print("=" * 78)
    print(stem, "| source", source, "| chars", len(text or ""),
          "| ballots_cast", record.get("ballots_cast"),
          "| municipality", repr(record.get("municipality")))
    for f in findings:
        print("   FINDING L%s %s %s: %s" % f)
    b, why, est = layers.derive_ballots(record)
    print("   derive_ballots:", why)
    for e in record.get("elections") or []:
        print("   - %-42s seats=%-2s %s | %s"
              % (str(e.get("office_original"))[:42], e.get("num_winners"),
                 layers.scope_of(e), why_not_qualifying(e)))
        for c in e.get("candidates") or []:
            v = layers.votes_of(c)
            g = "" if v is None else (
                "found" if layers.figure_found(v, text or "") else "NOT-FOUND")
            n = layers.name_of(c)
            ng = "" if not n else ("" if layers.figure_found and n.lower() in
                                   (text or "").lower() else "name NOT-FOUND")
            print("        %-34s %-7s %-9s %s" % (repr(n)[:34], v, g, ng))
    print("   -- article, ballot-ish lines --")
    seen = set()
    for m in re.finditer(r"[^.]{0,80}\b(?:ballots?|turnout|votes cast|registered"
                         r"|blank|write-in)\b[^.]{0,80}", text or "", re.I):
        w = " ".join(m.group(0).split())[:160]
        if w not in seen:
            seen.add(w)
            print("      |", w)


def main():
    stems = sys.argv[1:]
    findings = {}
    for r in csv.DictReader(open(os.path.join(BASE, "qa", "layers_report.csv"),
                                 encoding="utf-8")):
        if r["verdict"] in ("FAIL", "UNKNOWN"):
            findings.setdefault(r["stem"], []).append(
                (r["layer"], r["check"], r["verdict"], r["evidence"][:100]))
    for s in stems:
        worksheet(s, findings.get(s, []))


if __name__ == "__main__":
    main()
