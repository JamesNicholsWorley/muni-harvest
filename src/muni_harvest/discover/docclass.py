"""Deterministic, WIDE-NET document classifier — typify municipal docs from the URL.

Grounded in real patterns from the corpus (anchors are empty for ~99% of docs, so we
work from the path + filename). Extracts (board/body, doctype, date, meeting_id).

Design bias: favor RECALL (cast a wide net, many synonyms/abbreviations) — a later
content-verify pass prunes false positives. Order matters: specific bodies are tested
before generic ones (e.g. 'council on aging' before bare 'council').
"""

from __future__ import annotations

import re

# --- governing bodies / boards (ordered: specific -> generic) ------------------
# Each: (key, label, wide-net pattern). First match wins.
BOARDS: list[tuple[str, str, str]] = [
    ("coa", "Council on Aging",
     r"council[ _-]on[ _-]aging|\bcoa\b|senior center"),
    ("select_board", "Select Board / Selectmen",
     r"select[ _-]?board|selectmen|selectman|board[ _-]of[ _-]selectmen|\bbos\b"),
    ("city_council", "City / Town Council",
     r"city[ _-]?council|town[ _-]?council|common[ _-]?council|\bcouncil\b"),
    ("zba", "Zoning Board of Appeals",
     r"\bzba\b|\bzboa\b|zoning[ _-]board[ _-]of[ _-]appeals|zoning[ _-]board|"
     r"board[ _-]of[ _-]appeals"),
    ("planning_board", "Planning Board",
     r"planning[ _-]?board|planning[ _-]?bd\b|(?:^|[/_-])pb(?=[/_-])|/planning/|planning[ _-]?comm"),
    ("conservation", "Conservation Commission",
     r"conservation|con[ _-]?comm|concom|\bconcomm\b|con[ _-]com\b"),
    ("board_of_health", "Board of Health",
     r"board of health|\bboh\b|health[ _-]department|health board"),
    ("school_committee", "School Committee",
     r"school[ _-]committee|school[ _-]comm\b|school[ _-]board"),
    ("finance", "Finance / Advisory Committee",
     r"finance[ _-]committee|fin[ _-]?com\b|financ\w*[ _-]comm|advisory[ _-](board|committee)|\bfincom\b|warrant committee"),
    ("assessors", "Board of Assessors",
     r"assessor"),
    ("zoning", "Zoning / Land Use (non-ZBA)",
     r"\bzoning\b|land use"),
    ("library", "Library Trustees",
     r"\blibrary\b|library trustees|trustees of the"),
    ("historic", "Historical Commission",
     r"historic\w*"),
    ("licensing", "Licensing",
     r"licens\w+"),
    ("elections", "Elections / Town Clerk",
     r"election|town[ _-]clerk|/elections?/|registrar"),
    ("town_meeting", "Town Meeting",
     r"town[ _-]meeting|\batm\b|\bstm\b|warrant"),
]
_BOARD_RES = [(k, lbl, re.compile(p, re.I)) for k, lbl, p in BOARDS]

# --- document types (ordered) --------------------------------------------------
DOCTYPES: list[tuple[str, str]] = [
    ("agenda", r"agenda|/agendas?/|\bagd\b"),
    ("minutes", r"minutes|/minutes/|[_-]min[_.\b-]|meeting[ _-]?notes|\bmins\b"),
    ("warrant", r"warrant"),
    ("election_results", r"election.*result|result.*election|canvass|precinct|"
                         r"tally|unofficial[ _-]result|official[ _-]result|vote[ _-]?count"),
    ("budget", r"budget|acfr|appropriat|annual[ _-]report"),
    ("bylaw", r"by[ _-]?law|ordinance|charter|regulation"),
    ("packet", r"packet|agenda[ _-]?packet"),
    ("notice", r"notice|posting|posted|hearing"),
    ("decision", r"decision|finding|variance|special[ _-]permit"),
    ("report", r"\breport\b"),
]
_DOCTYPE_RES = [(k, re.compile(p, re.I)) for k, p in DOCTYPES]

# --- dates ---------------------------------------------------------------------
_AGENDACENTER = re.compile(r"/AgendaCenter/ViewFile/(Agenda|Minutes)/_(\d{2})(\d{2})(\d{4})-(\d+)", re.I)
_DATE_PATS = [
    re.compile(r"(?<!\d)(20[0-2]\d)[-_.]([01]\d)[-_.]([0-3]\d)(?!\d)"),   # YYYY-MM-DD
    re.compile(r"(?<!\d)([01]?\d)[-_.]([0-3]?\d)[-_.](20[0-2]\d)(?!\d)"),  # MM-DD-YYYY
    re.compile(r"(?<!\d)([01]?\d)[-_.]([0-3]?\d)[-_.]([0-2]\d)(?!\d)"),    # MM-DD-YY
]
_YEAR = re.compile(r"(?<!\d)(20[0-2]\d)(?!\d)")


def _norm_date(y: str, m: str, d: str) -> str:
    y = ("20" + y) if len(y) == 2 else y
    try:
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return ""


def extract_date(text: str) -> tuple[str, str]:
    """Return (iso_date_or_'', year_or_'')."""
    for pat in _DATE_PATS:
        m = pat.search(text)
        if not m:
            continue
        g = m.groups()
        iso = _norm_date(g[0], g[1], g[2]) if g[0].startswith("20") else _norm_date(g[2], g[0], g[1])
        if iso:
            return iso, iso[:4]
    ym = _YEAR.search(text)
    return "", (ym.group(1) if ym else "")


def classify_document(url: str, anchor: str = "") -> dict:
    """Typify a document. Returns board/doctype/date/year/meeting_id + flags.

    AgendaCenter URLs get authoritative doctype+date+meeting_id (board stays '' — it
    lives in the empty anchor); everything else is inferred wide-net from url+anchor.
    """
    hay = f"{url} {anchor}"

    ac = _AGENDACENTER.search(url)
    if ac:
        doctype = ac.group(1).lower()
        iso = _norm_date(ac.group(4), ac.group(2), ac.group(3))
        # board still worth a try from anchor (crawl-sourced AgendaCenter links)
        board = _match_board(anchor) if anchor else ""
        return {"board": board, "doctype": doctype, "date": iso, "year": iso[:4],
                "meeting_id": ac.group(5), "agendacenter": True}

    board = _match_board(hay)
    doctype = ""
    for key, rx in _DOCTYPE_RES:
        if rx.search(hay):
            doctype = key
            break
    iso, year = extract_date(hay)
    return {"board": board, "doctype": doctype, "date": iso, "year": year,
            "meeting_id": "", "agendacenter": False}


def _match_board(text: str) -> str:
    for key, _lbl, rx in _BOARD_RES:
        if rx.search(text):
            return key
    return ""


BOARD_LABEL = {k: lbl for k, lbl, _ in BOARDS}
