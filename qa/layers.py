"""Four layers of QA, built from first principles.

There are exactly four ways a record can be wrong, and they are ordered.
Each layer only matters if the one before it passed, because no later check
can recover from a wrong document.

    Layer 0  Is this the right document?
    Layer 1  Is the reading grounded in it?
    Layer 2  Does the arithmetic hold?
    Layer 3  Is it in scope and complete?

Every check returns the same shape -- stem, layer, check, verdict, evidence --
and evidence is always a verbatim quote or a computed comparison, never a bare
assertion.  That one format is what lets the nightly run, the dashboard and the
adjudication ledger share a vocabulary.

Two rules govern what belongs here:

  * A check asserts about numbers in the record, never about pipeline plumbing.
    If it would still pass on a corpus holding 49 arithmetically impossible
    contests, it is not earning its runtime.

  * A new check retires one, or states why not.

READ-ONLY.  Writes a report and nothing else.

    python -m qa.layers                 # whole corpus
    python -m qa.layers --stem Athol2023
"""

import argparse
import collections
import csv
import glob
import json
import os
import re
import statistics
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, UNKNOWN, NOTE = "PASS", "FAIL", "UNKNOWN", "NOTE"
# An overridden finding is NOT a passing one.  It keeps its own verdict so it
# stays counted and reviewable; a mechanism that turned findings into passes
# would hide how much of the corpus rests on somebody's judgement call.
OVERRIDDEN = "OVERRIDDEN"

# A tally row is a line in the return that counts marks, not a person.
TALLY_ROWS = {"blanks", "blank", "others", "other", "write-ins", "write-in",
              "write ins", "writein", "total", "totals", "scattering",
              "scattered", "all others"}

# The word "district" does double duty and that is the whole trap.  A precinct
# or ward divides ONE town and its numbers sum to the town total.  A regional
# district spans SEVERAL towns and its numbers routinely exceed the host town's
# ballots, legitimately.  Until `scope` is a real field this has to be inferred
# from the office name, which is exactly the guessing the field will remove.
RE_REGIONAL = re.compile(
    r"REGION|VOCATION|TECHNICAL|AGRICULTUR|COOPERATIVE|\bRSD\b|"
    r"GREATER\s|SCHOOL\s+DISTRICT|DISTRICT\s+SCHOOL", re.I)
RE_SUBTOWN = re.compile(
    r"\bDIST\b|\bDISTRICT\s+[0-9A-F]\b|\bWARD\b|\bPCT\b|\bPRECINCT\b|\bTMM\b", re.I)

# Offices that are not municipal and must never appear in this corpus.
RE_NOT_MUNICIPAL = re.compile(
    r"GOVERNOR|SENATOR IN CONGRESS|REPRESENTATIVE IN CONGRESS|"
    r"PRESIDENT OF THE UNITED STATES|PRESIDENTIAL|"
    r"ATTORNEY GENERAL|SECRETARY OF STATE|STATE SENATOR|STATE REPRESENTATIVE|"
    r"COUNTY COMMISSIONER|REGISTER OF|DISTRICT ATTORNEY|SHERIFF|"
    r"GOVERNOR'S COUNCIL|ASSEMBLY DELEGATE|"
    # Massachusetts calls its legislature the General Court.  These are the
    # state office names as they are actually printed on a MA ballot.
    # "General Court" is what Massachusetts calls its legislature, so SENATOR
    # and REPRESENTATIVE IN GENERAL COURT are the state offices as printed on a
    # MA ballot.  COUNCILLOR DISTRICT is NOT one: Boston, Lynn and Worcester
    # elect city councillors by district, which is municipal.  Including it
    # flagged 6 town-years 43 times and reported them as state elections.
    r"IN GENERAL COURT|GENERAL COURT\b", re.I)


# ---------------------------------------------------------------- helpers

def name_of(cand):
    return str(cand.get("name_original") or cand.get("name") or "").strip()


