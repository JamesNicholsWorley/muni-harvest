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
