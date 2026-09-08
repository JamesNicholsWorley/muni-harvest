"""A compact, computed digest of the news-sourced deferrals, for reading.

One block per town-year, small enough that a session can read a bucket of them
in a sitting and long enough that nothing has to be taken on trust: the findings
as the report states them, every contest with its marks and the reason it does
or does not qualify for the derivation, whether the contests agree on a total
among themselves, and which figures fail to ground.

Every number here is computed from the record.  The quotes are taken verbatim
from the reading and bounded to qa.layers.MAX_QUOTE, because for 197 town-years
the reading is a subscription news article.
"""

import collections
import csv
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402


def contest_lines(record, text):
    out = []
    for e in record.get("elections") or []:
        seats = e.get("num_winners") or 1
        m = layers.marks_in(e)
        why = []
        if layers.scope_of(e) != "at_large":
            why.append(layers.scope_of(e))
        if seats != 1:
            why.append(f"{seats} seats")
        if not layers.blanks_printed(e):
            why.append("no blanks row")
        if not layers.has_ballot_candidate(e):
            why.append("write-in scramble")
        ungrounded = [f"{layers.name_of(c)}={layers.votes_of(c)}"
                      for c in e.get("candidates") or []
                      if layers.votes_of(c) is not None
                      and not layers.figure_found(layers.votes_of(c), text)]
        out.append((str(e.get("office_original") or "")[:38], seats, m,
                    ", ".join(why) or "QUALIFIES", ungrounded))
    return out


def agreement(record):
    """What totals do the single-seat town-wide contests agree on?"""
    est = collections.Counter()
    for e in record.get("elections") or []:
        if layers.scope_of(e) == "at_large" and (e.get("num_winners") or 1) == 1:
            m = layers.marks_in(e)
            if m:
                est[m] += 1
    return est.most_common(4)


def main():
    which = set(sys.argv[1:])
    rows = list(csv.DictReader(open(os.path.join(BASE, "qa", "worklist.csv"),
                                    encoding="utf-8")))
    findings = collections.defaultdict(list)
    for r in csv.DictReader(open(os.path.join(BASE, "qa", "layers_report.csv"),
                                 encoding="utf-8")):
        if r["verdict"] in ("FAIL", "UNKNOWN"):
            findings[r["stem"]].append(f'L{r["layer"]} {r["check"]}: '
                                       f'{r["evidence"][:70]}')
    for r in rows:
        stem = r["stem"]
        if which and stem not in which:
            continue
        if not which and not (r["status"] == "deferred" and
                              "CANNOT BE WORKED IN A CLOUD SESSION" in r["resolution"]):
            continue
        p = os.path.join(BASE, "data", "json", stem + ".json")
        if not os.path.exists(p):
            continue
        record = json.load(open(p, encoding="utf-8"))
        text, source = layers.document_text(stem)
        text = text or ""
        print(f"### {stem}  [{r['bucket']}] size={r['size']} src={source}"
              f" ballots_cast={record.get('ballots_cast')}")
        for f in findings[stem]:
            print("    !", f)
        print("    agree:", agreement(record))
        for office, seats, m, why, ung in contest_lines(record, text):
            u = ("  UNGROUNDED " + "; ".join(ung)) if ung else ""
            print(f"    {office:<38} s={seats} marks={m:<6} {why}{u}")
        hits = [" ".join(mm.group(0).split())[:layers.MAX_QUOTE]
                for mm in re.finditer(
                    r"[^.\n]{0,70}\b(?:ballots? cast|turnout|voted|registered "
                    r"voters|total voters|blank)\b[^.\n]{0,70}", text, re.I)][:3]
        for h in hits:
            print("    q>", h)
        print()


if __name__ == "__main__":
    main()