def is_tally_row(cand):
    if cand.get("tally_row") is True:
        return True
    return name_of(cand).lower() in TALLY_ROWS


def votes_of(cand):
    v = cand.get("votes")
    return v if isinstance(v, int) else None


def figure_found(value, text):
    """Is this vote count printed in `text`, in either spelling a clerk uses?

    A figure has two spellings on a page and the check only knew one.  Agawam
    2021 prints `WILLIAM SAPELLI 4,359 81.31%`, Wellesley 2021 prints
    `MARK G. KAPLAN 456 554 377 546 373 286 253 508 3,353`, Milton 2026 prints
    `KEVIN B. CHRISOM, JR. ... 2,517` -- and a search for `4359` finds none of
    them.  The record stores an integer, the document groups its thousands, and
    a grounded figure read as ungrounded is the failure this project cares most
    about: it makes a correct reading look unread, and 112 records were failing
    `figures_grounded` for no other reason.

    So try the grouped spelling too.  This can only ever un-flag -- every string
    that matched before still matches -- and it is not looser than the plain
    form: `(?<![\\d,])2,517(?![\\d,])` is as exact about its digits as `\\b2517\\b`,
    and the lookarounds are what stop `517` matching inside `2,517`.
    """
    if value is None:
        return False
    if re.search(r"\b" + str(int(value)) + r"\b", text):
        return True
    if abs(int(value)) < 1000:
        return False
    return bool(re.search(r"(?<![\d,])" + f"{int(value):,}" + r"(?![\d,])", text))


def scope_of(contest):
    """at_large | sub_town | regional_district.

    Prefer the stored field.  Inference from the office name is the fallback
    for records the schema migration has not reached, and it is exactly the
    guessing the field exists to remove -- letter-named districts and regional
    committees both slipped past it.
    """
    stored = contest.get("scope")
    if stored in ("at_large", "sub_town", "regional_district"):
        return stored
    office = str(contest.get("office_original") or contest.get("office") or "")
    if RE_REGIONAL.search(office):
        return "regional_district"
    if (contest.get("district_original") or "").strip() or RE_SUBTOWN.search(office):
        return "sub_town"
    return "at_large"


def marks_in(contest):
    """Total marks printed for a contest: candidate votes plus tally rows.

    Sentinels (-1 uncontested, -3 write-in winner) are excluded -- they are
    not counts, and summing them is how a contest quietly totals negative.
    """
    total = 0
    for c in contest.get("candidates") or []:
        v = votes_of(c)
        if v is not None and v > 0:
            total += v
    return total


def blanks_printed(contest):
    stored = contest.get("blanks_printed")
    if isinstance(stored, bool):
        return stored
    return any(name_of(c).lower() in ("blanks", "blank")
               for c in contest.get("candidates") or [])


def has_ballot_candidate(contest):
    """A contest with no named candidate polling above zero was a write-in
    scramble.  Its printed tally does not cover every ballot and it cannot
    speak for the ballot count."""
    for c in contest.get("candidates") or []:
        if is_tally_row(c):
            continue
        v = votes_of(c)
        if v is not None and v > 0:
            return True
    return False


# What is left of a text once the things that are not a reading are removed:
# extractor placeholders standing in for a picture, empty markdown table rules,
# and the replacement character a mis-decoded file is full of.  A placeholder is
# not an extraction (docs/notes/civicatlas-unsearchable-blind-spot).
RE_NOT_A_READING = re.compile(r"<!--.*?-->|^\s*\|[\s|:-]*\|\s*$|�",
                              re.S | re.M)


def readable_chars(text):
    """Letters and digits in `text` that came from the page rather than the tool."""
    return len(re.sub(r"[^A-Za-z0-9]", "", RE_NOT_A_READING.sub(" ", text)))



