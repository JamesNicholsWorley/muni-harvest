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


def derive_ballots(contests):
    """Ballots, from contests that agree. Two agreeing is the minimum."""
    q = collections.Counter()
    for c in contests:
        seats = c.get("num_winners")
        if not seats or c.get("scope") == "regional_district":
            continue
        marks = _marks(c)
        if marks is None or marks % seats:
            continue
        q[marks // seats] += 1
    if not q:
        return None
    best, n = q.most_common(1)[0]
    return best if n >= 2 else None


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
