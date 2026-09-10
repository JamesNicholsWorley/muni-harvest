"""Derive the published record shape from a transcribed ATR return.

The transcription and the publication are deliberately different shapes. The
parse emits `_original` fields and nothing else, because a field that does not
exist cannot be invented; the site wants a canonical municipality and an ISO
date. Something has to close that gap, and this is it -- the second pass
`CLAUDE.md` describes, which reads only `_original` fields, never sees the
document, and can be re-run and corrected when it gets something wrong.

Three rules hold it honest.

**It never edits an original.** Derived values are added alongside; the
transcription is carried through untouched, so a grounding check downstream
still has the characters the page actually printed.

**It refuses rather than guesses.** A municipality it cannot match against the
known list, or a date it cannot parse, comes back unresolved with a reason.
An unresolved record is visible; a wrongly-resolved one is not.

**The page outranks the filename.** Where `date_original` gives a year and the
stem gives another, the page wins and the disagreement is recorded -- a town
report is named for its fiscal year and 8% of this corpus prints a year that is
not the one in its filename.
"""
import csv
import io
import os
import re

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}


def load_municipalities(path):
    """{normalised name -> canonical name} from the inventory."""
    out = {}
    with io.open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("municipality") or row.get("Municipality") or "").strip()
            if name:
                out[re.sub(r"[^a-z]", "", name.lower())] = name
    return out


def canonical_municipality(printed, stem_town, known):
    """(canonical, source, note). The printed name is preferred and checked.

    The printed name exists to disagree with the filename, so it is tried
    first -- but a page reading "TOWN OF STERLING" has to resolve to Sterling,
    and one that resolves to nothing must say so rather than fall back
    silently, because a silent fallback is exactly how a wrong-town record gets
    published looking correct.
    """
    def norm(s):
        s = (s or "").strip()
        # A page heads itself in several ways for the same town: TOWN OF
        # STERLING, ARLINGTON MASSACHUSETTS, "Amherst, MA". Stripping the
        # framing is not a guess about which town it is -- the letters that
        # remain still have to match a known municipality exactly, and a page
        # naming somewhere we do not recognise still fails.
        s = re.sub(r"^(the\s+)?(town|city)\s+of\s+", "", s, flags=re.I)
        s = re.sub(r"[,\s]+(massachusetts|mass\.?|ma)\s*$", "", s, flags=re.I)
        s = re.sub(r"\s+(annual|town|election).*$", "", s, flags=re.I)
        return re.sub(r"[^a-z]", "", s.lower())

    if printed:
        hit = known.get(norm(printed))
        if hit:
            note = ("" if norm(printed) == norm(stem_town)
                    else "page says %r, filename says %r" % (printed, stem_town))
            return hit, "printed", note
    hit = known.get(norm(stem_town))
    if hit:
        return hit, "filename", ("the page did not name the town"
                                 if not printed else
                                 "the printed name %r matched nothing" % printed)
    return None, None, "neither %r nor %r matches a known municipality" % (
        printed, stem_town)


def _four_digit_year(digits):
    """2018 from "18" or from "2018". The corpus runs 2000-2020 and no ATR in
    it prints a nineteen-hundreds two-digit year, so there is nothing here to
    choose between; a year that lands outside the corpus is refused below
    rather than nudged into it."""
    n = int(digits)
    return n if n >= 100 else 2000 + n


ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
            "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
            "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
            "fifteenth": 15, "sixteenth": 16, "seventeenth": 17,
            "eighteenth": 18, "nineteenth": 19, "twentieth": 20,
            "thirtieth": 30}
UNITS = {k: v for k, v in ORDINALS.items() if v < 10}


def _word_ordinal(words):
    """25 from "twenty fifth", "twenty-fifth" or "TWENTY NINTH". None if not one.

    A clerk writing the election date out in full is writing a legal notice,
    and the notice is often the only place the day appears -- Plymouth 2010
    prints nothing but "Saturday, the Eighth Day of May, 2010" and Natick 2016
    nothing but "TUESDAY, THE TWENTY NINTH DAY OF MARCH 2016".
    """
    t = words.lower().replace("-", " ")
    m = re.search(r"\b(twenty|thirty)\s+(%s)\b" % "|".join(UNITS), t)
    if m:
        return (20 if m.group(1) == "twenty" else 30) + UNITS[m.group(2)]
    for word, n in ORDINALS.items():
        if re.search(r"\b%s\b" % word, t):
            return n
    return None