RE_RETURN_VOCABULARY = tuple(re.compile(p, re.I) for p in (
    r"\bblanks?\b",
    r"\bwrite[\s.-]?ins?\b",
    r"\bballots?\s+(?:were\s+)?cast\b",
    r"\bvotes?\s+cast\b",
    r"\b(?:precincts?|prec\.?\s*\d|wards?\s*\d)\b",
    r"\bvote\s+for\s+(?:no\s+more\s+than\s+)?"
    r"(?:one|two|three|four|five|\d+)\b",
    r"\b(?:was|were)\s+elected\b",
    r"\bofficial\s+(?:election\s+)?results\b",
    r"\btally\s+sheet\b",
    r"\bvoter\s+turnout\b",
))

def return_vocabulary(text):
    """Verbatim quotes of the tally words this text uses, one per distinct term."""
    quotes = []
    for rx in RE_RETURN_VOCABULARY:
        m = rx.search(text)
        if m:
            quotes.append(text[max(0, m.start() - 25):m.end() + 25].strip())
    return quotes

def document_text(stem):
    """EVERY reading of the held document, joined, and which ones they were.

    We hold up to three readings of ONE document -- the published OCR of the
    pixels, the markdown extraction, and pdftotext over the same `_d0` PDF -- and
    each is lossy in a different place.  Taking the first that exists asks the
    wrong question, because there is no reading that is right in general:

        Boston 2021   raw_ocr is 4,231 chars of collapsed table
                      ("pvescsr | oa ez] oira]ar] roe] eal sos]"), while pdftext
                      reads "MICHELLE WU  3878 3002 ... 91794".  0 of 25 names
                      and 0 of 36 figures grounded, and the document was right
                      all along.
        Auburn 2022   markdown extracts the heading as "MAY 1 7 , 202 2";
                      pdftext reads "MAY 17, 2022".  The year check failed on a
                      document that prints the year.
        Hopedale 2025 raw_ocr is "<!-- image -->" and nothing else.

    So preferring raw_ocr blinds the checks on a born-digital PDF, and preferring
    pdftext blinds them on a scan, which is why `unsearchable-blind-spot` was
    written.  The document is the thing being asked about and a reading is only a
    lossy view of it, so the union of the readings is strictly closer to the
    document than any one of them.  It can only ever un-flag: every string that
    matched one reading still matches the join.

    Returns (text, source) where source names the readings actually searched, so
    a failure still says where we looked.
    """
    parts, used = [], []
    for name, rel in (("raw_ocr", f"data/raw_ocr/{stem}.txt"),
                      ("markdown", f"data/markdown/{stem}.md"),
                      ("pdftext", f"data/pdftext/{stem}.txt")):
        p = os.path.join(BASE, rel)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            t = fh.read()
        if t.strip():
            parts.append(t)
            used.append(name)
    # A file can be non-empty and hold no reading: Hopedale2025's OCR is 32
    # bytes, both of them "<!-- image -->"; Dunstable2025's markdown is 1,117
    # replacement characters out of 1,255.  Joining such a file into the union
    # is harmless -- it adds no string anything can match -- but letting it
    # stand as the ONLY reading is not, because `document_held` would then be
    # answering about the extractor rather than the document.  So the union
    # carries everything and the bar decides one thing: whether we hold a
    # reading at all.  30 characters is a heading, not a return.
    if not parts or max(readable_chars(t) for t in parts) < 30:
        return None, None
    return re.sub(r"\s+", " ", "\n".join(parts)), "+".join(used)


def municipality_of(stem):
    return re.sub(r"\d{4}$", "", stem)


def year_of(stem):
    m = re.search(r"(\d{4})$", stem)
    return m.group(1) if m else None


