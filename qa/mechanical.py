"""Repairs a record settles by itself, and one the page has to confirm.

Each fires only where exactly one answer closes the sum, and records the
numbers that justify it so a reviewer can disagree with any single row.

    seat count      a contest whose marks are exactly N x the ballot count,
                    with N different from its recorded seats, has the wrong
                    seat count -- a voter marks a k-seat race up to k times, so
                    total marks land on ballots x k and nowhere else.

    doubled column  a contest whose marks are exactly twice its own printed
                    total has counted one column twice, almost always a
                    per-precinct figure added alongside the total it already
                    contains.

    no seat count   where the page printed none at all, the same arithmetic is
                    the only evidence there is, and it beats publishing a null
                    that says the race was decided by nobody. Above one seat it
                    has to be coherent with the rows.

    one blank cell  a contest with exactly one unreadable row and a printed
                    total has that row determined.

The asymmetry that makes the first three safe is the one the QA layers rest on.
Marks ABOVE ballots x seats are impossible at any magnitude, so something is
definitely wrong; marks below are ordinary.

The fourth is different in kind and is the one that needs the document. A seat
count is metadata and can be re-derived from the same evidence tomorrow; a vote
is a transcription, and a value invented in a blank cell is the one error
arithmetic can never catch. So a figure is only ever written where the page
prints it too -- of 130 contests the arithmetic settles, the page agrees with
93 and prints something else for 25, and those 25 stay unreadable.

Where a doubling cannot be attributed to a specific duplicate row, the contest
is flagged, not rewritten.
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
# A row may be prefixed with a winner marker -- Belchertown 2011 prints
# "* YES 1430" -- so the leading punctuation is stepped over rather than
# anchored on. Without that the question read as a one-seat race and had a seat
# count derived for it, which is a claim that somebody was elected.
_QUESTION_ROW = re.compile(r"^[^A-Za-z]*(yes|no|blanks?|write[- ]?ins?|others?|total)\b", re.I)
_YES_OR_NO = re.compile(r"^[^A-Za-z]*(yes|no)\b", re.I)
_QUESTION_HEADING = re.compile(r"^\s*(ballot\s+)?question\b|^\s*shall\s+the\b|"
                               r"^\s*proposition\b", re.I)


def is_ballot_question(contest):
    if _QUESTION_HEADING.match(contest.get("office_original") or ""):
        return True
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


ROLE_ROW = re.compile(r"^\s*(blanks?|write[- ]?ins?|all\s+others?|others?|totals?|"
                      r"scatter\w*|vacancy)", re.I)


def fill_unreadable_figure(contest, text):
    """The one figure the printed total accounts for, if the page prints it too.

    A contest with exactly one unreadable row and a printed total has that row
    determined: total minus the rest, and nothing else closes it. That is
    arithmetic, and arithmetic alone is not enough to write a VOTE -- a figure
    is a transcription, and the one error arithmetic can never catch is a value
    invented in a blank cell.

    So the derived figure has to be printed on the page before it is written.
    Measured over this corpus the difference is not academic: of 130 contests
    the arithmetic settles, the page prints the derived figure for 93 and
    prints something else for 25. Those 25 stay unreadable, which is the
    answer the transcriber gave and a truer one than a number that closes a sum
    the page disagrees with.
    """
    cands = contest.get("candidates") or []
    total = contest.get("printed_total")
    if total is None or text is None:
        return None
    missing = [i for i, c in enumerate(cands) if c.get("votes") is None]
    if len(missing) != 1:
        return None
    rest = sum(c.get("votes") or 0 for c in cands if c.get("votes") is not None)
    value = total - rest
    if value < 0:
        return None
    from qa import layers
    if not layers.figure_found(value, text):
        return None
    return missing[0], value


def derive_seat_count(contest, ballots):
    """Seats for a contest that never printed them, from where its marks land.

    A voter marks a k-seat race up to k times, so total marks land on
    ballots x k and nowhere else. Where a contest tallies exactly that and the
    page printed no seat count at all, the arithmetic is the only evidence
    there is -- and it is better evidence than a null, which publishes nothing
    and says the race was decided by nobody.

    It is still the field that decides who won, so k above one has to be
    coherent with the rows: a two-seat race printing one candidate and tallying
    exactly twice the ballots is a coincidence, not a derivation.
    """
    if contest.get("num_winners") is not None or is_ballot_question(contest):
        return None
    marks = _marks(contest)
    if not ballots or not marks or marks % ballots:
        return None
    k = marks // ballots
    if not 1 <= k <= 20:
        return None
    real = sum(1 for c in (contest.get("candidates") or [])
               if not ROLE_ROW.match((c.get("name_original") or "").strip()))
    if k > 1 and real < k:
        return None
    return k


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
