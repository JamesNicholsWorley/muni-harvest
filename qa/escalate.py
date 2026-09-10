"""Decide whether a parse needs a stronger model, from the parse alone.

The cheap model is right most of the time and wrong in ways this corpus already
knows how to name. So rather than guess in advance which documents are hard --
by skew, by resolution, by scan quality -- parse everything cheaply and let the
document's own arithmetic say which parses to buy again. Predicting difficulty
is a guess; a contest whose marks exceed ballots times seats is a fact.

The asymmetry that makes this work is the same one the QA layers rest on:

    marks >  ballots x seats    impossible at any magnitude. Escalate.
    marks == ballots x seats    the digits were read faithfully. Accept.
    marks <  ballots x seats    usually legitimate -- blanks, uncounted
                                write-ins. Describe it; do not escalate.

What this deliberately does NOT do is treat closure as proof. Exact closure is
evidence about FIGURES and only about figures. It is blind to a fused race,
because merging two blocks preserves the identity exactly, and blind to a lost
name, because a dropped candidate's votes are usually captured under the name
above. Those two need the document, so they escalate on structural grounds
rather than arithmetic ones.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import mechanical                                   # noqa: E402

ADDRESS = re.compile(r"^\s*[0-9]+\s+[A-Za-z]", re.M)     # "42 Elm Street"

# A page that is not a return at all. Buying a second opinion on it is money
# spent on a locator failure: no model can transcribe an election from town
# meeting minutes. These need a different cut, not a better reader.
WRONG_DOCUMENT = re.compile(
    r"(town meeting minutes|not an election return|no (annual )?municipal "
    r"election|is a warrant|ballot template|caucus|salary|officers directory|"
    r"table of contents|no election (results|return) )", re.I)

# The transcriber doing exactly what the spec asks. `municipality_printed:
# false` exists so the record can disagree with the filename; a note saying the
# town is not named is that mechanism working, not a defect. Escalating on it
# taught the corpus to treat honesty as failure, which is the surest way to
# stop getting it.
HOUSEKEEPING = re.compile(
    r"(no municipality name|municipality (name )?(is )?not print|town name "
    r"(is )?not|no (election )?date (is )?print|date (is )?not print|"
    r"filename (says|indicates)|seat count (is )?not print|no seat count|"
    r"no 'vote for'|vote for.*not print)", re.I)
ROLE = re.compile(r"^(BLANKS?|WRITE[- ]?INS?|OTHERS?|TOTALS?|SCATTER\w*)$", re.I)


def _marks(contest):
    v = [c.get("votes") for c in contest.get("candidates", [])]
    return None if any(x is None for x in v) else sum(v)


def review(record):
    """(verdict, reasons). verdict is 'accept' or 'escalate'."""
    contests = record.get("elections", record.get("contests", []))
    reasons = []
    ballots, support, dissent = mechanical.ballot_quorum(contests)
    if ballots is None and len(contests) >= 2:
        # Two different silences. Nothing closing exactly is a gap in what we
        # can CHECK and 294 published records already carry it. A quorum that
        # other contests outvote is a disagreement INSIDE the record, and that
        # is a finding -- somewhere in it, a figure or a seat count is wrong,
        # and nothing here can say which.
        if support >= 2 and dissent >= support:
            reasons.append(
                "the contests disagree about how many ballots were cast -- %d "
                "close on one count and %d imply a larger one"
                % (support, dissent))
        else:
            reasons.append("no two contests agree on a ballot count")

    for c in contests:
        if c.get("is_recount"):
            continue
        office = c.get("office_original", "?")
        cands = c.get("candidates", [])
        seats = c.get("num_winners")
        marks = _marks(c)

        if not cands:
            reasons.append(f"{office}: no candidates")
            continue
        for cand in cands:
            nm = (cand.get("name_original") or "").strip()
            if not nm:
                reasons.append(f"{office}: a row has no name")
            elif ADDRESS.match(nm):
                reasons.append(f"{office}: name looks like an address -- {nm!r}")
        if any(cand.get("votes") is None for cand in cands):
            reasons.append(f"{office}: a figure was not readable")

        if seats is None:
            # A null seat count is the spec's honest answer, not a defect --
            # but it is also the field that decides who won, so it is bought
            # again rather than published on the cheap model's uncertainty.
            reasons.append(f"{office}: seat count left null by the transcriber")
        elif not seats:
            reasons.append(f"{office}: seat count is zero")
        elif c.get("scope") != "regional_district" and ballots and marks is not None:
            if marks > ballots * seats:
                reasons.append(
                    f"{office}: {marks} marks exceeds {ballots}x{seats}"
                    f"={ballots*seats} -- impossible")
            elif c.get("num_winners_source") in ("derived", "marked"):
                implied = round(marks / ballots) if ballots else None
                if implied and implied != seats:
                    reasons.append(
                        f"{office}: seats inferred as {seats} but the totals "
                        f"imply {implied}")

    # A return with one contest is nearly always a cut that lost the rest.
    if len(contests) == 1:
        reasons.append("only one contest -- a return usually elects several")
    flagged = list(record.get("document_problems") or [])
    for c in contests:
        flagged += list(c.get("problems") or [])
    for note in flagged:
        if WRONG_DOCUMENT.search(note):
            reasons.append(f"the document is not a return: {note[:140]}")
        elif not HOUSEKEEPING.search(note):
            reasons.append(f"transcriber flagged: {note[:140]}")
    # A recount is a second reading of one office, so it does not owe the
    # ballot arithmetic anything and must not drag the record into escalation.
    

    return ("escalate" if reasons else "accept"), reasons
