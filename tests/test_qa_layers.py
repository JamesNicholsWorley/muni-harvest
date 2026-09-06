"""Offline tests for the layer-0 checks in `qa.layers`.

Every heading below is quoted from a document in the corpus. That is the point:
the check was wrong about nineteen of the twenty records it flagged, and it was
only reading a word. The cases are what the documents actually say.
"""

from qa import layers

_layers = layers  # alias used by tests merged from another run
from qa.layers import layer0_right_document, document_text, readable_chars


def _fired(head_text):
    """True if `preliminary_in_an_annual_slot` fires on this document text."""
    rows = layer0_right_document("Anytown2024", {"elections": []}, head_text, "test")
    return any(r[2] == "preliminary_in_an_annual_slot" for r in rows)


RECORD = {"elections": [{"office_original": "SELECT BOARD", "num_winners": 1,
                         "candidates": [{"name_original": "Jane Q. Public",
                                         "votes": 4271}]}]}

NR_OCR = ("NORTH READING, MA\nAnnual Town Election\nMAY 4, 2021\n\n"
          "Kathryn M. Manupelli 232 166 265 295 958\n"
          "Stephen J. O'Leary 262 165 276 339 1042\n"
          "TOTALS 648 436 734 834 2652\n")

NR_PDF = ("                  NORTH READING, MA\n           Annual Town Election\n"
          "                        MAY 4, 2021\n"
          "SELECT BOARD          For Three Years -- Vote for not more than TWO\n"
          "Blanks                 79   38   70  104   291\n"
          "Kathryn M. Manupelli  232  166  265  295   958\n"
          "Stephen J. O'Leary    262  165  276  339  1042\n"
          "COMMUNITY PLANNING    For Three Years -- Vote for not more than TWO\n"
          "Ryan J. Carroll       253  163  279  293   988\n"
          "Jeremiah C. Johnston  218  148  242  253   861\n"
          "   Proof                                  2652\n")


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

def _supports(text):
    """The verdict `document_supports_record` reaches on this document text."""
    rows = layer0_right_document("Anytown2024", RECORD, text, "test")
    return next(r[3] for r in rows if r[2] == "document_supports_record")



def _corpus_paths(tmp_path, monkeypatch, **files):
    """Lay out data/raw_ocr, data/markdown, data/pdftext under a temp BASE."""
    for rel, body in files.items():
        p = tmp_path / "data" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    monkeypatch.setattr(_layers, "BASE", str(tmp_path))

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

def test_the_fuller_reading_of_the_same_pdf_wins(tmp_path, monkeypatch):
    # Both files are readings of NorthReading2021_d0.pdf. The OCR is above the
    # 30-character bar, so the old order returned it and the record's only
    # ungrounded name, Ryan J. Carroll, was simply not in the text being
    # searched. Between two readings of one PDF the question is which recovered
    # more of the page.
    _corpus_paths(tmp_path, monkeypatch,
            **{"raw_ocr/NorthReading2021.txt": NR_OCR,
               "pdftext/NorthReading2021.txt": NR_PDF})
    text, source = document_text("NorthReading2021")
    assert "pdftext" in source  # union: no single reading wins
    assert "Ryan J. Carroll" in text
    assert "Vote for not more than TWO" in text

def test_a_scan_keeps_its_ocr_when_pdftotext_found_nothing(tmp_path, monkeypatch):
    # The ordinary case, and the reason raw_ocr leads: a scan with no text layer
    # yields an empty pdftext, and the OCR is the only reading there is.
    _corpus_paths(tmp_path, monkeypatch,
            **{"raw_ocr/Pelham2022.txt":
               "ANNUAL TOWN ELECTION MAY 17, 2022 SELECT BOARD (One for Three Years)",
               "pdftext/Pelham2022.txt": "\f\n \n"})
    _text, source = document_text("Pelham2022")
    assert "raw_ocr" in source  # union: no single reading wins

def test_a_longer_markdown_never_displaces_the_scan(tmp_path, monkeypatch):
    # markdown is not always an extraction of the same PDF. data/markdown for
    # Dalton2025 is an iBerkshires article about the election -- five times the
    # OCR's length and not the return -- so length must not promote it. Only
    # raw_ocr and pdftext, two readings of one PDF, are compared.
    _corpus_paths(tmp_path, monkeypatch,
            **{"raw_ocr/Dalton2025.txt":
               "TOWN OF DALTON ANNUAL TOWN ELECTION MAY 12, 2025 SELECT BOARD",
               "markdown/Dalton2025.md":
               "# Pagliarulo, Strout Win Seats on Dalton Select Board\n"
               "**By a staff reporter** " + "article prose. " * 200})
    _text, source = document_text("Dalton2025")
    assert "raw_ocr" in source  # union: no single reading wins


# ---- a figure has two spellings and the check knew one --------------------

