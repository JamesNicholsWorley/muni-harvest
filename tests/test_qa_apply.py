"""What `qa.apply` must refuse.

Every case here is a way the gate could let a wrong correction through. The
cases that apply cleanly are the easy half; these are the half that matters,
because a correction written to the wrong candidate is the damage this project
cannot undo.
"""

import io
import json
import os

from qa import apply as A


def _tree(tmp_path, monkeypatch, *, record, reading, sha_ok=True):
    """A data/ holding one record and one reading of its document."""
    for sub in ("json", "raw_ocr", "pdfs"):
        (tmp_path / "data" / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "json" / "Anytown2024.json").write_text(
        json.dumps(record), encoding="utf-8")
    (tmp_path / "data" / "raw_ocr" / "Anytown2024.txt").write_text(
        reading, encoding="utf-8")
    monkeypatch.setattr(A, "BASE", str(tmp_path))
    import qa.layers as layers
    monkeypatch.setattr(layers, "BASE", str(tmp_path))


RECORD = {"elections": [{"office_original": "SELECT BOARD", "num_winners": 1,
                         "candidates": [{"name_original": "Joseph J. Magnani, Jr.",
                                         "votes": 345}]}]}


def _row(**kw):
    base = dict(stem="Anytown2024", source_sha256="", field='candidates[].name_original',
                was="Joseph J. Magnani, Jr.", should_be="JOSPEH J. MAGNANI, JR.",
                read="q", why="", status="proposed", decided_by="", decided_on="")
    base.update(kw)
    return base


def test_the_page_says_it_and_we_do_not(tmp_path, monkeypatch):
    # Ashland 2025: the clerk's own text layer prints the misspelling.
    _tree(tmp_path, monkeypatch, record=RECORD,
          reading="ANNUAL TOWN ELECTION JOSPEH J. MAGNANI, JR. 345")
    verdict, note, _ = A.consider(_row())
    assert verdict == "apply", note


def test_a_document_holding_both_spellings_is_not_decidable(tmp_path, monkeypatch):
    # If the page prints both, the string test has no opinion and must say so
    # rather than pick the one somebody proposed.
    _tree(tmp_path, monkeypatch, record=RECORD,
          reading="JOSPEH J. MAGNANI, JR. 345 ... Joseph J. Magnani, Jr. 345")
    verdict, note, _ = A.consider(_row())
    assert verdict == "needs-owner"
    assert "BOTH" in note


def test_a_correction_the_document_does_not_support_is_not_applied(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, record=RECORD,
          reading="ANNUAL TOWN ELECTION and nothing resembling either spelling")
    verdict, _, _ = A.consider(_row())
    assert verdict == "skip"


def test_num_winners_is_never_a_string_test(tmp_path, monkeypatch):
    # Seats up decides who won. It is one digit and it is not settled by
    # whether the digit appears on the page.
    _tree(tmp_path, monkeypatch, record=RECORD, reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS vote for TWO 345")
    verdict, note, _ = A.consider(_row(field="elections[0].num_winners",
                                       was="1", should_be="2"))
    assert verdict == "needs-owner"
    assert "judgement" in note


def test_a_value_in_two_places_is_ambiguous(tmp_path, monkeypatch):
    two = {"elections": [
        {"office_original": "SELECT BOARD", "num_winners": 1,
         "candidates": [{"name_original": "A. Smith", "votes": 10}]},
        {"office_original": "MODERATOR", "num_winners": 1,
         "candidates": [{"name_original": "A. Smith", "votes": 20}]}]}
    _tree(tmp_path, monkeypatch, record=two, reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS A. SMYTH 10 A. SMYTH 20")
    verdict, note, _ = A.consider(_row(was="A. Smith", should_be="A. SMYTH"))
    assert verdict == "needs-owner"
    assert "ambiguous" in note


def test_a_figure_needs_a_session_to_have_reopened_the_document(tmp_path, monkeypatch):
    # A digit is short enough to appear on a page by coincidence.
    _tree(tmp_path, monkeypatch, record=RECORD,
          reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS MAGNANI 346 votes recorded")
    verdict, note, _ = A.consider(_row(field="candidates[].votes", was="345",
                                       should_be="346"))
    assert verdict == "needs-owner"
    assert "verified" in note


def test_a_verified_figure_applies_even_though_the_old_number_is_also_on_the_page(tmp_path, monkeypatch):
    # The both-present rule is right for a name and wrong for a figure: on a
    # multi-page return almost every number appears somewhere. Requiring the old
    # value to be absent blocked all 44 rows a session had read off the page.
    _tree(tmp_path, monkeypatch, record=RECORD,
          reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS MAGNANI 346 ... 345 elsewhere on the sheet")
    verdict, _, payload = A.consider(_row(field="candidates[].votes", was="345",
                                          should_be="346", status="verified"))
    assert verdict == "apply"
    jpath, record, target, value = payload
    A.write_value(record, target, value)
    assert record["elections"][0]["candidates"][0]["votes"] == 346


def test_a_replaced_document_retires_the_reasoning(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, record=RECORD, reading="JOSPEH J. MAGNANI, JR. 345")
    (tmp_path / "data" / "pdfs" / "Anytown2024.pdf").write_bytes(b"different bytes")
    verdict, note, _ = A.consider(_row(source_sha256="0" * 64))
    assert verdict == "skip"
    assert "replaced" in note


def test_a_record_that_does_not_hold_the_old_value_is_skipped(tmp_path, monkeypatch):
    # Somebody already fixed it, or the row describes a different record.
    _tree(tmp_path, monkeypatch, record=RECORD, reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS SOMEONE ELSE 345")
    verdict, _, _ = A.consider(_row(was="Not In The Record", should_be="SOMEONE ELSE"))
    assert verdict == "skip"
