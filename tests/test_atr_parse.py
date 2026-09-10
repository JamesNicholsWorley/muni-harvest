"""Tests for the pre-2021 ATR path.

Each case is a thing the corpus cost something to learn, written so that
un-learning it fails loudly rather than quietly changing a number.
"""
import pymupdf
import pytest

from qa import escalate
from tools import text_arith, warrant, zones


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


def test_a_quorum_its_own_record_outvotes_is_not_a_ballot_count():
    """Ashburnham 2006, whose page prints "Total Votes Cast = 683".

    Two Planning Board races tallied 534 each, so 534 was taken as the ballot
    count and three correctly-read contests -- Moderator 583, Selectmen 683,
    Municipal Light Board 542 -- were reported as arithmetically impossible.
    Three contradicting two is a disagreement about how many ballots were cast,
    not three impossible contests.
    """
    rec = {"elections": [
        _contest("One Planning Board - For five year term", 1, [("A", 534)]),
        _contest("One Planning Board - For one year term", 1, [("B", 534)]),
        _contest("Moderator - For one year term", 1, [("C", 583)]),
        _contest("One Board of Selectmen - For three year term", 1,
                 [("D", 492), ("E", 186), ("Others", 3), ("Blanks", 2)]),
        _contest("One Municipal Light Board - For three year term", 1,
                 [("F", 542)])]}
    verdict, reasons = escalate.review(rec)
    assert not any("impossible" in r for r in reasons)
    assert any("disagree about how many ballots" in r for r in reasons)


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


def test_a_state_election_is_not_an_annual_municipal_one():
    """Ayer 2010: "Democratic Party Primary Election Results ... September 14".

    A town report prints the state election beside its own return and the
    locator cannot tell them apart, so four state elections were graded
    publishable in annual town-year slots.
    """
    rec = {"elections": [
        _contest("Governor and Lieutenant Governor", 1,
                 [("DEVAL L PATRICK", 200), ("BLANKS", 177)]),
        _contest("Attorney General", 1, [("MARTHA COAKLEY", 300), ("BLANKS", 77)])]}
    verdict, reasons = escalate.review(rec)
    assert verdict == "escalate"
    assert any(r.startswith("this is not an annual municipal election")
               for r in reasons)


def test_a_town_auditor_is_a_municipal_office():
    """Six hill towns elect one; a bare AUDITOR test condemns all six."""
    rec = {"elections": [
        _contest("Auditor-One Year", 1, [("EVA C SMITH", 40), ("BLANKS", 5)]),
        _contest("Moderator-One Year", 1, [("PAUL R JONES", 41), ("BLANKS", 4)])]}
    assert not any(r.startswith("this is not an annual municipal election")
                   for r in escalate.review(rec)[1])


def test_a_year_the_fiscal_offset_cannot_explain_is_not_this_town_year():
    """Salisbury 2010 holds a return dated 2016-05-10, grounded 20 of 20."""
    from qa import atr_gate
    one_off = {"_source_stem": "Maynard2014", "elections": [
        _contest("Moderator", 1, [("A", 500), ("BLANKS", 500)]),
        _contest("Town Clerk", 1, [("B", 600), ("BLANKS", 400)])]}
    for c in one_off["elections"]:
        c["date"] = "2013-04-30"
    assert atr_gate.grade(one_off)[0] == "publish"
    far = dict(one_off, _source_stem="Salisbury2010")
    assert atr_gate.grade(far)[0] == "review"


# ------------------------------------------------------------------- locator

def _page(doc, lines):
    page = doc.new_page(width=612, height=792)
    y = 40
    for text in lines:
        page.insert_text((40, y), text, fontsize=9)
        y += 12
    return page


def test_a_contents_page_does_not_outscore_a_return_printed_with_dot_leaders():
    """Avon 2013 prints its whole return with dot leaders, and lost to the index.

    The same shape hid Topsfield's run for twelve years and put Carver 2014's
    index page into the published corpus with nine contests read off it.
    """
    from tools import atr_sections
    doc = pymupdf.open()
    _page(doc, ["Table of Contents", "Annual Town Election .......... 50",
                "Board of Selectmen ............ 12", "Assessors ..................... 14",
                "Town Clerk .................... 16", "Planning Board ................ 18",
                "Board of Health ............... 20", "Finance Committee ............. 22",
                "Library Trustee ............... 24"])
    _page(doc, ["ANNUAL TOWN ELECTION RESULTS", "BOARD OF HEALTH: ......... 3 years",
                "vote for one",
                "Robert A. Ogilvie, 28 Butler Ave ...........302",
                "Write In: .................................. 0",
                "Blanks: ................................... 91",
                "PLANNING BOARD: .......... 5 years", "vote for one",
                "Steven P. Rose, 120 Central St ............308",
                "Write In .................................... 0",
                "Blanks: ................................... 85"])
    best = atr_sections.score_pages(doc)
    assert best and best[0][1] == 1


def test_figures_alone_do_not_promote_a_page_with_no_ballot_words():
    """A police department's three-year statistics table is not a return."""
    from tools import atr_sections
    doc = pymupdf.open()
    _page(doc, ["ANNUAL TOWN ELECTION", "Moderator", "Selectmen", "Assessors",
                "Town Clerk", "Planning Board", "Board of Health"])
    _page(doc, ["ANNUAL REPORT OF THE POLICE DEPARTMENT",
                "Motor Vehicle Stops   2013 2014 2015",
                "Total number ......... 1906 1662 1436",
                "Verbal warnings ...... 72 74 77",
                "Written warnings ..... 4 7 4",
                "Citations issued ..... 15 5 9",
                "Summoned to court .... 7 11 6",
                "Arrested ............. 2 3 4",
                "Selectmen appointed .. 1 1 1",
                "Assessors notified ... 2 2 2",
                "Moderator briefed .... 1 1 1"])
    best = atr_sections.score_pages(doc)
    assert best and best[0][1] == 0


# ------------------------------------------------------------------- the date

def test_a_date_the_page_printed_is_not_a_missing_date():
    """Nineteen records were reported as undated with the date on the page.

    Three spellings, all unambiguous: the month is named, so nothing has to be
    guessed about which number is the day.
    """
    from qa.atr_bridge import iso_date
    assert iso_date("31-Mar-03", 2003)[0] == "2003-03-31"
    assert iso_date("4-Apr-07", 2007)[0] == "2007-04-04"
    assert iso_date("11May2015", 2015)[0] == "2015-05-11"
    assert iso_date("7 MAY 2019", 2019)[0] == "2019-05-07"
    assert iso_date("Monday, the Fourth Day of May, 2015", 2015)[0] == "2015-05-04"
    assert iso_date("TUESDAY, THE TWENTY NINTH DAY OF MARCH 2016", 2016)[0] == "2016-03-29"
    assert iso_date("Saturday, the Eighth Day of May, 2010", 2010)[0] == "2010-05-08"


def test_the_spellings_already_read_still_read_the_same():
    from qa.atr_bridge import iso_date
    assert iso_date("April 26, 2014", 2014)[0] == "2014-04-26"
    assert iso_date("April 25th, 2015", 2015)[0] == "2015-04-25"
    assert iso_date("Monday the 20th day of May, 2002", 2002)[0] == "2002-05-20"
    assert iso_date("04/06/2002", 2002)[0] == "2002-04-06"
    assert iso_date("2015-05-12", 2015)[0] == "2015-05-12"
    # A four-digit misread still fails, and a year window still guards it.
    assert iso_date("March 28, 2107", 2005)[0] is None
    assert iso_date("March 25, 1974", 2014)[0] is None
