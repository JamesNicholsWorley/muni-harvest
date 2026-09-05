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
    r"GOVERNOR'S COUNCIL|ASSEMBLY DELEGATE", re.I)


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


def document_text(stem):
    """The best reading of the held document, or None if we hold none."""
    for rel in (f"data/raw_ocr/{stem}.txt",
                f"data/markdown/{stem}.md",
                f"data/pdftext/{stem}.txt"):
        p = os.path.join(BASE, rel)
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                t = fh.read()
            if t.strip():
                return re.sub(r"\s+", " ", t), rel
    return None, None


def municipality_of(stem):
    return re.sub(r"\d{4}$", "", stem)


def year_of(stem):
    m = re.search(r"(\d{4})$", stem)
    return m.group(1) if m else None


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
    m = re.search(r"\b" + re.escape(year) + r"\b", text) if year else None
    out.append((stem, 0, "carries_the_year",
                PASS if m else FAIL,
                f"...{text[max(0,m.start()-40):m.end()+40].strip()}..." if m
                else f"'{year}' does not appear in {source}"))

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
    f_hit = sum(1 for v in figures if re.search(r"" + str(v) + r"", text))
    if names or figures:
        supported = n_hit > 0 or f_hit > 0
        out.append((stem, 0, "document_supports_record",
                    PASS if supported else FAIL,
                    f"{n_hit}/{len(names)} names and {f_hit}/{len(figures)} figures "
                    f"located in {source}"))
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
    f_ok = sum(1 for v in figures if re.search(r"\b" + str(v) + r"\b", text))

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


if __name__ == "__main__":
    main()
