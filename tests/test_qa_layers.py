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


# ---------------------------------------------------------------------------
# document_supports_record, and which file it reads.
#
# The check condemned 18 records as wrong documents. Opening all 18 gave: 14 the
# RIGHT document read by a tool that could not read it, 3 holding no readable
# text at all, and exactly 1 genuine wrong document. Every text below is quoted
# from the file named beside it.

RECORD = {"elections": [{"office_original": "SELECT BOARD", "num_winners": 1,
                         "candidates": [{"name_original": "Jane Q. Public",
                                         "votes": 4271}]}]}


def _supports(text):
    """The verdict `document_supports_record` reaches on this document text."""
    rows = layer0_right_document("Anytown2024", RECORD, text, "test")
    return next(r[3] for r in rows if r[2] == "document_supports_record")


def test_a_collapsed_scan_is_unread_not_wrong():
    # data/raw_ocr/Boston2021.txt -- heading survives, every table under it does
    # not. The record's names and figures are nowhere in this text, and that is
    # a fact about the OCR, not about the document.
    assert _supports(
        "CITY OF BOSTON MUNICIPAL ELECTION - NOVEMBER 2, 2021 MAYOR "
        "VOTES CAST BY WARD [canomares [+ [?]2]*]s]*]7]*]*|o[n[@[o[u[ 6] e[7][w| "
        "PERCENTAGE OF VOTES CAST BY PRECINCT") == "UNKNOWN"
    # data/raw_ocr/Chatham2022.txt -- the minutes read, the tally did not. The
    # record closes exactly on the 1,089 this text prints, in all three contests.
    assert _supports(
        "TOWN OF CHATHAM THURSDAY, MAY 19, 2022 ANNUAL TOWN ELECTION MINUTES "
        "At the time of this Election there were 6,170 registered voters in "
        "Chatham, 1,089 ballots were cast (17%). a BLANKS S| | a") == "UNKNOWN"
    # data/raw_ocr/Middleborough2026.txt -- only the TOTALS row came through.
    assert _supports(
        "TOWN OF MIDDLEBOROUGH RECORD OF : Annual Town Election OFFICIAL "
        "RESULTS : Saturday, April 4, 2026 Pi = P2_—siBB P4 P5 —- P6 TOTALS "
        "Select Board (Vote for 2) 956 490 614 466 716 650 756| 4648 | "
        "* Denotes Write In Candidate") == "UNKNOWN"


def test_town_meeting_minutes_are_still_a_wrong_document():
    # data/pdftext/Brimfield2022.txt -- 17,082 readable characters of Town
    # Meeting warrant articles. It says "Annual Town Election" exactly once, in
    # a bylaw listing which officers are elected, and holds no tally word at
    # all. None of the record's four candidates or figures appear.
    assert _supports(
        "ARTICLE 18: To see if the Town will vote to raise and appropriate the "
        "sum of $30,000 to the Treasurer's Department. Motion to approve "
        "Articles 12, 13, 15, 16 and 17 passed by a show of voting cards. "
        "4.0 Election of Officials 4.1 Officers to be Elected, Terms The "
        "Officers of the Town to be elected at the Annual Town Election in the "
        "years in which the terms of the incumbents expire, with their terms "
        "of office, shall be as follows: 5 Selectmen for 3 years each") == "FAIL"


def test_one_tally_word_is_not_a_return():
    # The bar is two distinct terms, and it is the bar because of Brimfield.
    assert _supports("Notice of a public hearing. Blanks in the schedule "
                     "below will be filled by the board.") == "FAIL"


def test_a_document_that_supports_the_record_still_passes():
    assert _supports("SELECT BOARD Jane Q. Public 4271 Blanks 12") == "PASS"


# ---------------------------------------------------------------------------
# Which file counts as a reading at all.

from qa.layers import readable_chars  # noqa: E402


def test_a_placeholder_is_not_a_reading():
    # data/raw_ocr/Hopedale2025.txt, in full -- 32 bytes, both of them the
    # extractor saying it found a picture. Preferring it hid
    # data/markdown/Hopedale2025.md, which holds the whole return in plain text,
    # and reported Hopedale as not carrying its own year and as a wrong document.
    assert readable_chars("<!-- image -->\n\n<!-- image -->\n") < 30
    # data/markdown/Buckland2022.md, in full -- an empty table rule and ten more
    # of those. Nothing is held for Buckland 2022; that is the honest answer.
    assert readable_chars("|    |\n|----|\n\n" + "<!-- image -->\n\n" * 10) < 30
    # data/markdown/Dunstable2025.md -- 1,117 replacement characters of 1,255.
    assert readable_chars("�" * 1117 + "\nTE\n") < 30


def test_a_real_extraction_still_counts():
    # data/markdown/Hopedale2025.md, its first lines.
    assert readable_chars(
        "Hopedale Annual Town Election\nSelect Board - 3 year term\n"
        "Bernard J. Stock 275\nWrite-in 53\nBlanks 15\n") >= 30
    # A picture caption alongside real text does not disqualify the text.
    assert readable_chars(
        "<!-- image -->\nANNUAL TOWN ELECTION MAY 18, 2021 Blanks 808") >= 30
