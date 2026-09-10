"""Tests for the pre-2021 ATR path.

Each case is a thing the corpus cost something to learn, written so that
un-learning it fails loudly rather than quietly changing a number.
"""
import pymupdf
import pytest

from qa import atr_bridge, atr_gate, escalate, mechanical
from tools import atr_sections, text_arith, warrant, zones


# ------------------------------------------------------------------ arithmetic

def test_ballots_derived_from_races_of_different_sizes():
    """Danvers 2020: one seat 1807, two seats 3614, three seats 5421."""
    assert text_arith.derive_ballots([(1807, 1), (3614, 2), (5421, 3)]) == 1807


def test_two_races_that_disagree_are_not_a_derivation():
    assert text_arith.derive_ballots([(1807, 1), (9999, 1)]) is None


def test_one_race_is_not_a_quorum():
    assert text_arith.derive_ballots([(1807, 1)]) is None


def test_implied_seats_cross_checks_a_seat_count():
    assert text_arith.implied_seats(3614, 1807) == 2
    assert text_arith.implied_seats(5421, 1807) == 3


def test_a_unique_split_repairs_a_bled_row():
    parts = [5047, 22, 62, 43, 49, 33, 26]
    fixed, why = text_arith.repair_row(parts, 332)
    assert fixed == [50, 47, 22, 62, 43, 49, 33, 26]
    assert "split" in why


def test_an_ambiguous_split_is_refused():
    """Two different splits closing the same row is not a repair.

    The safeguard is the whole point: a repair that had to choose between
    candidates would be a guess wearing the costume of a proof.
    """
    fixed, why = text_arith.repair_row([11, 11], 3)
    assert fixed is None


def test_a_row_that_already_closes_is_left_alone():
    parts = [50, 47, 22, 62, 43, 49, 33, 26]
    fixed, why = text_arith.repair_row(parts, 332)
    assert fixed == parts and why == "already closes"


# ------------------------------------------------------------------- escalation

def _contest(office, seats, votes, **kw):
    c = {"office_original": office, "num_winners": seats,
         "num_winners_source": kw.pop("source", "printed"),
         "candidates": [{"name_original": n, "votes": v} for n, v in votes]}
    c.update(kw)
    return c


def test_a_clean_record_is_accepted():
    rec = {"elections": [
        _contest("Moderator - 1 for 1 Year", 1,
                 [("PATRICIA C. FRAIZER", 332), ("WRITE INS", 147), ("BLANKS", 1328)]),
        _contest("Selectmen - 1 for 3 Years", 1,
                 [("MATTHEW E. DUGGAN", 575), ("TIMOTHY TREVOR DONAHUE", 454),
                  ("MAUREEN A. BERNARD", 732), ("WRITE INS", 36), ("BLANKS", 10)])]}
    assert escalate.review(rec)[0] == "accept"


def test_marks_exceeding_ballots_times_seats_escalates():
    rec = {"elections": [
        _contest("A", 1, [("X", 500), ("BLANKS", 500)]),
        _contest("B", 1, [("Y", 600), ("BLANKS", 400)]),
        _contest("C", 1, [("Z", 5000)])]}
    verdict, reasons = escalate.review(rec)
    assert verdict == "escalate"
    assert any("impossible" in r for r in reasons)


def test_marks_below_the_product_do_not_escalate():
    """Under is the legitimate direction -- blanks and uncounted write-ins."""
    rec = {"elections": [
        _contest("A", 1, [("X", 500), ("BLANKS", 500)]),
        _contest("B", 1, [("Y", 600), ("BLANKS", 400)]),
        _contest("C", 1, [("Z", 700)])]}
    assert escalate.review(rec)[0] == "accept"


def test_a_regional_district_contest_is_exempt_from_the_arithmetic():
    """Its figures routinely exceed the host town's ballots, legitimately."""
    rec = {"elections": [
        _contest("A", 1, [("X", 500), ("BLANKS", 500)]),
        _contest("B", 1, [("Y", 600), ("BLANKS", 400)]),
        _contest("Wachusett Regional", 2, [("R", 9000)], scope="regional_district")]}
    assert escalate.review(rec)[0] == "accept"


