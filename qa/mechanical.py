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
definitely wrong; marks below are ordinary.

Below the line the seat repair fires only where the contest TALLIES ITS BLANKS,
and that condition is doing all the work. A blank is a ballot position left
unmarked, so once blanks are counted the rows account for every position a
voter had, and the sum owes the identity exactly: candidates + blanks =
ballots x seats. Landing on ballots x N for an integer N other than the
recorded seats is then not an under-count, it is the seat count being wrong.
Without a blanks row the same sum says nothing -- marks short of ballots x
seats is the ordinary shape of a return that did not print its blanks, and
reading a seat count out of it would be the tuned threshold this project
refuses.

Amherst 2018 is the shape. Its return prints a TOTAL line under every office:
SELECT BOARD "TOTAL ... 6043" against 6043 ballots, SCHOOL COMMITTEE
"TOTAL ... 12086". The parse recorded three seats and four; the page says one
and two, and its own blanks rows (1531 and 4119) close both sums exactly.

What these deliberately do NOT do is touch a figure. A seat count is metadata
about the contest and can be re-derived from the same evidence tomorrow; a vote
is a transcription, and editing one destroys the only record of what the page
said. Where the doubling cannot be attributed to a specific duplicate row, the
contest is flagged, not rewritten.
"""
import collections
import re

# The two scopes that are not the town. A regional district spans several
# towns, so its marks exceed the town's ballots legitimately; a ward or
# precinct divides one town, so its marks are that precinct's ballots and the
# town's count says nothing about them. Everything else is town-wide,
# INCLUDING a record that does not state a scope: a check that quietly stops
# checking when a field is missing is worse than one that is occasionally
# wrong out loud.
NOT_TOWN_WIDE = ("sub_town", "regional_district")

# The rows that are ballot POSITIONS rather than people. Only these complete
# the identity: a write-in or a scattering row may be present and still leave
# marks short, because an uncounted write-in is exactly what a clerk omits.
# Bedford heads the column "Unused Votes" and Amherst "Blank"; both are the
# same quantity under the town's own word for it.
BLANKS_ROW = re.compile(r"^\s*(blanks?|unused\s+votes?|under\s*votes?|"
                        r"no\s+vote|not\s+voted)\b", re.I)

# Rows that are quantities rather than people. A page may print any of them
# once per precinct, so a repeated one is not a column restated.
ROLE_ROW = re.compile(r"^\s*(blanks?|write[- ]?ins?|all\s+others?|others?|"
                      r"scatter\w*|totals?|unused\s+votes?|under\s*votes?|"
                      r"void|no\s+vote|not\s+voted)\b", re.I)

# A term length wearing a seat count's clothes. Hamilton 2014 heads its races
# "Selectman 3 years", "Town Clerk 3 years", "Housing AuthoritY 5 years", and
# every one of the three closes at exactly 1016 ballots x ONE. The parse
# recorded three seats, three seats and five, sourced "printed", and quoted the
# office line as its evidence -- so the quote is the thing that settles it.
TERM = re.compile(r"\b(\w+|\d+)[\s-]*(year|yr)s?\b", re.I)
# What a page says when it really is stating a seat count.
SEATS_SAID = re.compile(
    r"(vote\s+for|elect\s+|choose|not\s+more\s+than|\(\s*\d+\s*\)|"
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\b|\b\d+\b)", re.I)


def tallies_blanks(contest):
    """True when a row of this contest counts unmarked ballot positions."""
    return any(BLANKS_ROW.match(c.get("name_original") or "")
               for c in contest.get("candidates") or [])


def quotes_a_seat_count(contest):
    """Does the quote behind `num_winners_source: printed` state a seat count?

    A printed count outranks the arithmetic, so the claim is worth a REPORT
    rather than a repair -- but only where the page really printed one. Strip
    the term of office out of the quote first: what is left has to still say
    how many. "Selectman 3 years" says nothing once "3 years" is gone;
    "Planning Board TWO for 5 years" and "Vote for NOT more than Two" both do.
    """
    q = contest.get("seats_quote") or ""
    return bool(SEATS_SAID.search(TERM.sub(" ", q)))


def derive_ballots(contests):
    """Ballots, from MUNICIPALITY-WIDE contests that agree. Two is the minimum.

    Scope decides eligibility in both directions, and both were not covered.
    A regional district spans several towns so its marks exceed the town's
    ballots; a ward or precinct divides one town, so its marks are that
    precinct's ballots and not the town's. Marlborough 2011 derived 847 from
    Councilor Ward Six and Ward Seven agreeing with each other, and then
    reported the city's Mayor -- 6002 marks, which IS the city's ballot count
    -- as arithmetically impossible against it. Only `at_large` answers the
    question being asked.
    """
    q = collections.Counter()
    for c in contests:
        seats = c.get("num_winners")
        if not seats or c.get("scope") in NOT_TOWN_WIDE:
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

    Above the line -- marks over ballots x seats -- the exact multiple is taken
    on its own, because something is definitely wrong there and doing nothing
    is not the safe option either.

    Below the line the contest must tally its blanks first. That is not a
    softer version of the same test, it is what makes the sum mean anything:
    marks short of ballots x seats is the ordinary shape of a return whose
    blanks were never printed, and only a blanks row turns the sum into a
    closed identity that ballots x N can be read out of.

    Refuses either way when the contest says its seat count was PRINTED,
    because a printed count outranks the arithmetic and a disagreement there is
    a finding rather than a repair -- the page and the figures cannot both be
    right, and only the page can say which. Those are reported for a human.
    """
    seats, marks = contest.get("num_winners"), _marks(contest)
    if not ballots or not seats or marks is None:
        return None
    # A ward or precinct contest is bounded by ITS ballots, and the town's
    # count says nothing about how many those were. A regional district
    # exceeds the town's legitimately. Neither can be read against `ballots`.
    if contest.get("scope") in NOT_TOWN_WIDE:
        return None
    if marks % ballots:
        return None
    below = marks < ballots * seats
    if below and not tallies_blanks(contest):
        return None
    implied = marks // ballots
    if implied == seats or not 1 <= implied <= 20:
        return None
    where = ("under ballots x seats with blanks tallied" if below
             else "over ballots x seats")
    printed = contest.get("num_winners_source") == "printed"
    if printed and quotes_a_seat_count(contest):
        return ("REPORT", implied,
                "marks are exactly %dx ballots but the page is quoted as "
                "printing %d seats: %r" % (implied, seats,
                                           contest.get("seats_quote")))
    why = ("source %s" % contest.get("num_winners_source") if not printed else
           "sourced printed, but the quote %r states a term and not a seat "
           "count" % (contest.get("seats_quote") or ""))
    return ("FIX", implied,
            "marks %d are exactly %dx the ballot count %d (%s); seats "
            "recorded as %d, %s"
            % (marks, implied, ballots, where, seats, why))


