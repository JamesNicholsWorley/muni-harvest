"""Offline tests for the wide-net document classifier (real-world URL patterns)."""

from muni_harvest.discover.docclass import classify_document, extract_date


def test_agendacenter_url_gives_doctype_date_id():
    c = classify_document("https://www.acushnet.ma.us/AgendaCenter/ViewFile/Minutes/_01022025-297")
    assert c["doctype"] == "minutes" and c["agendacenter"]
    assert c["date"] == "2025-01-02" and c["meeting_id"] == "297"


def test_board_synonyms_wide_net():
    assert classify_document("/documents/BOS-Minutes/05-19-11-SelectmensMtg.pdf")["board"] == "select_board"
    assert classify_document("/f/minutes/concomm_meeting_minutes_02.15.24.pdf")["board"] == "conservation"
    assert classify_document("/Public_Documents/ArlingtonMA_BComm/zba/Rules.pdf")["board"] == "zba"
    assert classify_document("/fairhaven/07-07-2026-Board-of-Appeals-Meeting-Agenda.pdf")["board"] == "zba"
    assert classify_document("/DocumentCenter/View/1/2005-PB-Report")["board"] == "planning_board"


def test_council_on_aging_not_city_council():
    assert classify_document("/f/agendas/council_on_aging_03-08-2023.pdf")["board"] == "coa"
    assert classify_document("/citycouncil/agenda_2024.pdf")["board"] == "city_council"


def test_doctype_from_folder_and_name():
    assert classify_document("/f/agendas/x.pdf")["doctype"] == "agenda"
    assert classify_document("/BOS-Minutes/mtg.pdf")["doctype"] == "minutes"
    assert classify_document("/annual_town_meeting_warrant.pdf")["doctype"] == "warrant"


def test_date_formats():
    assert extract_date("minutes_02.15.24.pdf")[0] == "2024-02-15"
    assert extract_date("2023-11-07-results.pdf")[0] == "2023-11-07"
    assert extract_date("07-07-2026-agenda.pdf")[0] == "2026-07-07"
    assert extract_date("report2019.pdf") == ("", "2019")