def test_a_null_seat_count_escalates_rather_than_publishing():
    rec = {"elections": [
        _contest("A", 1, [("X", 500), ("BLANKS", 500)]),
        _contest("B", 1, [("Y", 600), ("BLANKS", 400)]),
        _contest("C", None, [("Z", 700)], source=None)]}
    verdict, reasons = escalate.review(rec)
    assert verdict == "escalate"
    assert any("null" in r for r in reasons)


def test_an_empty_name_escalates_even_when_the_figures_close():
    """Needham: the sum was exact and a candidate had been dropped entirely."""
    rec = {"elections": [
        _contest("A", 1, [("X", 500), ("BLANKS", 500)]),
        _contest("B", 1, [("", 600), ("BLANKS", 400)])]}
    verdict, reasons = escalate.review(rec)
    assert verdict == "escalate"
    assert any("no name" in r for r in reasons)


def test_a_recount_does_not_drag_the_record_into_escalation():
    """Sterling 2010 recounted one office three weeks later."""
    rec = {"elections": [
        _contest("A", 1, [("X", 500), ("BLANKS", 500)]),
        _contest("B", 1, [("Y", 600), ("BLANKS", 400)]),
        _contest("A recount", 1, [("X", 501)], is_recount=True)]}
    assert escalate.review(rec)[0] == "accept"


def test_a_state_office_says_the_section_is_the_wrong_election():
    """Ayer 2010 published eleven contests -- Governor and Lieutenant
    Governor, Attorney General, Secretary of State, Sheriff -- and the
    section's own first line reads "Ayer Massachusetts Democratic Party
    Primary Election Results for Tuesday, September 14, 2010". Billerica 2020
    published the presidential primary: "PRESIDENT -Vote for One", Warren
    1124, Sanders, Bloomberg.

    No name test could have caught either. Both are the town's own report,
    headed with the town's name, printing the town's precincts.
    """
    doc = {"elections": [
        _contest("Governor and Lieutenant Governor", 1, [("A", 2577)]),
        _contest("Attorney General", 1, [("B", 2577)]),
        _contest("Moderator", 1, [("C", 2577)])]}
    rung, why = atr_gate.grade(doc)
    assert rung == "hold" and "state or county office" in why[0]


def test_a_section_supporting_almost_nothing_is_the_wrong_document():
    """Carver 2014 published thirteen contests with names against them, cut
    from the report's own INDEX page -- "Elections: Annual Town Election
    Results, 4/26/14" -- where none of those names or figures appear. Layer 1
    located 0 of 13 names and 0 of 22 figures.

    Barnstable 2018's section is the Town Clerk's vital statistics ("831
    Births in Barnstable"), Wilbraham 2018's the town meeting warrant, and
    Scituate 2017's the SPECIAL TOWN ELECTION of September 16 -- a real
    return, of a different election than the record describes.
    """
    doc = {"elections": [_contest("SELECTMEN", 1, [("A", 10), ("BLANKS", 5)])]}
    rung, why = atr_gate.grade(doc, {"names": "0/13", "figures": "0/22"})
    assert rung == "hold" and "supports almost none" in why[0]


def test_a_record_whose_figures_all_ground_is_not_the_wrong_document():
    """Westford 2010 locates 2 of 10 names and 20 of 20 figures. That is a
    spelling problem, and holding it here would make the floor a bar."""
    assert atr_gate.supports_almost_nothing(
        {"names": "2/10", "figures": "20/20"}) is None
    # 147 published records locate most but not all of their names.
    assert atr_gate.supports_almost_nothing(
        {"names": "16/18", "figures": "31/33"}) is None
    # A scan carries no text to match against and says so, not zero.
    assert atr_gate.supports_almost_nothing(
        dict.fromkeys(("names", "figures"),
                      "no text held for this section")) is None
    # Too few of either to mean anything.
    assert atr_gate.supports_almost_nothing(
        {"names": "0/2", "figures": "0/3"}) is None


def test_a_city_councillor_is_not_a_governors_councillor():
    """Marlborough elects Councilor Ward One and Methuen a West District
    Councillor, and Gardner a Ward 1 Councilor. All three are municipal, and
    a test that read the word alone held every city in the corpus."""
    for office in ("COUNCILOR WARD ONE", "WEST DISTRICT COUNCILLOR",
                   "Ward 1 Councilor", "COUNCILOR-AT-LARGE",
                   "TOWN TREASURER", "Town Auditor"):
        assert not atr_gate.state_offices(
            [_contest(office, 1, [("A", 10)])]), office