def find_doubled_row(contest):
    """The rows whose removal makes the contest sum to its printed total.

    A NAME REPEATED inside one contest is looked for first, because a candidate
    appears once and a column appears against every candidate. Fairhaven prints
    "SUB TOT" and "TOTAL" side by side with a "Hand Counts" line between them,
    and the parse read the TOTAL column -- which already contains the hand
    counts -- and then read each Hand Counts line as a candidate as well. Its
    School Committee sums to 3350 against a printed 3346, and the four are the
    three Hand Counts rows.

    Reading that as a single doubled row is how the repair went wrong: the
    excess there was 2, no Hand Counts row held 2, and Selectman's genuine
    Write-Ins row did -- so the one repair that fired deleted two real
    write-in votes and left the duplication in place. Removing the repeated
    label as a group closes both, and the sum closing exactly is what says the
    printed total already contained them.

    Ballot-role rows are never removable this way. A page may print Blanks or
    Write-ins once per precinct, and those are quantities rather than a column
    restated.

    Uniqueness remains the safeguard for the single-row case. If two different
    rows would each close it, the arithmetic cannot say which was duplicated
    and neither can we, so nothing is removed. A repair that had to choose
    would be a guess with a citation.
    """
    total = contest.get("printed_total")
    cands = contest.get("candidates") or []
    marks = _marks(contest)
    if not total or marks is None or marks <= total:
        return None
    excess = marks - total

    seen = collections.Counter(
        (c.get("name_original") or "").strip().lower() for c in cands)
    restated = {n for n, k in seen.items()
                if k > 1 and n and not ROLE_ROW.match(n)}
    if restated:
        group = [i for i, c in enumerate(cands)
                 if (c.get("name_original") or "").strip().lower() in restated]
        if sum(cands[i].get("votes") or 0 for i in group) == excess:
            return group, "/".join(sorted(restated))

    hits = [i for i, c in enumerate(cands) if c.get("votes") == excess]
    if len(hits) != 1:
        return None
    return hits, cands[hits[0]].get("name_original")