RE_MONTH = (r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?")


def year_found(year, text):
    """Where this year is printed in `text`, in either spelling a clerk uses.

    A clerk dates a return the way a clerk writes a date, and half of them use
    two digits.  Wilmington heads four consecutive years
    "TOWN OF WILMINGTON - ANNUAL TOWN ELECTION 24-Apr-21" (and 23-Apr-22,
    22-Apr-23, 27-Apr-24); Becket 2025 heads "ANNUAL TOWN ELECTION 05/17/25";
    Boxborough 2026 "BOXBOROUGH TOWN ELECTION Results 2-Jun-26"; New Braintree
    2023 "FINAL RESULTS ANNUAL TOWN ELECTION 5/1/23 -- 129 VOTERS".  Every one
    of those documents prints its year, and 34 of them were reported as
    undated because the check knew only the four-digit spelling.

    The two-digit form is admitted only as part of a whole date -- a month and
    a day beside it -- which makes it STRICTER than the four-digit match it
    joins, not looser: a bare "2021" grounds on anything, "24-Apr-21" grounds on
    a date.  So this can only un-flag.

    Returns the match, or None, so the caller can quote what it found.
    """
    if not year:
        return None
    m = re.search(re.escape(year), text)
    if m:
        return m
    yy = year[2:]
    for pat in (r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-]" + yy + r"\b",
                RE_MONTH + r"\s*[-/]?\s*(?:0?[1-9]|[12]\d|3[01]),?\s*[-/]?\s*" + yy + r"\b",
                r"\b(?:0?[1-9]|[12]\d|3[01])\s*[-/]\s*" + RE_MONTH + r"\s*[-/]\s*" + yy + r"\b"):
        m = re.search(pat, text, re.I)
        if m:
            return m
    return None


# ---------------------------------------------------------------- layer 0