def test_a_grouped_thousand_is_the_same_figure():
    # data/raw_ocr/Agawam2021.txt, verbatim: the record stores 4359 and the page
    # groups its thousands, so `\b4359\b` found nothing on a page that prints it.
    assert layers.figure_found(
        4359, "WILLIAM SAPELLI 4,359 81.31% CHARLES ALVANOS 1,002 18.69%")
    # data/markdown/Wellesley2021.md -- a precinct row ending in its total.
    assert layers.figure_found(
        3353, "MARK G. KAPLAN 456 554 377 546 373 286 253 508 3,353")
    # Boston prints the same kind of figure without the comma; both spellings
    # are the figure, and the plain one still matches.
    assert layers.figure_found(91794, "MICHELLE WU  3878 3002 ... 91794")


def test_a_grouped_form_is_no_looser_than_the_plain_one():
    # The lookarounds are the point: the grouped spelling of 2517 must not
    # ground itself on a printed 12,517, which `\d,\d\d\d` alone would allow.
    assert not layers.figure_found(2517, "TOTAL 12,517")
    # What the grouped branch does NOT do is tighten the plain one. `\b517\b`
    # has always matched inside `2,517` -- a comma is a word boundary -- and 517
    # therefore still grounds there. That is the pre-existing looseness of
    # string grounding, left alone deliberately: narrowing it would FLAG records
    # that pass today, and a check fix must only ever un-flag.
    assert layers.figure_found(517, "KEVIN B. CHRISOM, JR. ... 2,517")
    assert not layers.figure_found(4359, "43590")
    # A thousands separator is the only comma the trailing lookaround may
    # refuse.  data/markdown/Marshfield2025.md, verbatim: three correct figures,
    # and the two followed by a comma did not ground while the one followed by
    # a full stop did.
    _prose = ("Greer received the most votes, 2,505, Brait, 2,218, "
              "and Swain, 1,749. ")
    assert layers.figure_found(2505, _prose)
    assert layers.figure_found(2218, _prose)
    assert layers.figure_found(1749, _prose)
    # and it is still no looser about the digits than it was
    assert not layers.figure_found(2505, "the figure 12,505 and nothing else")
    assert not layers.figure_found(1234, "totals 1,234,567 here")
    # Under a thousand there is no grouped spelling to try, so a small figure
    # is matched exactly as it was before.
    assert layers.figure_found(275, "Bernard J. Stock 275")
    assert not layers.figure_found(275, "Bernard J. Stock 2750")


def test_a_grouped_figure_grounds_the_record():
    # figures_grounded and document_supports_record read the page the same way,
    # so the comma must not decide which of them fires.
    rows = layers.layer1_grounded(
        "Anytown2024", RECORD,
        "SELECT BOARD Jane Q. Public 4,271 Blanks 12", "test")
    assert dict((r[2], r[3]) for r in rows)["figures_grounded"] == "PASS"
    assert _supports("SELECT BOARD Jane Q. Public 4,271 Blanks 12") == "PASS"


# ---- a clerk dates a return the way a clerk writes a date ------------------

def test_a_two_digit_year_inside_a_date_is_the_year():
    # Each of these is the heading line of a held document, verbatim, and each
    # was reported as not carrying its own year.
    assert layers.year_found(
        "2021", "TOWN OF WILMINGTON - ANNUAL TOWN ELECTION 24-Apr-21 OFFICES")
    assert layers.year_found("2025", "ANNUAL TOWN ELECTION 05/17/25 Boad of Health")
    assert layers.year_found("2026", "BOXBOROUGH TOWN ELECTION Results 2-Jun-26")
    assert layers.year_found(
        "2023", "FINAL RESULTS ANNUAL TOWN ELECTION 5/1/23 - 129 VOTERS")
    assert layers.year_found("2022", "## LOCALELECTION 2-May-22 ## GROVELAND")


def test_the_four_digit_year_still_matches_without_a_boundary():
    # Medford 2025: OCR strips the spaces, so a word boundary cannot match.
    assert layers.year_found(
        "2025", "OFFICIAL2025GENERALMUNICIPALELECTIONRESULTS")


def test_two_loose_digits_are_not_a_year():
    # The two-digit form is admitted only inside a whole date. A tally of 21
    # votes, a precinct numbered 26, or a bare pair of digits is not one.
    assert not layers.year_found("2021", "Blanks 21 Write-ins 3 TOTAL 24")
    assert not layers.year_found("2026", "PRECINCT 26 TOTAL 1,204")
    assert not layers.year_found("2023", "23")
    # A date in a different year is still a different year.
    assert not layers.year_found("2024", "ANNUAL TOWN ELECTION 24-Apr-21")


def test_an_undated_document_is_still_undated():
    rows = layer0_right_document(
        "Anytown2024", {"elections": []},
        "ANNUAL TOWN ELECTION Blanks 12 Jane Q. Public 4271", "test")
    assert dict((r[2], r[3]) for r in rows)["carries_the_year"] == "FAIL"


def test_a_full_stop_is_a_date_separator_too():
    # data/raw_ocr/Swampscott2025.txt, its heading line.
    assert layers.year_found(
        "2025", "LOCAL ELECTION UNOFFICIAL ELECTION RESULTS 4.29.25 Voter Total")
    # It is still a date and not a decimal: the day has to be a day.
    assert not layers.year_found("2025", "TURNOUT 4.99.25 PERCENT")
