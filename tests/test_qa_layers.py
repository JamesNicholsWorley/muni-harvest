"""Offline tests for the layer-0 checks in `qa.layers`.

Every heading below is quoted from a document in the corpus. That is the point:
the check was wrong about nineteen of the twenty records it flagged, and it was
only reading a word. The cases are what the documents actually say.
"""

from qa import layers
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


# ---------------------------------------------------------------- readings

def _corpus(tmp_path, monkeypatch, **readings):
    """Lay out data/ the way bootstrap does, with the readings given."""
    for name, text in readings.items():
        d = tmp_path / "data" / name
        d.mkdir(parents=True, exist_ok=True)
        ext = ".md" if name == "markdown" else ".txt"
        (d / ("Anytown2022" + ext)).write_text(text, encoding="utf-8")
    monkeypatch.setattr(layers, "BASE", str(tmp_path))


def test_a_degraded_ocr_does_not_hide_the_text_layer(tmp_path, monkeypatch):
    # Boston 2021: the OCR collapsed the table into noise while the PDF's own
    # text layer reads the same page cleanly.  Taking raw_ocr and stopping
    # grounded 0 of 25 names against a document that was right all along.
    _corpus(tmp_path, monkeypatch,
            raw_ocr="CITY OF BOSTON MUNICIPAL ELECTION - NOVEMBER 2, 2021\n"
                    "pvescsr | oa ez] oira]ar] roe] eal sos] tera] su]",
            pdftext="CITY OF BOSTON  MUNICIPAL ELECTION - NOVEMBER 2, 2021\n"
                    "MICHELLE WU   3878  3002  5935   91794")
    text, source = layers.document_text("Anytown2022")
    assert source == "raw_ocr+pdftext"
    assert "MICHELLE WU" in text          # the figure is findable
    assert "pvescsr" in text              # and the OCR is not discarded


def test_an_extraction_that_splits_the_year_does_not_hide_one_that_does_not(
        tmp_path, monkeypatch):
    # Auburn 2022's markdown extraction prints "MAY 1 7 , 202 2"; pdftotext over
    # the same PDF prints "MAY 17, 2022".  The year check was reading the first
    # and reporting a correctly-dated return as undated.
    _corpus(tmp_path, monkeypatch,
            markdown="TOWN OF AUBURN ANNUAL ELECTION MAY 1 7 , 202 2",
            pdftext="TOWN OF AUBURN ANNUAL ELECTION MAY 17, 2022")
    text, source = layers.document_text("Anytown2022")
    rows = layer0_right_document("Anytown2022", {"elections": []}, text, source)
    year = [r for r in rows if r[2] == "carries_the_year"]
    assert year and year[0][3] == "PASS", year


def test_no_reading_held_is_still_no_reading(tmp_path, monkeypatch):
    monkeypatch.setattr(layers, "BASE", str(tmp_path))
    assert layers.document_text("Anytown2022") == (None, None)


def test_a_placeholder_reading_contributes_nothing_but_is_not_fatal(tmp_path, monkeypatch):
    # Hopedale 2025's raw_ocr is "<!-- image -->" and nothing else.  Joined with
    # a real reading it neither helps nor blocks.
    _corpus(tmp_path, monkeypatch,
            raw_ocr="<!-- image -->\n\n<!-- image -->",
            pdftext="HOPEDALE ANNUAL TOWN ELECTION 2025 SELECT BOARD")
    text, source = layers.document_text("Anytown2022")
    assert source == "raw_ocr+pdftext"
    assert "2025" in text
