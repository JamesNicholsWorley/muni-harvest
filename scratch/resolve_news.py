"""Resolve the deferrals that were only ever blocked by a missing link.

178 rows were deferred "CANNOT BE WORKED IN A CLOUD SESSION: layers
.document_text returns None".  That was true when it was written and is not
true now: `qa.bootstrap` links `civicatlas-private/news_text`, and all 178 of
those town-years read from it.  They were never unreadable; the reading simply
was not mounted.

What is left after the link is a different answer, and it is mostly the same
one: for a record whose only source is a news article, `ballots_derivable` is
UNKNOWN permanently and correctly.  `derive_ballots` needs a contest that
prints its BLANKS, and prose does not print blanks -- it prints who won and by
how much.  That is a fact about the source, not a defect in the record, and it
will not change until an official return is found.

So each resolution here says three things, all of them computed or quoted, none
of them asserted: which contests exist and exactly why each fails to qualify,
what the article says about turnout in its own words, and whether the record
already holds a ballot count.  Every quotation is bounded to qa.layers
.MAX_QUOTE, because the worklist is committed to a public repository and the
source is a subscription article.

    python -m scratch.resolve_news              # print, change nothing
    python -m scratch.resolve_news --write      # write them into the worklist
"""

import collections
import csv
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402

WORKLIST = os.path.join(BASE, "qa", "worklist.csv")
MARK = "CANNOT BE WORKED IN A CLOUD SESSION"

# A sentence that says how many people voted, as prose actually says it.
RE_TURNOUT = re.compile(
    r"[^.\n]{0,90}\b(?:ballots?\s+(?:were\s+)?cast|cast\s+(?:a\s+)?ballots?"
    r"|turnout|came\s+out\s+to\s+(?:the\s+polls|vote)|went\s+to\s+the\s+polls"
    r"|turned\s+out|participated)\b[^.\n]{0,90}", re.I)


def why_not_qualifying(e):
    bad = []
    scope = layers.scope_of(e)
    if scope != "at_large":
        bad.append(scope)
    if (e.get("num_winners") or 1) != 1:
        bad.append("%d seats" % (e.get("num_winners") or 1))
    if not layers.blanks_printed(e):
        bad.append("no blanks row")
    if not layers.has_ballot_candidate(e):
        bad.append("write-in only")
    return ", ".join(bad)


def turnout_quote(text):
    for m in RE_TURNOUT.finditer(text):
        w = " ".join(m.group(0).split())
        if re.search(r"\d", w):
            return w[:layers.MAX_QUOTE]
    return None


def resolution(stem, record, text, findings):
    contests = record.get("elections") or []
    reasons = collections.Counter()
    for e in contests:
        reasons[why_not_qualifying(e) or "qualifies"] += 1
    held = record.get("ballots_cast")
    q = turnout_quote(text)

    parts = [
        "READ data/news_text/%s.md, which is the only reading held for this "
        "town-year -- the earlier deferral said document_text returns None, "
        "and that was true only because qa.bootstrap had not linked "
        "civicatlas-private/news_text. It does now, so this is worked, not "
        "deferred." % stem,
        "The record holds %d contest(s); none qualifies for the ballot "
        "derivation and the reasons are computed, not guessed: %s."
        % (len(contests),
           "; ".join(f"{n} {r}" for r, n in reasons.most_common())),
        "A news article reports who won and by how much; it does not print a "
        "blanks row, and blanks are what make a block total the whole ballot "
        "rather than a lower bound. So ballots_derivable is UNKNOWN correctly "
        "and permanently for this source, and only an official return changes "
        "it.",
    ]
    if isinstance(held, int) and held > 0:
        parts.append("The record does hold ballots_cast %d%s." %
                     (held, ", and the article prints it"
                      if layers.figure_found(held, text) else
                      " (not found in this reading)"))
    else:
        parts.append("The record holds no ballots_cast, and this reading "
                     + ("prints no count either." if not q else
                        "prints only what is quoted below."))
    if q:
        parts.append('The article says, verbatim: "%s"' % q)
    else:
        parts.append("Nothing in the article states a turnout or ballot "
                     "figure; searched for ballots cast, turnout, went to the "
                     "polls, turned out and participated.")
    other = [f for f in findings if f[1] != "ballots_derivable"]
    if other:
        parts.append("Other findings on this record are untouched by this "
                     "resolution: " + "; ".join(f"{f[1]} {f[2]}" for f in other)
                     + ".")
    return " ".join(parts)


def main():
    with io.open(WORKLIST, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
    findings = collections.defaultdict(list)
    for r in csv.DictReader(io.open(os.path.join(BASE, "qa",
                                                 "layers_report.csv"),
                                    encoding="utf-8")):
        if r["verdict"] in ("FAIL", "UNKNOWN"):
            findings[r["stem"]].append((r["layer"], r["check"], r["verdict"]))

    done = 0
    for r in rows:
        if r["status"] != "deferred" or MARK not in (r["resolution"] or ""):
            continue
        stem = r["stem"]
        text, source = layers.document_text(stem)
        if source != "news_text" or not text:
            continue
        fs = findings[stem]
        # Only the records whose ONLY open finding is the derivation. Anything
        # else -- an ungrounded figure, a thin year, an impossible contest --
        # is a different question and is not answered by this.
        if any(f[1] != "ballots_derivable" for f in fs):
            continue
        record = json.load(io.open(os.path.join(BASE, "data", "json",
                                                stem + ".json"),
                                   encoding="utf-8"))
        r["status"] = "done"
        r["resolution"] = resolution(stem, record, text, fs)
        done += 1
        print(f"{stem:<22} {r['resolution'][:110]}")
    print(f"\n{done} rows resolved")
    if "--write" in sys.argv and done:
        with io.open(WORKLIST, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print("written to qa/worklist.csv")
    else:
        print("nothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
