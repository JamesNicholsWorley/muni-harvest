"""Append rows to qa/reference/adjudications.csv from a JSON list on stdin.

A correction is a row, never code (CLAUDE.md).  This only writes rows; it holds
no per-town knowledge of its own.
"""
import csv, json, os, sys

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "qa/reference/adjudications.csv")
FIELDS = ["stem", "source_sha256", "field", "was", "should_be", "read", "why",
          "status", "decided_by", "decided_on"]

rows = json.load(sys.stdin)
with open(PATH, newline="", encoding="utf-8") as fh:
    have = {(r["stem"], r["field"], r["should_be"]) for r in csv.DictReader(fh)}

new = [r for r in rows if (r["stem"], r["field"], r["should_be"]) not in have]
with open(PATH, "a", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
    for r in new:
        r.setdefault("status", "proposed")
        r.setdefault("decided_by", "civicatlas-qa (unattended run)")
        r.setdefault("decided_on", "2026-09-06")
        w.writerow({k: r.get(k, "") for k in FIELDS})
print(f"wrote {len(new)} of {len(rows)} (skipped {len(rows)-len(new)} already present)")
