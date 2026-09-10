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
        s = re.sub(r"[,\s]+(massachusetts|mass\.?|ma)\s*"r"(\d{5}(-\d{4})?)?\s*$", "", s, flags=re.I)
        s = re.sub(r"\s+(annual|town|election).*$", "", s, flags=re.I)
        return re.sub(r"[^a-z]", "", s.lower())

    if printed:
        hit = known.get(norm(printed))
        if hit:
            note = ("" if norm(printed) == norm(stem_town)
                    else "page says %r, filename says %r" % (printed, stem_town))
            return hit, "printed", note
    # Text introduced by TOWN OF or CITY OF is CLAIMING to name a
    # municipality. If it claims to and the name is one we do not know, that is
    # evidence about the document -- Chelsea 2013's page reads TOWN OF
    # BENNINGTON, which is a real town in another state, and the record was
    # published as Chelsea. A heading that never claims to name a town says
    # nothing either way and the filename may stand.
    claims_a_town = bool(re.match(r"\s*(the\s+)?(town|city)\s+of\s+\S",
                                  printed or "", flags=re.I))
    if printed and claims_a_town:
        return None, None, ("the page names %r, which is not a Massachusetts "
                            "municipality -- this is probably another town's "
                            "document" % printed.strip())
    hit = known.get(norm(stem_town))
    if hit:
        return hit, "filename", ("the page did not name the town"
                                 if not printed else
                                 "the printed name %r matched nothing" % printed)
    return None, None, "neither %r nor %r matches a known municipality" % (
        printed, stem_town)


def iso_date(printed, stem_year):
    """(iso, note). None when the page prints nothing parseable."""
    if not printed:
        return None, "the page printed no date"
    t = printed.strip()
    # "April 25th, 2015" is the same date as "April 25, 2015".
    t = re.sub(r"(\d{1,2})(st|nd|rd|th)\b", lambda mm: mm.group(1), t, flags=re.I)
    # "the twenty-fifth day of April" and "the 25th day of April" both
    # reduce to the same month-day-year the branch below already reads.
    t = re.sub(r"\bthe\s+(\d{1,2})\s+day\s+of\s+([A-Za-z]+)",
               lambda mm: mm.group(2) + " " + mm.group(1), t, flags=re.I)
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})\s*,?\s*(\d{4})", t)
    if m and m.group(1).lower() in MONTHS:
        y, mo, d = int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))
    else:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            # 04/06/2002. American order, which is what a
            # Massachusetts clerk writes; a day over 12 in the first
            # position would be unreadable either way and is rejected
            # by the plausibility check below rather than swapped.
            m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
            if not m:
                return None, "could not read a date from %r" % printed[:60]
            mo, d, y = (int(m.group(1)), int(m.group(2)),
                        int(m.group(3)))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None, "implausible date in %r" % printed[:60]
    # A pre-2021 ATR covers 2000-2020; the fiscal-year offset moves that
    # by a year at most. 1974 and 2107 both appeared, and both are
    # misreads of a four-digit number that would have published a
    # town-year with no election in it.
    if not (1999 <= y <= 2021):
        return None, ("year %d is outside the 2000-2020 corpus; "
                      "read from %r" % (y, printed[:50]))
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