def iso_date(printed, stem_year):
    """(iso, note). None when the page prints nothing parseable."""
    if not printed:
        return None, "the page printed no date"
    t = printed.strip()
    # "April 25th, 2015" is the same date as "April 25, 2015".
    t = re.sub(r"(\d{1,2})(st|nd|rd|th)\b", lambda mm: mm.group(1), t, flags=re.I)
    # "the twenty-fifth day of April" and "the 25th day of April" both
    # reduce to the same month-day-year the branch below already reads. Only
    # the digit form ever did: the comment claimed the word form and the
    # pattern demanded \d, which is why five towns whose clerks write the date
    # out in full came back undated.
    t = re.sub(r"\bthe\s+(\d{1,2})\s+day\s+of\s+([A-Za-z]+)",
               lambda mm: mm.group(2) + " " + mm.group(1), t, flags=re.I)
    t = re.sub(r"\bthe\s+((?:twenty|thirty)[\s-]+[a-z]+|[a-z]+)\s+day\s+of\s+"
               r"([A-Za-z]+)",
               lambda mm: ("%s %s" % (mm.group(2), _word_ordinal(mm.group(1)))
                           if _word_ordinal(mm.group(1)) else mm.group(0)),
               t, flags=re.I)
    # "11 May 2017" and "7 MAY 2019" are the same dates as "May 11, 2017" and
    # "May 7, 2019"; only the order differs, and the month name is unambiguous
    # in either position, so nothing is being guessed by reordering.
    t = re.sub(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b",
               lambda mm: ("%s %s %s" % (mm.group(2), mm.group(1), mm.group(3))
                           if mm.group(2).lower() in MONTHS else mm.group(0)),
               t)
    # "15-May-18" and "31-Mar-03" are what a spreadsheet prints by default,
    # and eight towns' returns were exported from one. The month is named, so
    # the surrounding numbers cannot be transposed: the leading one is the day.
    m = re.match(r"^\s*(\d{1,2})[-/]([A-Za-z]{3,9})[-/](\d{2}|\d{4})\s*$", t)
    if m and m.group(2)[:3].lower() in [k[:3] for k in MONTHS]:
        month = [k for k in MONTHS if k.startswith(m.group(2)[:3].lower())][0]
        t = "%s %s %s" % (month, m.group(1), _four_digit_year(m.group(3)))
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})\s*,?\s*(\d{4})", t)
    if m and m.group(1).lower() in MONTHS:
        y, mo, d = int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))
    else:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            # 04/06/2002 and 5/21/19. American order, which is what a
            # Massachusetts clerk writes; a day over 12 in the first
            # position would be unreadable either way and is rejected
            # by the plausibility check below rather than swapped. A
            # two-digit year is only ever this century here -- the corpus
            # starts in 2000 -- so widening it invents no ambiguity.
            m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})\b", t)
            if not m:
                return None, "could not read a date from %r" % printed[:60]
            mo, d, y = (int(m.group(1)), int(m.group(2)),
                        _four_digit_year(m.group(3)))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None, "implausible date in %r" % printed[:60]
    # A pre-2021 ATR covers 2000-2020; the fiscal-year offset moves that
    # by a year at most. 1974 and 2107 both appeared, and both are
    # misreads of a four-digit number that would have published a
    # town-year with no election in it.
    if not (1999 <= y <= 2021):
        return None, ("year %d is outside the 2000-2020 corpus; "
                      "read from %r" % (y, printed[:50]))
    # A town report is named for its fiscal year, so the page and the filename
    # differ by a year in 8% of this corpus and the page wins. Two years is a
    # different animal: it is a section cut out of the wrong report or a
    # four-digit number misread, and calling it a fiscal offset publishes a
    # town-year holding another year's election. Barnstable 2010 read 2009 and
    # is right; Salem 2010 read 2018.
    if stem_year and abs(y - stem_year) > 1:
        return None, ("the page dates this %d and the filename says %d -- more "
                      "than the fiscal-year offset accounts for; read from %r"
                      % (y, stem_year, printed[:50]))
    # 1 January is what an empty date cell prints, not a date a town voted on.
    # Across 19,642 published 2021-2026 contests not one election falls in
    # January at all, and every January date in this corpus is 1 January.
    if (mo, d) == (1, 1):
        return None, ("1 January is what an empty date cell prints; no "
                      "election in either corpus falls in January. Read "
                      "from %r" % printed[:50])
    note = ""
    if stem_year and y != stem_year:
        note = ("the page dates this %d, the filename says %d -- the page wins"
                % (y, stem_year))
    return "%04d-%02d-%02d" % (y, mo, d), note


