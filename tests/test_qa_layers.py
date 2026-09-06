"""Offline tests for the layer-0 checks in `qa.layers`.

Every heading below is quoted from a document in the corpus. That is the point:
the check was wrong about nineteen of the twenty records it flagged, and it was
only reading a word. The cases are what the documents actually say.
"""

from qa.layers import layer0_right_document


def _fired(head_text):
    """True if `preliminary_in_an_annual_slot` fires on this document text."""
    rows = layer0_right_document("Anytown2024", {"elections": []}, head_text, "test")
    return any(r[2] == "preliminary_in_an_annual_slot" for r in rows)


def test_a_preliminary_election_still_fires():
    # A PRELIMINARY ELECTION is the Massachusetts municipal primary, and it must
    # never occupy an annual slot.  Both quotes are pages of Salem2023_d0.pdf.
    assert _fired("CITY OF SALEM SPECIAL PRELIMINARY ELECTION "
                  "MARCH 28, 2023 OFFICIAL RESULTS")
    assert _fired("OFFICIAL RESULTS CITY OF SALEM PRELIMINARY ELECTION "
                  "SEPTEMBER 19, 2023")
    # the same thing worded the other way round
    assert _fired("TOWN OF ANYTOWN PRELIMINARY MUNICIPAL ELECTION "
                  "SEPTEMBER 12, 2023")


def test_preliminary_results_of_an_annual_election_do_not_fire():
    # "Preliminary" qualifying the FIGURES -- unofficial counts announced on the
    # night, finalised later.  Every one of these is an annual town election.
    for heading in [
        # Needham2026_d0.pdf
        "Townwide Offices Preliminary Results of Annual Town Election 4/14/2026",
        # Acton2026_d0.pdf, on all three pages
        "Annual Town Election PRELIMINARY April 28, 2026 VOTE COUNT PCT 1",
        # Acushnet2026_d0.pdf, the clerk's own footnote
        "* Please note the figures listed below are preliminary and will be "
        "finalized within four days following the election. POLLS CALL IN SHEET",
        # Agawam2025_d0.pdf
        "MUNICIPAL ELECTION Preliminary PRECINCT 1 PRECINCT 2",
        # Carlisle2024_d0.pdf, over a full annual ballot including a fire-truck question
        "Preliminary Election Results May 21, 2024 Select Board - One for Three Years",
        # Holliston2025, Holliston Reporter
        "Preliminary Town Election Results 05/20/25 Posted on May 20, 2025",
        # Kingston2022_d0.pdf and Kingston2024_d0.pdf -- ATE is the Annual Town Election
        "ATE 2022 Preliminary 4/23/2022 OFFICE PRECINCTS TOTAL",
        "PRELIMINARY RESULTS KINGSTON ATE 2024 5/18/2024 7:45 PM",
        # Carlisle2026_d0.pdf
        "The 2026 Annual Town Election was held Tuesday, June 2, 2026 at the "
        "Carlisle Town Hall PRELIMINARY RESULTS Candidates SELECT BOARD",
        # WestNewbury2021_d0.pdf and WestNewbury2022_d0.pdf
        "MAY 3, 2021 ANNUAL TOWN ELECTION RESULTS WEST NEWBURY, MASSACHUSETTS "
        "There were 386 ballots cast. The Town Clerk announced the preliminary "
        "results at 8:05 PM.",
    ]:
        assert not _fired(heading), heading


def test_the_check_only_reads_the_heading():
    # A return that mentions a preliminary far down the page is not a preliminary.
    # The window is the heading, and staying inside it is what keeps a compilation
    # from being condemned by page one of twenty-one.
    assert not _fired("ANNUAL TOWN ELECTION MAY 14, 2026 " + "x " * 400
                      + "PRELIMINARY ELECTION SEPTEMBER 19")


# ---------------------------------------------------------------- the reader

import qa.layers as layers


def _store(tmp_path, monkeypatch, **files):
    """Lay out a data/ tree holding the named readings of one town-year."""
    for sub, name, body in (("raw_ocr", "Anytown2024.txt", files.get("raw_ocr")),
                            ("markdown", "Anytown2024.md", files.get("markdown")),
                            ("pdftext", "Anytown2024.txt", files.get("pdftext"))):
        if body is None:
            continue
        d = tmp_path / "data" / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(body, encoding="utf-8")
    monkeypatch.setattr(layers, "BASE", str(tmp_path))


def test_a_garbage_ocr_does_not_hide_a_clean_text_layer(tmp_path, monkeypatch):
    # Washington2024_d0.pdf is a born-digital return.  Its text layer prints
    # "David Drugmand            102"; its OCR renders the same block as
    # "Total SSst~<Cs*e~'se*d a0]".  Reading only the OCR reported 0/19 names
    # located and called the right document a wrong one.
    _store(tmp_path, monkeypatch,
           raw_ocr="TOWN OF WASHINGTON ANNUAL TOWN ELECTION\n"
                   "Total SSst~<Cs*e~'se*d a0] Writes SSs~=<idtCSOSS\n",
           pdftext="RESULTS TOWN OF WASHINGTON ANNUAL TOWN ELECTION\n"
                   "SATURDAY, MAY 18, 2024\nDavid Drugmand 102\n")
    record = {"elections": [{"office_original": "FINANCE COMMITTEE",
                             "candidates": [{"name_original": "David Drugmand",
                                             "votes": 102}]}]}
    text, source = layers.document_text("Anytown2024")
    rows = {r[2]: r for r in layers.layer0_right_document(
        "Anytown2024", record, text, source)}
    assert rows["document_supports_record"][3] == layers.PASS
    assert rows["document_supports_record"][4].startswith("1/1 names and 1/1 figures")
    assert rows["carries_the_year"][3] == layers.PASS


def test_a_scan_still_reads_from_its_ocr(tmp_path, monkeypatch):
    # The other direction, and why the OCR is searched at all: a pure scan has
    # no text layer, and only the pixels say anything.
    _store(tmp_path, monkeypatch,
           raw_ocr="TOWN OF PELHAM ANNUAL TOWN ELECTION MAY 17, 2024\n"
                   "SELECT BOARD Jane Doe 88\n",
           pdftext="\f")
    record = {"elections": [{"office_original": "SELECT BOARD",
                             "candidates": [{"name_original": "Jane Doe",
                                             "votes": 88}]}]}
    text, source = layers.document_text("Anytown2024")
    rows = {r[2]: r for r in layers.layer0_right_document(
        "Anytown2024", record, text, source)}
    assert rows["document_supports_record"][3] == layers.PASS
    assert "raw_ocr" in source


def test_the_heading_window_is_still_the_first_store(tmp_path, monkeypatch):
    # The preliminary check reads text[:600].  Joining the stores must not let a
    # later store's heading slide into that window and condemn the record.
    _store(tmp_path, monkeypatch,
           raw_ocr="ANNUAL TOWN ELECTION MAY 14, 2026 " + "x " * 400,
           pdftext="PRELIMINARY ELECTION SEPTEMBER 19, 2026")
    text, source = layers.document_text("Anytown2024")
    rows = layers.layer0_right_document("Anytown2024", {"elections": []},
                                        text, source)
    assert not any(r[2] == "preliminary_in_an_annual_slot" for r in rows)


def test_no_reading_held_is_still_no_reading(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch, markdown="   \n")
    assert layers.document_text("Anytown2024") == (None, None)
