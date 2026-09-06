"""Append rows to qa/reference/adjudications.csv from a JSON list on stdin.

A correction is a row. This writes the row, binds it to the document's sha256,
and refuses to write one with no `read` quote in it.
"""
import csv, hashlib, io, json, os, sys, datetime
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = os.path.join(BASE, "qa", "reference", "adjudications.csv")


def sha(stem):
    for n in (stem + ".pdf", stem + "_d0.pdf"):
        p = os.path.join(BASE, "data", "pdfs", n)
        if os.path.exists(p):
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for b in iter(lambda: fh.read(1 << 20), b""):
                    h.update(b)
            return h.hexdigest()
    return ""


def main():
    new = json.load(sys.stdin)
    rows = list(csv.DictReader(io.open(P, encoding="utf-8")))
    fields = list(rows[0].keys())
    today = datetime.date.today().isoformat()
    for r in new:
        assert r.get("read"), "a row without a quote is a guess with a signature on it"
        assert r.get("stem") and r.get("field") and r.get("should_be")
        rows.append({
            "stem": r["stem"], "source_sha256": sha(r["stem"]),
            "field": r["field"], "was": r.get("was", ""), "should_be": r["should_be"],
            "read": r["read"], "why": r.get("why", ""),
            "status": r.get("status", "proposed"),
            "decided_by": "civicatlas-qa (unattended run 2026-09-06)",
            "decided_on": today, "applied_on": "",
        })
    with io.open(P, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader()
        for r in rows: w.writerow({k: r.get(k, "") for k in fields})
    print(f"appended {len(new)} rows; ledger now {len(rows)}")


main()