def test_a_ballot_question_naming_the_governor_is_still_a_ballot_question():
    """Falmouth 2017 asked its voters to direct the Selectmen to communicate
    with the Governor of the Commonwealth about spent nuclear fuel."""
    question = ("Question Four: Shall the Town of Falmouth vote to direct the "
                "Board of Selectmen to communicate with the Governor of the "
                "Commonwealth of Massachusetts to employ all means available "
                "to ensure spent nuclear fuel generated by the Pilgrim "
                "Nuclear Power Station be placed in secure dry casks")
    assert not atr_gate.state_offices([_contest(question, None, [("YES", 10)])])


def test_a_ward_never_answers_how_many_ballots_the_town_cast():
    """Marlborough 2011. Seven ward councillor races, one seat each; Ward Six
    and Ward Seven both total 847, so they agreed with each other and 847 was
    taken for the city's ballot count. The city's Mayor race totals 6002 in a
    single-seat contest -- which IS the ballot count -- and was reported
    impossible against a ward's.

    A ward divides the town exactly as a regional district exceeds it, and
    only the first was excluded.
    """
    rec = {"elections": [
        _contest("COUNCILOR WARD SIX", 1, [("A", 847)], scope="sub_town"),
        _contest("COUNCILOR WARD SEVEN", 1, [("B", 847)], scope="sub_town"),
        _contest("MAYOR", 1, [("C", 4000), ("BLANKS", 2002)], scope="at_large"),
        _contest("SCHOOL COMMITTEE", 3, [("D", 18005)], scope="at_large"),
        _contest("ASSABET VALLEY SCHOOL COMMITTEE", 1, [("E", 6002)],
                 scope="regional_district")]}
    # One town-wide contest divides cleanly, and one is not a quorum. Nothing
    # is derived, which is the honest answer and not a licence to use a ward.
    assert escalate.derive_ballots(rec["elections"]) is None
    assert not [r for r in escalate.review(rec)[1] if "impossible" in r]


def test_a_town_that_prints_only_precinct_races_cannot_derive_its_ballots():
    """Framingham 2015 is nothing but Town Meeting Members by precinct. Two
    precincts totalling 91 agreed with each other and 91 became the town's
    ballot count. "Cannot derive" is the honest answer."""
    rec = {"elections": [
        _contest("Town Meeting Members Precinct 9 (One 1 year seat)", 1,
                 [("A", 91)], scope="sub_town"),
        _contest("Town Meeting Members Precinct 13 (One 2 year seat)", 1,
                 [("B", 91)], scope="sub_town"),
        _contest("Town Meeting Members Precinct 7", 4, [("C", 804)],
                 scope="sub_town")]}
    assert escalate.derive_ballots(rec["elections"]) is None
    assert not [r for r in escalate.review(rec)[1] if "impossible" in r]


# ------------------------------------------------------------ seat count repair

def test_a_seat_count_under_the_line_is_only_read_where_blanks_are_tallied():
    """Amherst 2018, page 1 of its section, verbatim.

        SELECT BOARD
        Robert E. Greeney ... 1572
        Ivan B. Babian ... 469
        Douglas Wesley Slaughter ... 2449
        All Others ... 22
        Blank ... 1531
        TOTAL ... 6043

    6043 is the ballot count -- MODERATOR and HOUSING AUTHORITY both close on
    it. The parse recorded three seats for a race the page totals at exactly
    one times ballots, and its own blanks row closes the sum, so the sum is a
    closed identity and the seat count is the thing that is wrong.

    Strip the blanks row and the same figures say nothing: marks short of
    ballots x seats is the ordinary shape of a return whose blanks were never
    printed, and nothing may be repaired off it.
    """
    rows = [("Robert E. Greeney", 1572), ("Ivan B. Babian", 469),
            ("Douglas Wesley Slaughter", 2449), ("All Others", 22)]
    with_blanks = _contest("SELECT BOARD", 3, rows + [("Blank", 1531)],
                           source="derived")
    assert mechanical.fix_seat_count(with_blanks, 6043)[:2] == ("FIX", 1)
    assert mechanical.fix_seat_count(
        _contest("SELECT BOARD", 3, rows, source="derived"), 4512) is None