def layer0_right_document(stem, record, text, source):
    """Is this the right document?

    Three things must be true, each with a verbatim quote: it names this town,
    it carries this year, and it is a RETURN rather than a notice or an index.
    No later check can recover from failing here, which is why it runs first.
    """
    out = []
    if text is None:
        pdf = os.path.join(BASE, "data", "pdfs", stem + ".pdf")
        if os.path.exists(pdf):
            out.append((stem, 0, "document_held", NOTE,
                        "PDF held but no text extracted; run extraction to check it"))
        else:
            out.append((stem, 0, "document_held", FAIL, "no document of any kind held"))
        return out

    town = municipality_of(stem)
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", town).strip()
    hit = None
    for cand in {town, spaced, town.replace("_", " ")}:
        m = re.search(re.escape(cand), text, re.I)
        if m:
            hit = text[max(0, m.start() - 30):m.end() + 30].strip()
            break
    out.append((stem, 0, "document_self_identifies",
                PASS if hit else NOTE,
                f"...{hit}..." if hit else
                f"document never prints '{town}'; identity rests on the citation alone"))

    year = year_of(stem)
    # No word boundary on the four-digit form: OCR strips spaces, and Medford
    # 2025 prints its heading as OFFICIAL2025GENERALMUNICIPALELECTIONRESULTS,
    # where a boundary cannot match.  Two digits inside a date count too --
    # see year_found.
    m = year_found(year, text)
    out.append((stem, 0, "carries_the_year",
                PASS if m else FAIL,
                f"...{text[max(0,m.start()-40):m.end()+40].strip()}..." if m
                else f"'{year}' does not appear in {source}, "
                     f"in that spelling or as a date ending {year[2:]}"))

    # A preliminary is not junk and it is not an annual election.  Like a
    # special it is cordoned off under its own name -- P<Muni><YYYYMMDD>, in
    # data/preliminaries/ with a row in preliminaries_register.csv -- and is
    # tracked without being published.  What makes it a defect is only that it
    # sits in an ANNUAL town-year slot, which a preliminary must never occupy.
    # The fix is to register and split it, never to discard it.
    #
    # But the WORD does double duty, and matching it alone was wrong about 19 of
    # the 20 records it flagged.  A PRELIMINARY ELECTION is the Massachusetts
    # municipal primary, a distinct election.  "Preliminary results" are the
    # unofficial figures of ANY election, announced on the night and finalised
    # later, and that is what nineteen of these documents were saying:
    #
    #   Needham 2026  "Preliminary Results of Annual Town Election 4/14/2026"
    #   Acton 2026    "Annual Town Election PRELIMINARY April 28, 2026"
    #   Acushnet 2026 "the figures listed below are preliminary and will be
    #                  finalized within four days following the election"
    #   Carlisle 2026 "The 2026 Annual Town Election was held Tuesday, June 2,
    #                  2026 ... PRELIMINARY RESULTS"
    #
    # So the word must name the ELECTION, not the figures: "preliminary" within
    # two words of "election", and not the phrase "preliminary ... election
    # results", which is how Holliston 2025 and Carlisle 2024 head a full annual
    # slate.  This is strictly narrower than the old pattern -- it can only
    # un-flag, never flag something new.  Salem 2023 is what still matches, and
    # it is a 21-page compilation whose first page is a special preliminary; a
    # compilation never gets a whole-document verdict, so it carries an override
    # rather than a weaker check.
    head = text[:600]
    m = re.search(r"\bpreliminary\s+(?:\w+\s+){0,2}?election\b(?!\s+results)",
                  head, re.I)
    if m:
        quote = head[max(0, m.start() - 40):m.end() + 40].strip()
        out.append((stem, 0, "preliminary_in_an_annual_slot", FAIL,
                    f"heading names a PRELIMINARY ELECTION: ...{quote}...; "
                    "register it as P<Muni><YYYYMMDD> in data/preliminaries/ "
                    "and find the annual for this town-year"))

    # "Is it a return?" cannot be answered by counting digits: Alford 2021 is a
    # real return with 53 ballots cast and barely any numbers, and 235 town-years
    # are legitimately sourced from news reports rather than returns.  The honest
    # test is whether the document supports the record AT ALL.  Zero support is a
    # wrong document -- that is what Quincy, Weston and Salisbury looked like.
    # Partial support is a reading problem and belongs to layer 1, not here.
    names, figures = [], []
    for e in record.get("elections") or []:
        for c in e.get("candidates") or []:
            if not is_tally_row(c) and name_of(c):
                names.append(name_of(c))
            v = votes_of(c)
            if v is not None and v > 0:
                figures.append(v)

    def found(n):
        parts = [x for x in re.split(r"[^A-Za-z]+", n) if len(x) > 2]
        return bool(parts) and all(re.search(re.escape(x), text, re.I) for x in parts[:2])

    n_hit = sum(1 for n in names if found(n))
    f_hit = sum(1 for v in figures if figure_found(v, text))
    if names or figures:
        ev = (f"{n_hit}/{len(names)} names and {f_hit}/{len(figures)} figures "
              f"located in {source}")
        if n_hit > 0 or f_hit > 0:
            out.append((stem, 0, "document_supports_record", PASS, ev))
        else:
            # Zero support is a statement about the TEXT, and the text may be a
            # collapsed OCR of exactly the right document.  Boston 2021's tables
            # read as `[canomares [+ [?]2]*]s]*]7]` and nothing in the record is
            # findable, yet the document is the return.  So when the text still
            # speaks the vocabulary of a return, say the record is unread here
            # -- still to be checked -- rather than contradicted.  Brimfield 2022
            # is why the bar is two distinct terms: its text is Town Meeting
            # minutes mentioning `the Annual Town Election` once, in a bylaw
            # article listing which officers get elected, and nothing else.  It
            # stays FAIL, as it should.
            quotes = return_vocabulary(text)
            if len(quotes) >= 2:
                out.append((stem, 0, "document_supports_record", UNKNOWN,
                            f"{ev}; but the document says it is a return -- "
                            + "; ".join(f'"{q}"' for q in quotes[:3])
                            + " -- so this text cannot support anything and the "
                              "record is unread here, not contradicted. Re-OCR "
                              "the document (python -m qa.ocr_queue --add "
                              f"{stem})"))
            else:
                out.append((stem, 0, "document_supports_record", FAIL, ev))
    return out


