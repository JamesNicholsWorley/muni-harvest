"""Repair the two impossible-arithmetic classes that the record itself settles.

Of 501 arithmetically impossible contests in the first ATR pass, roughly half
carry their own correction. Neither repair reads the document, and neither is
allowed to guess: each fires only where exactly one answer closes the sum, and
records what it changed and why.

    seat count      a contest whose marks are exactly N x the ballot count,
                    with N different from its recorded seats, has the wrong
                    seat count -- a voter marks a k-seat race up to k times, so
                    total marks land on ballots x k and nowhere else.

    doubled column  a contest whose marks are exactly twice its own printed
                    total has counted one column twice, almost always a
                    per-precinct figure added alongside the total it already
                    contains.

The asymmetry that makes both safe is the one the QA layers rest on. Marks
ABOVE ballots x seats are impossible at any magnitude, so something is
definitely wrong; marks below are ordinary. These only ever fire above the
line, where doing nothing is not the safe option either.

What they deliberately do NOT do is touch a figure. A seat count is metadata
about the contest and can be re-derived from the same evidence tomorrow; a vote
is a transcription, and editing one destroys the only record of what the page
said. Where the doubling cannot be attributed to a specific duplicate row, the
contest is flagged, not rewritten.
"""
import collections
import re

# A ballot question elects nobody, so it has no seat count to print and no
# winner to name. Asking it for one sent 42 records to review for a field that
# does not exist on them. It is still owed the arithmetic -- a voter may mark
# it once, exactly like a single-seat race -- so it is recognised rather than
# exempted, and it can help derive the ballot count like any other contest.
#
# Recognised by its ROWS, not its heading. "QUESTION 1", "Shall the Town of
# Belchertown cease assessing..." and an untitled override all appear as
# headings; what they share is that every row is YES, NO or a role.
_QUESTION_ROW = re.compile(r"^\s*(yes|no|blanks?|write[- ]?ins?|others?|total)\b", re.I)
_YES_OR_NO = re.compile(r"^\s*(yes|no)\b", re.I)


def is_ballot_question(contest):
    names = [(c.get("name_original") or "").strip()
             for c in (contest.get("candidates") or [])]
    return bool(names) and all(_QUESTION_ROW.match(n) for n in names) \
        and any(_YES_OR_NO.match(n) for n in names)


def seats_of(contest):
    """The number of times a voter may mark this contest. None if unknown."""
    return 1 if is_ballot_question(contest) else contest.get("num_winners")


def _countable(contests):
    """The contests the ballot arithmetic may speak about at all."""
    out = []
    for c in contests:
        if not isinstance(c, dict):
            continue
        if not seats_of(c) or c.get("scope") == "regional_district":
            continue
        if _marks(c) is None:
            continue
        out.append(c)
    return out


def ballot_quorum(contests):
    """(ballots, support, dissent). ballots is None when nothing carries.

    Two things have to hold before a modal quotient is a ballot count.

    Two contests must agree -- one is an assertion, not a derivation. And the
    value must not be contradicted by more contests than assert it, because
    `marks <= ballots x seats` holds for every contest in the record, so a
    contest implying MORE ballots than the candidate value is evidence against
    that value rather than a defect in itself.

    Skipping the second test is how Ashburnham 2006 came to be condemned. Two
    Planning Board races tallied 534 each, so 534 was taken as the ballot
    count, and the Moderator (583), Selectmen (683) and Municipal Light Board
    (542) were all reported as arithmetically impossible. The page prints
    "Total Votes Cast = 683": every one of those three was read correctly and
    the derivation was the thing that was wrong. Three contests contradicting
    two is a disagreement about how many ballots were cast, and the honest
    answer to it is that this record cannot say.
    """
    cs = _countable(contests)
    q = collections.Counter()
    for c in cs:
        marks, seats = _marks(c), seats_of(c)
        if marks % seats == 0:
            q[marks // seats] += 1
    if not q:
        return None, 0, 0
    best, support = q.most_common(1)[0]
    dissent = sum(1 for c in cs if _marks(c) > best * seats_of(c))
    # A lone contest above the line is an outlier and the check exists to find
    # it. A LARGER count that carries its own quorum is a second block of the
    # record asserting a different ballot count, and calling the smaller one
    # right condemns the whole of the larger block. Falmouth 2017 closes five
    # office races exactly at 7,243 and all four of its ballot questions
    # exactly at 7,244; the town's two tallies differ by one ballot, and
    # neither the four nor the five is the impossible one.
    rival = any(n >= 2 for cand, n in q.items() if cand > best)
    if support < 2 or dissent >= support or rival:
        return None, support, dissent
    return best, support, dissent


def derive_ballots(contests):
    """Ballots, from contests that agree and are not outvoted. None is real."""
    return ballot_quorum(contests)[0]


def _marks(contest):
    v = [c.get("votes") for c in contest.get("candidates", [])]
    return None if not v or any(x is None for x in v) else sum(v)


def fix_seat_count(contest, ballots):
    """Set seats to N where marks are exactly N x ballots and N != seats.

    Refuses when the contest says its seat count was PRINTED, because a printed
    count outranks the arithmetic and a disagreement there is a finding rather
    than a repair -- the page and the figures cannot both be right, and only
    the page can say which. Those are reported for a human.
    """
    seats, marks = contest.get("num_winners"), _marks(contest)
    if not ballots or not seats or marks is None:
        return None
    if marks <= ballots * seats or marks % ballots:
        return None
    implied = marks // ballots
    if implied == seats or not 1 <= implied <= 20:
        return None
    if contest.get("num_winners_source") == "printed":
        return ("REPORT", implied,
                "marks are exactly %dx ballots but the page is quoted as "
                "printing %d seats: %r" % (implied, seats,
                                           contest.get("seats_quote")))
    return ("FIX", implied,
            "marks %d are exactly %dx the ballot count %d; seats recorded as "
            "%d, source %s" % (marks, implied, ballots, seats,
                               contest.get("num_winners_source")))


def find_doubled_row(contest):
    """The one row whose removal makes the contest sum to its printed total.

    Uniqueness is the safeguard. If two different rows would each close it, the
    arithmetic cannot say which was duplicated and neither can we, so nothing
    is removed. A repair that had to choose would be a guess with a citation.
    """
    total = contest.get("printed_total")
    cands = contest.get("candidates") or []
    marks = _marks(contest)
    if not total or marks is None or marks <= total:
        return None
    excess = marks - total
    hits = [i for i, c in enumerate(cands) if c.get("votes") == excess]
    if len(hits) != 1:
        return None
    return hits[0], cands[hits[0]].get("name_original")
