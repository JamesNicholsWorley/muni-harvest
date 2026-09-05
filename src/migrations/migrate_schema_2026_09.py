"""Retire the -1/-3 sentinels and add the fields QA needs to stop guessing.

Four changes, one pass:

  1. `votes: -1`  ->  `votes: null, status: "uncontested"`
     `votes: -3`  ->  `votes: null, status: "write_in_winner"`

     A sentinel is a magic number sitting in a field that otherwise holds real
     counts.  Nothing stops a sum from including it, and a contest that quietly
     totals negative passes every check that does not think to look.  `null`
     cannot be summed by accident.

  2. `tally_row: true` on Blanks / Others / Write-ins.

     These are lines that count marks, not people.  Today that is inferred by
     matching names, which is why an office name occasionally ends up treated
     as a candidate.

  3. `scope` on every contest: at_large | sub_town | regional_district.

     The word "district" does double duty.  A precinct divides one town and its
     numbers sum to the town total; a regional district spans several towns and
     its numbers routinely exceed the host town's ballots, legitimately.  Until
     this is a field every checker has to guess from the office name.

  4. `blanks_printed` on every contest, and `ballots_cast` +
     `ballots_cast_source` on the record.

     Derived, never asked for.  Every municipality-wide single-seat contest that
     prints its blanks sits on the same ballot and implies the same figure.  Two
     that disagree are a disagreement, not a derivation -- those records get
     `ballots_cast: null` and a source of "cannot_derive" rather than a guess.

`name_original` and `office_original` are not touched.  They are the
transcription; grounding checks match against them, and editing them would
destroy the ability to check anything.

    python -m src.migrate_schema_2026_09 --dry-run
    python -m src.migrate_schema_2026_09 --apply
"""

import argparse
import collections
import glob
import json
import os
import re
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_DIR = os.path.join(BASE, "data", "json")

TALLY_ROWS = {"blanks", "blank", "others", "other", "write-ins", "write-in",
              "write ins", "writein", "scattering", "scattered", "all others"}

RE_REGIONAL = re.compile(
    r"REGION|VOCATION|TECHNICAL|AGRICULTUR|COOPERATIVE|\bRSD\b|"
    r"GREATER\s|SCHOOL\s+DISTRICT|DISTRICT\s+SCHOOL", re.I)
RE_SUBTOWN = re.compile(
    r"\bDIST\b|\bDISTRICT\s+[0-9A-Z]\b|\bWARD\b|\bPCT\b|\bPRECINCT\b|\bTMM\b", re.I)

SENTINELS = {-1: "uncontested", -3: "write_in_winner"}


def name_of(c):
    return str(c.get("name_original") or c.get("name") or "").strip()


def is_tally(c):
    return name_of(c).lower() in TALLY_ROWS


def scope_of(contest):
    office = str(contest.get("office_original") or contest.get("office") or "")
    if RE_REGIONAL.search(office):
        return "regional_district"
    if (contest.get("district_original") or "").strip() or RE_SUBTOWN.search(office):
        return "sub_town"
    return "at_large"


def blanks_printed(contest):
    return any(name_of(c).lower() in ("blanks", "blank")
               for c in contest.get("candidates") or [])


def marks_in(contest):
    t = 0
    for c in contest.get("candidates") or []:
        v = c.get("votes")
        if isinstance(v, int) and v > 0:
            t += v
    return t


def has_ballot_candidate(contest):
    for c in contest.get("candidates") or []:
        if is_tally(c):
            continue
        v = c.get("votes")
        if isinstance(v, int) and v > 0:
            return True
    return False


def derive_ballots(record):
    """(ballots, source).  Consensus needs a quorum; otherwise say so."""
    est = []
    for e in record.get("elections") or []:
        if e.get("scope") != "at_large":
            continue
        if (e.get("num_winners") or 1) != 1:
            continue
        if not e.get("blanks_printed") or not has_ballot_candidate(e):
            continue
        m = marks_in(e)
        if m:
            est.append(m)
    if len(est) < 2:
        return None, "cannot_derive"
    counts = collections.Counter(est)
    top, n = counts.most_common(1)[0]
    if n < 2:
        return None, "cannot_derive"
    return top, "derived_from_contests"


def migrate(record):
    """Returns (record, stats).  Idempotent: re-running changes nothing."""
    st = collections.Counter()

    for e in record.get("elections") or []:
        for c in e.get("candidates") or []:
            v = c.get("votes")
            if v in SENTINELS:
                c["votes"] = None
                c["status"] = SENTINELS[v]
                st[f"sentinel_{v}"] += 1
            if is_tally(c) and not c.get("tally_row"):
                c["tally_row"] = True
                st["tally_row"] += 1

        sc = scope_of(e)
        if e.get("scope") != sc:
            e["scope"] = sc
            st[f"scope_{sc}"] += 1

        bp = blanks_printed(e)
        if e.get("blanks_printed") != bp:
            e["blanks_printed"] = bp
            st["blanks_printed"] += 1

    ballots, source = derive_ballots(record)
    # A ballot count already stated in the record (read off the document) is
    # kept and compared, not overwritten -- a disagreement is a real finding.
    #
    # But only a figure this migration did not itself write counts as stated.
    # On a second pass the derived value is sitting in the same field, and
    # without this guard it would be relabelled "stated_in_record" -- a derived
    # number quietly promoted to a documented one, which is the whole class of
    # error this schema exists to prevent.
    prior = record.get("ballots_cast_source")
    stated = record.get("ballots_cast") if prior in (None, "stated_in_record") else None
    if isinstance(stated, int) and stated > 0:
        record["ballots_cast_source"] = "stated_in_record"
        if ballots is not None and ballots != stated:
            record["ballots_cast_derived"] = ballots
            st["stated_disagrees_with_derived"] += 1
    else:
        record["ballots_cast"] = ballots
        record["ballots_cast_source"] = source
        st[f"ballots_{source}"] += 1

    return record, st


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(JSON_DIR, "*.json")))
    total = collections.Counter()
    changed = 0
    failed = []

    if args.apply:
        bk = os.path.join(BASE, "_schema_backup_20260905")
        if os.path.exists(bk):
            shutil.rmtree(bk)
        shutil.copytree(JSON_DIR, bk)
        print(f"backup: {os.path.relpath(bk, BASE)}  ({len(paths)} files)\n")

    for p in paths:
        try:
            with open(p, encoding="utf-8") as fh:
                rec = json.load(fh)
        except Exception as exc:
            failed.append((os.path.basename(p), str(exc)))
            continue
        before = json.dumps(rec, sort_keys=True)
        rec, st = migrate(rec)
        total.update(st)
        if json.dumps(rec, sort_keys=True) != before:
            changed += 1
            if args.apply:
                with open(p, "w", encoding="utf-8") as fh:
                    json.dump(rec, fh, indent=2, ensure_ascii=False)
                    fh.write("\n")

    print(f"{'APPLIED' if args.apply else 'DRY RUN'}")
    print(f"records read    : {len(paths)}")
    print(f"records changed : {changed}")
    if failed:
        print(f"records FAILED  : {len(failed)}")
        for n, e in failed[:5]:
            print(f"   {n}: {e[:70]}")
    print()
    for k, v in sorted(total.items()):
        print(f"   {v:>7}  {k}")


if __name__ == "__main__":
    main()
