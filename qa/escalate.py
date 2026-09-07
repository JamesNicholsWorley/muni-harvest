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
import collections
import re

ADDRESS = re.compile(r"^\s*[0-9]+\s+[A-Za-z]", re.M)     # "42 Elm Street"
ROLE = re.compile(r"^(BLANKS?|WRITE[- ]?INS?|OTHERS?|TOTALS?|SCATTER\w*)$", re.I)


def _marks(contest):
    v = [c.get("votes") for c in contest.get("candidates", [])]
    return None if any(x is None for x in v) else sum(v)


def derive_ballots(contests):
    """The ballot count, from contests that agree. None is a real answer."""
    q = collections.Counter()
    for c in contests:
        m, s = _marks(c), c.get("num_winners")
        if m is None or not s or c.get("scope") == "regional_district":
            continue
        if m % s == 0:
            q[m // s] += 1
    if not q:
        return None
    best, n = q.most_common(1)[0]
    return best if n >= 2 else None


def review(record):
    """(verdict, reasons). verdict is 'accept' or 'escalate'."""
    contests = record.get("elections", record.get("contests", []))
    reasons = []
    ballots = derive_ballots(contests)
    if ballots is None and len(contests) >= 2:
        reasons.append("no two contests agree on a ballot count")

    for c in contests:
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

        if not seats:
            reasons.append(f"{office}: no seat count")
        elif c.get("scope") != "regional_district" and ballots and marks is not None:
            if marks > ballots * seats:
                reasons.append(
                    f"{office}: {marks} marks exceeds {ballots}x{seats}"
                    f"={ballots*seats} -- impossible")
            elif c.get("num_winners_source") == "inferred":
                implied = round(marks / ballots) if ballots else None
                if implied and implied != seats:
                    reasons.append(
                        f"{office}: seats inferred as {seats} but the totals "
                        f"imply {implied}")

    # A return with one contest is nearly always a cut that lost the rest.
    if len(contests) == 1:
        reasons.append("only one contest -- a return usually elects several")
    if record.get("problems"):
        reasons.append(f"transcriber flagged: {'; '.join(record['problems'])[:160]}")

    return ("escalate" if reasons else "accept"), reasons
