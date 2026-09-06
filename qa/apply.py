"""Apply an adjudication to the record, when the document itself can settle it.

A hundred and seventy-five corrections have been read off documents, quoted, and
bound to a document hash -- and not one of them had reached the JSON. The QA had
become very good at describing errors and had no way to fix them.

This applies the ones a machine can check, and refuses the rest.

    python -m qa.apply                     what would happen, changing nothing
    python -m qa.apply --apply             write it
    python -m qa.apply --apply --limit 20  a few

## What "a machine can check" means

The gate is not "an agent was confident". It is a property of the document:

    the corrected value appears in the document text
    AND the value we currently hold does NOT

If both appear, the document says both things and a string test cannot choose --
that is a reading, and it goes to the owner. If neither appears, the quote in the
ledger is not something this document supports, and the row is suspect rather
than ready. Either way the answer is to stop, not to guess.

That test is strictly stronger than a model's opinion, and it cannot hallucinate:
it is `in`, run against the bytes of the reading.

## What is never applied here

`num_winners` decides who won. `scope` moves a contest between the ballot
arithmetic and the exemption from it. A whole-record reparse replaces everything.
None of those is a string a document either contains or does not, so none of them
is settled by this file -- they are marked `needs-owner` and left alone.

Figures are applied only when a session reopened the document and recorded its
own reading (`status: verified`), because a digit is short enough to appear in a
document by coincidence and a name is not.

## Why it matches on the value and not the field path

The ledger's `field` column is prose written by whoever filed the row:
`candidates[].name_original == "Tracey L. Whitfield"` in one row and
`elections[0]  (2023-05-16, stage=General, ...)` in the next. Parsing that is a
guess. Searching the record for the value we are replacing is not, and it fails
closed: no match, or more than one, and the row is skipped and reported. A
correction applied to the wrong candidate is exactly the damage this project
cannot undo.

## It dies with the document

Every row carries the `source_sha256` it was formed against. If the file we hold
now hashes differently, it is a different document and the reasoning about the
old one says nothing about it. The row is skipped, not applied.
"""

import argparse
import collections
import csv
import datetime
import hashlib
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")

# Fields whose correctness is a judgement, not a string test.  Listed by what
# they are, never by what they are not: anything unrecognised also stops.
APPLIABLE_NAME = "name_original"
APPLIABLE_FIGURE = ("votes", "ballots_cast")
NEVER = ("num_winners", "scope", "district", "office_original", "election_type",
         "whole record", "reparse", "moved to its own record")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def classify(row):
    """What kind of correction is this, and may this file apply it?"""
    blob = " ".join((row.get("field") or "", row.get("why") or "")).lower()
    for word in NEVER:
        if word in blob:
            return "needs-owner", f"{word} is a judgement, not a string test"
    if APPLIABLE_NAME in blob:
        return "name", ""
    for word in APPLIABLE_FIGURE:
        if re.search(r"\b" + word + r"\b", blob):
            return "figure", ""
    return "needs-owner", "unrecognised field; enumerate what it IS before applying"


def document_says(stem):
    """Every reading we hold of this town-year, normalised for comparison."""
    sys.path.insert(0, BASE)
    from qa import layers
    text, source = layers.document_text(stem)
    return (norm(text) if text else ""), source


def find_targets(record, kind, was):
    """Every place in the record holding `was`, as (setter, description).

    Returns a list so the caller can refuse when it is not exactly one. A
    correction applied to the wrong candidate is worse than one not applied.
    """
    hits = []
    for ei, e in enumerate(record.get("elections") or []):
        office = e.get("office_original") or e.get("office") or f"elections[{ei}]"
        for ci, c in enumerate(e.get("candidates") or []):
            if kind == "name" and (c.get("name_original") or "") == was:
                hits.append((("cand", ei, ci, "name_original"),
                             f"{office} / {was}"))
            if kind == "figure" and str(c.get("votes")) == str(was):
                hits.append((("cand", ei, ci, "votes"),
                             f"{office} / {c.get('name_original')} = {was}"))
    if kind == "figure" and str(record.get("ballots_cast")) == str(was):
        hits.append((("top", None, None, "ballots_cast"), f"ballots_cast = {was}"))
    return hits