def test_bedford_calls_its_blanks_unused_votes():
    """Bedford 2007: "Times counted 1236", "Unused Votes 172", four candidates
    and 412 ballots. The row is a blanks row under the town's own word."""
    c = _contest("LIBRARY TRUSTEE", 4,
                 [("SARAH S. GETTY", 293), ("ABIGAIL A. HAFER", 334),
                  ("RACHEL FIELD", 206), ("HOWARD D. COHEN", 229),
                  ("Unused Votes", 172), ("Write-in votes", 2)],
                 source="derived")
    assert mechanical.fix_seat_count(c, 412)[:2] == ("FIX", 3)


def test_a_term_of_office_quoted_as_a_seat_count_is_not_one():
    """Hamilton 2014 heads three races "Selectman 3 years", "Town Clerk 3
    years" and "Housing AuthoritY 5 years", and every one of them closes at
    exactly 1016 ballots x ONE. The parse called all three `printed` and
    quoted the office line as the evidence, so the quote is what settles it:
    with "3 years" removed it states no count at all.

    "Planning Board TWO for 5 years" is the same page saying it properly, and
    stays a REPORT for a human rather than being repaired.
    """
    term = _contest("Selectman 3 years", 3,
                    [("Jeffrey Miles Hubbard", 513), ("Shawn M. Farrell", 494),
                     ("Write-ins", 2), ("Blanks", 7)],
                    source="printed", seats_quote="Selectman 3 years")
    assert mechanical.fix_seat_count(term, 1016)[:2] == ("FIX", 1)

    said = _contest("Planning Board TWO for 5 years", 3,
                    [("Edwin M. Howard, Jr.", 666),
                     ("Claudia Allison Woods", 664), ("Write-ins", 6),
                     ("Blanks", 696)],
                    source="printed",
                    seats_quote="Planning Board TWO for 5 years")
    assert mechanical.fix_seat_count(said, 1016)[:2] == ("REPORT", 2)


def test_a_column_restated_against_every_candidate_is_removed_as_a_group():
    """Fairhaven 2016 prints SUB TOT and TOTAL side by side with a Hand Counts
    line between them, and the parse read the TOTAL column -- which already
    contains the hand counts -- and each Hand Counts line as well.

        Stacia A. Powers      909  Hand Counts 0
        Tatiana N. Andrade    496  Hand Counts 1
        Michael McNamara      890  Hand Counts 3
        Write-In                3
        Blanks               1048
        TOTAL                3346

    The sum is 3350. Removing the repeated label as a group closes it; no
    single row holds the excess of 4, which is what the earlier rule looked
    for.
    """
    c = _contest("School Committee - 3 years", 2,
                 [("Stacia A. Powers", 909), ("Hand Counts", 0),
                  ("Tatiana N. Andrade", 496), ("Hand Counts", 1),
                  ("Michael McNamara", 890), ("Hand Counts", 3),
                  ("Write-In", 3), ("Blanks", 1048)],
                 printed_total=3346)
    idx, label = mechanical.find_doubled_row(c)
    assert [c["candidates"][i]["name_original"] for i in idx] == \
        ["Hand Counts"] * 3


def test_a_repeated_column_is_preferred_over_a_real_row_holding_the_excess():
    """The same page's Selectman race is how the single-row rule went wrong.
    Its excess is 2, no Hand Counts row holds 2, and the genuine Write-Ins row
    does -- so the repair that fired deleted two real write-in votes and left
    the duplication in place."""
    c = _contest("Selectman - 3 years", 1,
                 [("Geoffrey A. Haworth, II", 387), ("Hand Counts", 0),
                  ("Daniel C. Freitas", 580), ("Hand Counts", 1),
                  ("Patricia A. Pacella", 162), ("Hand Counts", 1),
                  ("Bernard F. Rodericks", 526), ("Hand Counts", 0),
                  ("Write-Ins", 2), ("Blanks", 16)],
                 printed_total=1673)
    idx, label = mechanical.find_doubled_row(c)
    assert "Write-Ins" not in [c["candidates"][i]["name_original"] for i in idx]
    assert label == "hand counts"