# ---------------------------------------------------------------- layer 1

def layer1_grounded(stem, record, text, source):
    """Is the reading grounded in the document?

    Every name and every figure must be findable in the document text.  Pure
    string matching, no model judgement -- which is what makes it trustworthy
    and cheap enough to run nightly over the whole corpus.

    Grounding matches `name_original`, never the canonical name.  If a clerk
    misspelled a name the DOCUMENT holds the misspelling, and the check must
    agree with the document.
    """
    if text is None:
        return [(stem, 1, "grounded", UNKNOWN, "no document text held")]

    names, figures = [], []
    for e in record.get("elections") or []:
        for c in e.get("candidates") or []:
            if not is_tally_row(c):
                n = name_of(c)
                if n:
                    names.append(n)
            v = votes_of(c)
            if v is not None and v > 0:
                figures.append(v)

    def name_found(n):
        parts = [p for p in re.split(r"[^A-Za-z]+", n) if len(p) > 2]
        if not parts:
            return True
        return all(re.search(re.escape(p), text, re.I) for p in parts[:2])

    n_ok = sum(1 for n in names if name_found(n))
    f_ok = sum(1 for v in figures if figure_found(v, text))

    out = []
    if names:
        out.append((stem, 1, "names_grounded",
                    PASS if n_ok == len(names) else FAIL,
                    f"{n_ok}/{len(names)} names located in {source}"))
    if figures:
        out.append((stem, 1, "figures_grounded",
                    PASS if f_ok == len(figures) else FAIL,
                    f"{f_ok}/{len(figures)} figures located in {source}"))
    return out


# ---------------------------------------------------------------- layer 2

def derive_ballots(record):
    """Ballots cast, derived from the contests rather than asked of a model.

    Every municipality-wide single-seat contest that prints its blanks sits on
    the same ballot, so each implies the same figure.  Deriving it removes a
    hallucination site for a value we already hold, and where the document DOES
    print a count we get a free comparison instead of a second opinion.

    A contest only qualifies if it is at-large, single-seat, prints blanks and
    had a candidate on the ballot.  Returns (ballots, evidence, contributors).
    """
    est = []
    for e in record.get("elections") or []:
        if scope_of(e) != "at_large":
            continue
        if (e.get("num_winners") or 1) != 1:
            continue
        if not blanks_printed(e) or not has_ballot_candidate(e):
            continue
        m = marks_in(e)
        if m:
            est.append((m, str(e.get("office_original") or e.get("office") or "")[:40]))
    if len(est) < 2:
        return None, f"only {len(est)} qualifying contest(s); cannot derive", est
    counts = collections.Counter(v for v, _ in est)
    top, n = counts.most_common(1)[0]
    # Consensus needs a quorum.  Two contests that disagree are a disagreement,
    # not a derivation -- picking one is how stale data becomes confident data.
    if n < 2:
        return None, f"{len(est)} contests, no two agree: {sorted(counts)}", est
    return top, f"{n} of {len(est)} contests agree on {top}", est