def bridge(stem, record, known):
    """A published-shape record, or None with reasons if it cannot be derived."""
    m = re.match(r"^(.*?)(\d{4})$", stem)
    stem_town, stem_year = (m.group(1), int(m.group(2))) if m else (stem, 0)
    problems = []

    muni, muni_src, note = canonical_municipality(
        record.get("municipality_original"), stem_town, known)
    if note:
        problems.append(note)
    date, dnote = iso_date(record.get("date_original"), stem_year)
    if dnote:
        problems.append(dnote)
    if not muni:
        return None, problems

    out = []
    for c in record.get("elections") or []:
        if not isinstance(c, dict):
            continue
        pub = {
            "municipality": muni,
            "date": date,
            "office_original": c.get("office_original"),
            "district_original": c.get("district_original") or "",
            "num_winners": c.get("num_winners"),
            "stage": "General",
            "type": "Regular",
            "scope": c.get("scope"),
            "candidates": [{"name_original": x.get("name_original"),
                            "votes": x.get("votes")}
                           for x in (c.get("candidates") or [])],
        }
        # Provenance travels with the record, not in a sidecar. A pre-2021
        # return was cut out of a 200-page report by a locator and read by the
        # cheap model; a 2021-2026 return came from a clerk's own document.
        # Publishing them side by side without saying which is which would let
        # the audit page stop distinguishing them.
        pub["provenance"] = "atr_section"
        pub["num_winners_source"] = c.get("num_winners_source")
        if c.get("seats_quote"):
            pub["seats_quote"] = c["seats_quote"]
        if c.get("printed_total") is not None:
            pub["printed_total"] = c["printed_total"]
        if c.get("is_recount"):
            pub["is_recount"] = True
        out.append(pub)

    doc = {
        "document": {
            "heading_verbatim": record.get("date_original") or "",
            "date_verbatim": record.get("date_original") or "",
            "election_type": "Regular",
            "election_type_evidence": "pre-2021 ATR section; type not stated",
            "municipality_printed": record.get("municipality_printed"),
            "municipality_source": muni_src,
        },
        "elections": out,
        "_source_stem": stem,
        "_provenance": "atr_section",
        "_bridge_problems": problems,
    }
    return doc, problems


def main():
    import argparse
    import glob
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--parsed", nargs="+", required=True)
    ap.add_argument("--municipalities", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    known = load_municipalities(a.municipalities)
    recs = {}
    for d in a.parsed:
        for p in glob.glob(os.path.join(d, "*.json")):
            x = json.load(io.open(p, encoding="utf-8"))
            r = x.get("record")
            if isinstance(r, dict) and isinstance(r.get("elections"), list):
                recs[x["stem"]] = r

    ok = unresolved = 0
    notes = {}
    if a.apply:
        os.makedirs(a.out, exist_ok=True)
    for stem, r in sorted(recs.items()):
        doc, problems = bridge(stem, r, known)
        if doc is None:
            unresolved += 1
            notes[stem] = problems
            continue
        ok += 1
        if problems:
            notes[stem] = problems
        if a.apply:
            io.open(os.path.join(a.out, stem + ".json"), "w",
                    encoding="utf-8").write(
                        json.dumps(doc, indent=1, ensure_ascii=False))
    print("  bridged        %d" % ok)
    print("  unresolved     %d" % unresolved)
    print("  carrying notes %d" % len(notes))
    for stem, ns in list(notes.items())[:6]:
        print("     %-18s %s" % (stem, ns[0][:74]))
    if not a.apply:
        print("\nDRY RUN. Nothing written. Pass --apply.")


if __name__ == "__main__":
    main()