def test_a_ballot_role_printed_per_precinct_is_never_removed():
    """Blanks and Write-ins are quantities, and a page may print either once
    per precinct. Repetition there says nothing about a restated column."""
    c = _contest("MODERATOR", 1,
                 [("JOHN SMITH", 300), ("Blanks", 20), ("Blanks", 30),
                  ("Write-ins", 5)],
                 printed_total=300)
    assert mechanical.find_doubled_row(c) is None


def test_a_seat_count_nobody_could_establish_is_filled_from_the_page():
    """Amherst 2016's Charter Commission runs nineteen candidates and prints
    "Blank 7666 / TOTAL 31419" against 3491 ballots. 31419 is 3491 x 9
    exactly, and a Massachusetts charter commission is nine members.

    The transcriber left the seat count null, which is the honest answer and
    was treated as a reason to buy the parse again. Filling it from the sum is
    strictly weaker than the repair that already OVERWRITES a stated count on
    the same evidence: a fill contradicts nothing.
    """
    c = _contest("CHARTER COMMISSION", None,
                 [("Andrew M. Churchill", 1662), ("Nicholas P. Grabbe", 1519),
                  ("Diana B. Stein", 1442), ("Irvin E. Rhodes", 1439),
                  ("the other fifteen", 17659), ("All Others", 32),
                  ("Blank", 7666)], source=None)
    assert mechanical.fix_seat_count(c, 3491)[:2] == ("FIX", 9)


def test_a_ballot_question_is_not_given_a_seat_count():
    """Acushnet heads one "QUESTION I", Belchertown "Question: Shall the Town
    of Belchertown...", Falmouth writes hers out in full. What they have in
    common is on the rows and not the title: they are answered yes or no.

    A question has no seats, so a null one is right. Demanding it held 59
    correctly-read questions out of the corpus, and filling it would invent a
    field the page never had.
    """
    q = _contest("QUESTION I", None,
                 [("YES", 200), ("NO", 150), ("Blanks:", 45)], source=None)
    assert mechanical.is_ballot_question(q)
    assert mechanical.fix_seat_count(q, 395) is None
    assert not [r for r in escalate.review({"elections": [
        q,
        _contest("MODERATOR", 1, [("A", 300), ("BLANKS", 95)]),
        _contest("SELECTMEN", 1, [("B", 250), ("BLANKS", 145)]),
    ]})[1] if "seat count" in r]


def test_a_race_between_people_named_no_one_is_not_a_question():
    """Only rows that say yes or no make a question. A contest with names on
    it still owes a seat count."""
    c = _contest("SELECTMEN", None,
                 [("Noel P. Given", 300), ("Yesenia Cruz", 200),
                  ("BLANKS", 95)], source=None)
    assert not mechanical.is_ballot_question(c)


def test_a_printed_vote_for_still_outranks_the_arithmetic():
    """Brookline 2016: "SELECTMEN - For Three Years / Vote for NOT more than
    Two", one candidate, and a printed TOTAL of 2287 against 2287 ballots. The
    page and the figures cannot both be right and only the page can say which,
    so this is reported and never rewritten."""
    c = _contest("SELECTMEN - For Three Years", 2,
                 [("NEIL A. WISHINSKY", 1751), ("Write-in votes", 23),
                  ("Blanks", 513)],
                 source="printed", seats_quote="Vote for NOT more than Two")
    assert mechanical.fix_seat_count(c, 2287)[0] == "REPORT"


# ------------------------------------------------------------------------- date