def layer2_arithmetic(stem, record):
    """Does the arithmetic hold?

    In nearly every election a voter may mark a contest once per seat.  The
    direction of a discrepancy matters more than its size, and the asymmetry is
    a fact about ballots rather than a tuned threshold:

        marks >  ballots x seats   impossible.  An error.
        marks == ballots x seats   the digits were probably read faithfully.
        marks <  ballots x seats   usually legitimate: blanks or write-ins not
                                   tallied.  Describe it; do not flag it.

    Closure is evidence about FIGURES only, and two blind spots matter:

    It cannot see a FUSED race.  If block A closes at ballots x k1 and block B
    at ballots x k2, then A+B closes at ballots x (k1+k2) -- merging preserves
    the identity exactly.  Provincetown 2025 ran two races together into a
    three-seat Select Board and closed perfectly at 1623 = 541 x 3.  Fusion is a
    property of the document's LAYOUT, so only the document answers it.

    It cannot see a LOST NAME.  Needham Precinct D summed to the printed total
    while a candidate had been dropped: her votes captured, her name not.

    A closing contest means "the digits are probably right", never "the record
    is right".  A flag is only ever cleared after review and documentation.
    """
    out = []
    ballots, why, contributors = derive_ballots(record)
    out.append((stem, 2, "ballots_derivable",
                PASS if ballots else UNKNOWN, why))
    if not ballots:
        return out

    for e in record.get("elections") or []:
        scope = scope_of(e)
        office = str(e.get("office_original") or e.get("office") or "")[:44]
        if scope == "regional_district":
            out.append((stem, 2, "regional_exempt", NOTE,
                        f"{office}: spans several towns; ballot arithmetic does not apply"))
            continue
        if scope == "sub_town":
            continue                       # summed against the town total instead
        if not blanks_printed(e):
            continue                       # inequality case, cannot test exactly
        seats = e.get("num_winners") or 1
        m = marks_in(e)
        if not m:
            continue
        expect = ballots * seats
        if m > expect:
            out.append((stem, 2, "marks_exceed_ballots", FAIL,
                        f"{office}: {m} marks > {ballots} ballots x {seats} seats = {expect}"))
        elif m == expect:
            out.append((stem, 2, "contest_closes", PASS,
                        f"{office}: {m} == {ballots} x {seats}"))
        else:
            out.append((stem, 2, "tally_incomplete", NOTE,
                        f"{office}: {m} of {expect}; {expect - m} marks not tallied"))
    return out


# ---------------------------------------------------------------- layer 3

def layer3_scope(stem, record, corpus_offices):
    """Is it in scope and complete?"""
    out = []
    offices = []
    for e in record.get("elections") or []:
        o = str(e.get("office_original") or e.get("office") or "")
        offices.append(o)
        if RE_NOT_MUNICIPAL.search(o):
            out.append((stem, 3, "municipal_only", FAIL,
                        f"non-municipal office present: {o[:60]}"))

    town = municipality_of(stem)
    peers = [n for s, n in corpus_offices.items()
             if municipality_of(s) == town and s != stem]
    if peers and offices:
        med = statistics.median(peers)
        if med and len(offices) < med * 0.5:
            out.append((stem, 3, "office_count_consistent", FAIL,
                        f"{len(offices)} contests; this town's other years median {med:.0f}"))
        else:
            out.append((stem, 3, "office_count_consistent", PASS,
                        f"{len(offices)} contests; median {med:.0f} in other years"))
    return out


# ---------------------------------------------------------------- runner