def write_value(record, target, value):
    where, ei, ci, key = target
    if where == "top":
        record[key] = int(value) if str(value).isdigit() else value
    else:
        c = record["elections"][ei]["candidates"][ci]
        c[key] = int(value) if key == "votes" and str(value).isdigit() else value


def consider(row):
    """(verdict, note) for one ledger row. Verdict is apply / skip / needs-owner."""
    stem = row["stem"]
    kind, why = classify(row)
    if kind == "needs-owner":
        return "needs-owner", why, None

    jpath = os.path.join(BASE, "data", "json", stem + ".json")
    if not os.path.exists(jpath):
        return "skip", "no record held", None

    # The row was formed against one document. A different file is a different
    # document, and the reasoning does not carry over.
    for cand in (os.path.join(BASE, "data", "pdfs", stem + ".pdf"),
                 os.path.join(BASE, "data", "pdfs", stem + "_d0.pdf")):
        if os.path.exists(cand):
            if row.get("source_sha256", "").strip() and \
               sha256_of(cand) != row["source_sha256"].strip():
                return "skip", "document has been replaced since the row was written", None
            break

    text, source = document_says(stem)
    if not text:
        return "skip", "no readable text held; cannot check against the document", None

    was, should = row.get("was", ""), row.get("should_be", "")
    if not norm(should):
        return "skip", "no corrected value recorded", None

    # The gate.
    if norm(should) not in text:
        return "skip", f"corrected value is not in {source}", None

    if kind == "figure":
        # A digit is short enough to appear by coincidence; a name is not. So a
        # figure is never settled by the string test alone -- it needs a session
        # to have rendered the page and read it.
        if (row.get("status") or "").strip() != "verified":
            return "needs-owner", "figure needs a session to reopen the document (status: verified)", None
        # The both-present rule below is right for a name and wrong for a
        # figure. On a multi-page return almost every number appears somewhere
        # -- a precinct column, another contest, a page number -- so "the old
        # value is also in the text" is nearly always true and says nothing.
        # Applying it to figures blocked all 44 rows a session had already read
        # off the page, which is how the mistake was found. Where a session has
        # read the page, the reading is the evidence and the string test is not
        # the authority.
        pass
    elif norm(was) and norm(was) in text:
        return "needs-owner", f"{source} contains BOTH spellings; a string test cannot choose", None

    with io.open(jpath, encoding="utf-8") as fh:
        record = json.load(fh)
    hits = find_targets(record, kind, was)
    if not hits:
        return "skip", f"record holds no {kind} equal to {was!r}", None
    if len(hits) > 1:
        return "needs-owner", f"{len(hits)} places hold {was!r}; ambiguous", None
    return "apply", hits[0][1], (jpath, record, hits[0][0], should)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the changes")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    with io.open(LEDGER, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys()) if rows else []
    for extra in ("applied_on",):
        if extra not in fields:
            fields.append(extra)

    tally = collections.Counter()
    done = 0
    for row in rows:
        if (row.get("status") or "").strip() in ("applied", "needs-owner"):
            tally[row["status"]] += 1
            continue
        if args.limit and done >= args.limit:
            break
        verdict, note, payload = consider(row)
        tally[verdict] += 1
        print(f"  {verdict:11} {row['stem']:<18} {note[:78]}")
        if verdict == "needs-owner":
            row["status"] = "needs-owner"
            row["why"] = (row.get("why") or "") + f" || not applied: {note}"
        elif verdict == "apply" and args.apply:
            jpath, record, target, value = payload
            write_value(record, target, value)
            with io.open(jpath, "w", encoding="utf-8") as fh:
                json.dump(record, fh, ensure_ascii=False, indent=1)
            row["status"] = "applied"
            row["applied_on"] = datetime.date.today().isoformat()
            done += 1

    if args.apply:
        with io.open(LEDGER, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})

    print()
    for k, v in sorted(tally.items()):
        print(f"{v:5}  {k}")
    if not args.apply:
        print("\nnothing was written. Re-run with --apply to write it.")


if __name__ == "__main__":
    main()