def test_the_formats_a_clerk_actually_uses_are_dates():
    """Every one of these was on a page and reported as unreadable, and the
    record was withheld for it. The quote is the heading in each case.

        Medfield 2003   "Town Of Medfield / Election Results / 31-Mar-03"
        Bourne 2018     "Town Election / 15-May-18 / Town of Bourne"
        Barnstable 2014 "TOWN OF BARNSTABLE ELECTION RESULTS / DATE / 11/5/13"
        Maynard 2019    "MAYNARD TOWN ELECTION - 7 MAY 2019"
        Conway 2017     "adjourned until Thursday, 11 May 2017"
        Foxborough 2016 "ANNUAL TOWN ELECTION / Monday, the Second Day of
                         May, 2016"
        Natick 2016     "TUESDAY, THE TWENTY NINTH DAY OF MARCH 2016"
    """
    for printed, want in (("31-Mar-03", "2003-03-31"),
                          ("15-May-18", "2018-05-15"),
                          ("4-Apr-17", "2017-04-04"),
                          ("11/5/13", "2013-11-05"),
                          ("5-18-09", "2009-05-18"),
                          ("7 MAY 2019", "2019-05-07"),
                          ("11 May 2017", "2017-05-11"),
                          ("Monday, the Second Day of May, 2016", "2016-05-02"),
                          ("TUESDAY, THE TWENTY NINTH DAY OF MARCH 2016",
                           "2016-03-29"),
                          ("Saturday, the Eighth Day of May, 2010",
                           "2010-05-08")):
        assert atr_bridge.iso_date(printed, 2016)[0] == want, printed


def test_a_page_that_prints_no_day_still_prints_no_day():
    """The point of the field is to disagree with the filename, so a year on
    its own is not a date and must not become one."""
    for printed in ("April, 2007", "2019", "<UNKNOWN>", "APRIL 5TH",
                    "2010 Local Election Results", "November of 2015"):
        assert atr_bridge.iso_date(printed, 2016)[0] is None, printed


def test_a_misread_year_is_still_refused():
    """Sudbury read 1974 and Winchester 2107, and both would have published a
    town-year with no election in it."""
    assert atr_bridge.iso_date("March 25, 1974", 2014)[0] is None
    assert atr_bridge.iso_date("March 28, 2107", 2005)[0] is None


# --------------------------------------------------------------------- locating

def test_ballot_vocabulary_outranks_a_warrant_full_of_offices():
    """The shape that put warrants, contents pages and officers directories
    into 317 of the cuts. The warrant names more offices and heads itself an
    election just as loudly; only the return prints Blanks and Write-ins."""
    warrant_page = (
        "ANNUAL TOWN ELECTION\nTo see if the Town will vote to choose the "
        "following officers:\nMODERATOR\nSELECTMEN\nASSESSOR\nTOWN CLERK\n"
        "SCHOOL COMMITTEE\nPLANNING BOARD\nBOARD OF HEALTH\nCONSTABLE\n"
        "LIBRARY TRUSTEE\nCEMETERY COMMISSION\n")
    return_page = (
        "ANNUAL TOWN ELECTION\nSELECTMEN\nJOHN SMITH 900\nJANE DOE 800\n"
        "Blanks 107\nWrite-ins 12\nTotal Votes 1819\nPrecinct 1 2 3\n")
    scored = atr_sections.score_pages(None, [warrant_page, return_page])
    assert scored[0][1] == 1, scored


def test_a_state_primary_page_ranks_below_the_towns_own_election():
    """Bolton 2009's report prints "SPECIAL STATE PRIMARY ELECTION / December
    8, 2009" and its own May town election. The state page carries MORE ballot
    vocabulary, so ranking on that alone moved the cut onto it."""
    state = ("SPECIAL STATE PRIMARY ELECTION\nDecember 8, 2009\n"
             "SENATOR IN CONGRESS\nPrecinct 1 2\nBlanks 12\nWrite-ins 3\n"
             "Total Votes 1450\nMARTHA COAKLEY 700\nSCOTT P BROWN 735\n")
    town = ("ANNUAL TOWN ELECTION\nMay 11, 2009\nSELECTMAN\nBlanks 20\n"
            "Write-ins 1\nTotal Votes 900\nJANE ROE 879\n")
    scored = atr_sections.score_pages(None, [state, town])
    assert scored[0][1] == 1, scored


def test_a_page_with_no_ballot_words_still_falls_back_on_the_old_score():
    """Hawley's return is nine offices, nine names and not one figure,
    because every race was uncontested. Nothing about the ranking may reach
    it: where no page holds ballot vocabulary the old order is unchanged."""
    hawley = ("Annual Town Election Results: May 5, 2025\n"
              "Selectmen/Board of Health - 3 years    Hussain Hamdan\n"
              "Assessor - 3 years    Ed Brady\nTown Clerk - 3 years  A Nurse\n"
              "Moderator - 1 year    P Perkins\nConstable - 3 years  R Sears\n")
    thin = "TOWN ELECTION\nMODERATOR\nSELECTMEN\nASSESSOR\n"
    scored = atr_sections.score_pages(None, [thin, hawley])
    assert scored and scored[0][1] == 1, scored