def cross_year_duplicates(records):
    """Two years of one town must not hold the same (name, votes) set.

    A citation that is a PAGE rather than a document can silently retarget --
    a town CMS reusing a slug serves the newest post at an old permalink -- and
    this is the only check that catches it.
    """
    out = []
    by_town = collections.defaultdict(list)
    for stem, rec in records.items():
        pairs = frozenset(
            (name_of(c), votes_of(c))
            for e in (rec.get("elections") or [])
            for c in (e.get("candidates") or [])
            if not is_tally_row(c) and votes_of(c) is not None
        )
        if len(pairs) >= 4:
            by_town[municipality_of(stem)].append((stem, pairs))
    for town, entries in by_town.items():
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                a, pa = entries[i]
                b, pb = entries[j]
                shared = pa & pb
                if len(shared) == len(pa) == len(pb):
                    out.append((a, 3, "cross_year_duplicate", FAIL,
                                f"identical to {b}: all {len(pa)} (name, votes) pairs match"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stem", help="check one town-year")
    ap.add_argument("--out", default=os.path.join(BASE, "qa", "layers_report.csv"))
    ap.add_argument("--compare-to", metavar="REPORT",
                    help="diff this run against an earlier report, per check. "
                         "A check fix must only ever UN-flag; this is how you "
                         "show that instead of asserting it.")
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(BASE, "data", "json", "*.json")))
    if args.stem:
        paths = [p for p in paths if os.path.basename(p)[:-5] == args.stem]
        if not paths:
            sys.exit(f"no such stem: {args.stem}")

    records, rows = {}, []
    for p in paths:
        stem = os.path.basename(p)[:-5]
        try:
            with open(p, encoding="utf-8") as fh:
                rec = json.load(fh)
        except Exception as exc:
            rows.append((stem, 0, "record_readable", FAIL, f"{type(exc).__name__}: {exc}"))
            continue
        records[stem] = rec

    counts = {s: len(r.get("elections") or []) for s, r in records.items()}

    for stem, rec in records.items():
        text, source = document_text(stem)
        rows += layer0_right_document(stem, rec, text, source)
        rows += layer1_grounded(stem, rec, text, source)
        rows += layer2_arithmetic(stem, rec)
        rows += layer3_scope(stem, rec, counts)
    rows += cross_year_duplicates(records)

    # An override applies only where its reasoning was formed against the
    # document we still hold.  A replaced document retires the reasoning.
    try:
        from qa import overrides as _ov
        ovr = _ov.load()
    except Exception:
        ovr = {}
    if ovr:
        applied = 0
        for i, r in enumerate(rows):
            key = (r[0], r[2])
            row = ovr.get(key)
            if row and r[3] in (FAIL, UNKNOWN):
                pdf = os.path.join(BASE, "data", "pdfs", r[0] + ".pdf")
                if _ov.applies(row, pdf):
                    rows[i] = (r[0], r[1], r[2], OVERRIDDEN,
                               f'{r[4]}  [OVERRIDDEN: {row["why"][:90]}]')
                    applied += 1
        if applied:
            print(f"overrides applied: {applied}")

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["stem", "layer", "check", "verdict", "evidence"])
        w.writerows(rows)

    print(f"town-years checked: {len(records)}")
    print(f"rows written:       {len(rows)}  ->  {os.path.relpath(args.out, BASE)}")
    print()
    tally = collections.Counter((r[1], r[2], r[3]) for r in rows)
    print(f"{'layer':<6}{'check':<26}{'verdict':<9}{'count':>7}")
    print("-" * 50)
    for (layer, check, verdict), n in sorted(tally.items()):
        print(f"{layer:<6}{check:<26}{verdict:<9}{n:>7}")

    if args.compare_to:
        # A fix to a check has to be shown, not claimed.  The question is always
        # the same: did this only stop flagging things, or did it start flagging
        # something new?  The second is how a "fix" quietly changes the corpus.
        was = {}
        with open(args.compare_to, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                was[(r["stem"], r["check"])] = r["verdict"]
        now = {(r[0], r[2]): r[3] for r in rows}
        unflagged, newly, changed = [], [], []
        for key in set(was) | set(now):
            a, b = was.get(key), now.get(key)
            if a == b:
                continue
            if b in (None, "PASS") and a in ("FAIL", "UNKNOWN"):
                unflagged.append((key, a, b))
            elif a in (None, "PASS") and b in ("FAIL", "UNKNOWN"):
                newly.append((key, a, b))
            else:
                changed.append((key, a, b))
        print()
        print(f"against {os.path.basename(args.compare_to)}:")
        print(f"  un-flagged      {len(unflagged)}")
        print(f"  newly flagged   {len(newly)}"
              f"{'   <-- a narrowing fix should show ZERO here' if newly else ''}")
        print(f"  changed verdict {len(changed)}")
        for (stem, check), a, b in newly[:12]:
            print(f"     NEW  {stem:<20} {check}  {a or '-'} -> {b}")
        for (stem, check), a, b in unflagged[:8]:
            print(f"     off  {stem:<20} {check}  {a} -> {b or '-'}")


if __name__ == "__main__":
    main()
