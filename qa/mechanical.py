"""Repair the classes the record settles by itself.

Of 501 arithmetically impossible contests in the first ATR pass, roughly half
carry their own correction. No repair here reads the document, and none is
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

    ballot question a YES/NO question is not an office and has no seat count to
                    print. The tool schema has a `questions` field of its own,
                    so a question that landed in `elections` is in the wrong
                    field of the same record -- it is moved, never discarded.

    blank figure    a figure the reader left null because the cell was blank or
                    a dash, where the row's own arithmetic supplies it: the
                    row's precinct breakdown, or the contest's printed total
                    less everything else read against it.

The asymmetry that makes the arithmetic repairs safe is the one the QA layers
rest on. Marks ABOVE ballots x seats are impossible at any magnitude, so
something is definitely wrong; marks below are ordinary. Those only ever fire
above the line, where doing nothing is not the safe option either.

A vote is a transcription and editing one destroys the only record of what the
page said, so nothing here overwrites a figure that was read. The blank-figure
repairs fill a hole and only a hole, and each is a sum of figures already on
the page rather than a reading of it. Both refuse in the two ways a blank has
been seen to lie: a row whose precinct breakdown repeats another row's is a
column of the table and not a candidate -- Granby 2015 prints "Sworn" beside
every winner with the winner's own precinct figures against it -- and a
residual against the printed total is taken only for a Blanks or Write-ins row,
whose value is by definition what is left, never for a named person, because a
person's blank is exactly how a dropped candidate looks.
"""
import collections
import re


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


# A question heads itself one. Every one of the 61 found in this corpus prints
# YES and NO where a contest prints people, and every one left its seat count
# null because there is no seat to count. The published 2021-2026 corpus holds
# none at all in 19,642 contests, so a question in `elections` is a field
# error, not a scope judgement to make record by record.
QUESTION = re.compile(
    r"^\s*(BALLOT\s+)?QUESTION\b|^\s*QUESTION\s*[#:]|^\s*REFERENDUM\b|"
    r"\bDEBT\s+EXCLUSION\b|\bSHALL\s+THE\s+TOWN\b|"
    r"\bPROP(OSITION)?\.?\s*2\s*(1/2|½)", re.I)

# The rows that are not people. A return's residual lines carry these names and
# nothing else; a candidate never does.
RESIDUAL_ROW = re.compile(
    r"^[\s/*]*(BLANKS?|BLANK VOTES?|WRITE[\s-]?INS?|\(WRITE[\s-]?IN\)|"
    r"OTHERS?|ALL OTHERS|SCATTER\w*|TOTAL WRITE[\s-]?INS?|MISCELLANEOUS)"
    r"[\s:.*]*$", re.I)


def ballot_question(contest):
    """Is this a ballot question that landed in `elections`?"""
    return bool(QUESTION.search(contest.get("office_original") or "")
                and contest.get("num_winners") is None)


def breakdown_is_precincts_only(contests):
    """(trustworthy, agreeing, disagreeing) for a record's precinct columns.

    Whether `votes_by_precinct` holds precincts alone or carries the total
    column too is a fact about one document's layout, and the document answers
    it: every row that has BOTH a total and a breakdown is a worked example.
    If they all close, a row that has only the breakdown can be summed; if any
    row disagrees, the columns are something else and nothing is summed.
    Belmont 2018's eighth column is its town total, and summing it would have
    doubled every write-in figure in the record.
    """
    agree = disagree = 0
    for c in contests:
        if not isinstance(c, dict):
            continue
        for cand in c.get("candidates") or []:
            bp = cand.get("votes_by_precinct")
            if cand.get("votes") is None or not bp or any(v is None for v in bp):
                continue
            if sum(bp) == cand["votes"]:
                agree += 1
            else:
                disagree += 1
    return (agree >= 2 and disagree == 0), agree, disagree


def sum_from_precincts(contest):
    """[(index, total, note)] for null figures the row's own precincts supply.

    A row repeating another row's breakdown is a column of the table, not a
    candidate, and is refused: that is the one shape where the sum is confident
    and wrong.
    """
    cands = contest.get("candidates") or []
    read = [tuple(c.get("votes_by_precinct") or [])
            for c in cands if c.get("votes") is not None]
    out = []
    for i, cand in enumerate(cands):
        bp = cand.get("votes_by_precinct")
        if cand.get("votes") is not None or not bp:
            continue
        if any(v is None for v in bp) or tuple(bp) in read:
            continue
        out.append((i, sum(bp),
                    "row %r reads %s across its precincts"
                    % (cand.get("name_original"), list(bp))))
    return out


def close_residual_row(contest):
    """(index, total, note) for the one blank Blanks-or-Write-ins row a printed
    total settles. None when the blank is a person's, or when more than one row
    is blank and the residual cannot be attributed."""
    cands = contest.get("candidates") or []
    total = contest.get("printed_total")
    blanks = [i for i, c in enumerate(cands) if c.get("votes") is None]
    if not total or len(blanks) != 1:
        return None
    i = blanks[0]
    if not RESIDUAL_ROW.match(cands[i].get("name_original") or ""):
        return None
    rest = sum(c.get("votes") for j, c in enumerate(cands) if j != i)
    if not 0 <= total - rest <= total:
        return None
    return (i, total - rest,
            "the printed total %d less the %d read on the other rows; the "
            "blank row is %r" % (total, rest, cands[i].get("name_original")))


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