# ---------------------------------------------------------------------- warrant

def test_a_warrant_is_recognised_and_a_return_is_not():
    warrant_text = (
        "TOWN WARRANT\nGreeting:\nYou are hereby directed to notify the "
        "inhabitants qualified to vote in town elections to bring in their "
        "votes for the following officers:\nModerator for one year\n"
        "Selectman for three years\nAssessor for three years\n")
    return_text = (
        "ANNUAL TOWN ELECTION\nSELECTMEN\nTotal Votes 1807\nJOHN SMITH 900\n"
        "JANE DOE 800\nBlanks 107\nWrite-ins 12\nPrecinct 1 2 3 4\n")
    hits = dict((i, s) for i, s in warrant.find([warrant_text, return_text]))
    assert 0 in hits and 1 not in hits


# ------------------------------------------------------------------------ zones

def _page_with_two_races():
    """Two races side by side, separated by a wide gutter.

    Deliberately more than 25 words: `gutters` refuses to read whitespace as
    structure on a sparse page, because on a page with a handful of words every
    gap is full-height and none of them means anything.
    """
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=400)
    left = [("MODERATOR ONE YEAR", 40), ("JOHN A SMITH 120", 60),
            ("MARY B JONES 80", 80), ("PETER C ADAMS 44", 100),
            ("SUSAN D CLARK 31", 120), ("WRITE INS 6", 140),
            ("BLANKS 15", 160), ("TOTAL VOTES 296", 180)]
    right = [("TOWN CLERK THREE YEARS", 40), ("ALICE E BROWN 150", 60),
             ("ROBERT F GREEN 60", 80), ("HELEN G WHITE 42", 100),
             ("DAVID H BLACK 33", 120), ("WRITE INS 6", 140),
             ("BLANKS 5", 160), ("TOTAL VOTES 296", 180)]
    for text, y in left:
        page.insert_text((40, y), text, fontsize=9)
    for text, y in right:
        page.insert_text((360, y), text, fontsize=9)
    return doc, page


def test_two_races_side_by_side_are_split_into_zones():
    doc, page = _page_with_two_races()
    text, nzones = zones.zone_text(page)
    assert nzones >= 2
    # No output line may carry a candidate from each race.
    for line in text.splitlines():
        assert not ("SMITH" in line and "BROWN" in line)


def test_best_text_reports_which_reading_it_returned():
    doc, page = _page_with_two_races()
    text, how, _ = zones.best_text(page)
    assert how in ("zoned", "raw")
    assert text.strip()


# ------------------------------------------------------------------- importable

def test_every_tool_entrypoint_imports_as_a_script():
    """Run each tool the way CI runs it, not the way a test imports it.

    `atr_warrant_sweep.py` passed a syntax check, was committed, and then
    failed on all fifteen runners with `ModuleNotFoundError: No module named
    'tools'` -- because `python tools/x.py` puts tools/ on sys.path and not the
    repository root. Parsing a file does not execute its imports, so the check
    that passed could never have caught it.
    """
    import pathlib
    import subprocess
    import sys

    root = pathlib.Path(__file__).resolve().parent.parent
    for name in ("atr_sections.py", "atr_warrant_sweep.py", "make_text.py",
                 "parse_run.py", "text_arith.py", "warrant.py", "zones.py"):
        path = root / "tools" / name
        r = subprocess.run(
            [sys.executable, "-c",
             f"import runpy,sys; sys.argv=['{name}','--help'];"
             f" exec(compile(open(r'{path}').read(), r'{path}', 'exec'),"
             f" {{'__name__':'__not_main__','__file__':r'{path}'}})"],
            capture_output=True, text=True, cwd=str(root), timeout=120)
        assert "ModuleNotFoundError" not in r.stderr, f"{name}: {r.stderr[-300:]}"
        assert "ImportError" not in r.stderr, f"{name}: {r.stderr[-300:]}"
