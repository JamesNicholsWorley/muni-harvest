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


def test_a_scope_change_is_never_a_string_test(tmp_path, monkeypatch):
    # Scope moves a contest between the ballot arithmetic and the exemption from
    # it. Nothing on the page settles that, so it stays the owner's.
    # (num_winners USED to be here. A printed "vote for no more than N" is the
    # seat count and outranks the arithmetic, which makes it a string test after
    # all -- see the seat tests below.)
    _tree(tmp_path, monkeypatch, record=RECORD,
          reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS PRECINCT 1 345")
    verdict, note, _ = A.consider(_row(field="elections[0].scope",
                                       was="at_large", should_be="sub_town"))
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


SEATS = {"elections": [{"office_original": "SELECT BOARD", "num_winners": 1,
                        "candidates": [{"name_original": "A. Smith", "votes": 10}]}]}


def test_a_printed_seat_count_settles_num_winners(tmp_path, monkeypatch):
    # The project's own rule: a printed "vote for no more than N" outranks the
    # arithmetic. That is a string test, so the document decides.
    _tree(tmp_path, monkeypatch, record=SEATS,
          reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS SELECT BOARD "
                  "(Vote for not more than TWO) A. Smith 10")
    verdict, note, payload = A.consider(
        _row(field="elections[0].num_winners", was="1", should_be="2"))
    assert verdict == "apply", note
    jpath, record, target, value = payload
    A.write_value(record, target, value)
    assert record["elections"][0]["num_winners"] == 2


def test_a_seat_count_in_digits_counts_too(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, record=SEATS,
          reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS SELECT BOARD "
                  "Vote for 2 -- A. Smith 10")
    verdict, _, _ = A.consider(
        _row(field="elections[0].num_winners", was="1", should_be="2"))
    assert verdict == "apply"


def test_an_unprinted_seat_count_needs_a_session_to_have_read_the_page(tmp_path, monkeypatch):
    # Attleboro 2025: nothing on the page states the number and the claim rests
    # on the block closing on ballots x 5. Real evidence, weaker than print.
    _tree(tmp_path, monkeypatch, record=SEATS,
          reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS SELECT BOARD A. Smith 10")
    verdict, note, _ = A.consider(
        _row(field="elections[0].num_winners", was="1", should_be="5"))
    assert verdict == "needs-owner"
    assert "prints no seat count" in note

    verdict, note, _ = A.consider(
        _row(field="elections[0].num_winners", was="1", should_be="5",
             status="verified"))
    assert verdict == "apply", note


def test_the_page_printing_a_different_number_does_not_apply(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, record=SEATS,
          reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS SELECT BOARD "
                  "(Vote for ONE) A. Smith 10")
    verdict, note, _ = A.consider(
        _row(field="elections[0].num_winners", was="1", should_be="3"))
    assert verdict == "needs-owner"
    assert "prints 1" in note or "[1]" in note


def test_one_spelling_containing_the_other_is_not_an_ambiguity(tmp_path, monkeypatch):
    # Tisbury 2026: we hold "Hillary Conklin", the page prints "J. Hillary
    # Conklin". Both are "present" only because one contains the other, so
    # there is nothing for the document to be ambiguous about.
    rec = {"elections": [{"office_original": "SELECT BOARD", "num_winners": 1,
                          "candidates": [{"name_original": "Hillary Conklin",
                                          "votes": 10}]}]}
    _tree(tmp_path, monkeypatch, record=rec,
          reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS J. Hillary Conklin 10")
    verdict, note, _ = A.consider(_row(was="Hillary Conklin",
                                       should_be="J. Hillary Conklin"))
    assert verdict == "apply", note


def test_punctuation_alone_is_not_two_spellings(tmp_path, monkeypatch):
    # Wellesley 2021: "Robertfragasso" against "Robert-Fragasso" is one string
    # once punctuation is stripped, which is how the comparison is made.
    rec = {"elections": [{"office_original": "TOWN MEETING", "num_winners": 1,
                          "candidates": [{"name_original": "Laura W. Robertfragasso",
                                          "votes": 10}]}]}
    _tree(tmp_path, monkeypatch, record=rec,
          reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS Laura W. Robert-Fragasso 10")
    verdict, note, _ = A.consider(_row(was="Laura W. Robertfragasso",
                                       should_be="Laura W. Robert-Fragasso"))
    assert verdict == "apply", note


def test_the_rows_own_reading_can_stand_in_for_a_broken_ocr(tmp_path, monkeypatch):
    # Lakeville 2026's names are wrong in the record BECAUSE the OCR is wrong,
    # so the OCR can never confirm the correction. A session rendered the page
    # and wrote down what it says. Preferring the OCR there is preferring the
    # machine that got it wrong.
    rec = {"elections": [{"office_original": "SELECT BOARD", "num_winners": 2,
                          "candidates": [{"name_original": "Maureen E. Conello",
                                          "votes": 437}]}]}
    _tree(tmp_path, monkeypatch, record=rec,
          reading="OFFICIAL RESULTS TOWN OF LAKEVILLE Maureen E. Conello 437")
    verdict, note, payload = A.consider(_row(
        was="Maureen E. Conello", should_be="Maureen E. Candito",
        read="Page 1 rendered at 170dpi: 'Maureen E. Candito 134 185 118 437'"))
    assert verdict == "apply", note
    jpath, record, target, value = payload
    A.write_value(record, target, value)
    assert record["elections"][0]["candidates"][0]["name_original"] == "Maureen E. Candito"


def test_a_reading_that_does_not_quote_the_correction_is_still_refused(tmp_path, monkeypatch):
    rec = {"elections": [{"office_original": "SELECT BOARD", "num_winners": 1,
                          "candidates": [{"name_original": "A. Smith", "votes": 10}]}]}
    _tree(tmp_path, monkeypatch, record=rec,
          reading="ANNUAL TOWN ELECTION OFFICIAL RESULTS A. Smith 10")
    verdict, _, _ = A.consider(_row(was="A. Smith", should_be="A. Smythe",
                                    read="I rendered the page and it looked fine"))
    assert verdict == "skip"


def test_a_row_that_locates_by_name_and_changes_a_vote_is_a_figure():
    # `candidates[name_original == "X"].votes` names one field to find the row
    # and another to change. Matching name_original first refused it with
    # "record holds no name equal to '189'" -- about the row's wording, not the
    # document. The field being changed is the rightmost.
    kind, _ = A.classify({"field": 'candidates[name_original == "Marie Cain"].votes',
                          "why": ""})
    assert kind == "figure"


def test_a_plain_name_row_is_still_a_name():
    kind, _ = A.classify({"field": 'candidates[].name_original == "Jospeh"',
                          "why": ""})
    assert kind == "name"


def test_a_seat_row_that_mentions_a_candidate_is_still_seats():
    kind, _ = A.classify({"field": 'elections[SELECT BOARD].num_winners',
                          "why": "the block closes on ballots x 2"})
    assert kind == "seats"
