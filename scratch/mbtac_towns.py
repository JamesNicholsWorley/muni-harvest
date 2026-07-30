"""Stage 0 (reference table) for the MBTA Communities Act 3A vote finder.

Reads the 175 designated MBTA-Communities towns from the state xlsx, joins the
governing body (Select Board vs City Council) from the election_results SQL dump's
`municipalstructure` table, and stamps each town's compliance-deadline tier.

Output: config/mbtac_towns.csv  (town, town_norm, community_type, governing_body,
deadline_year). Governing body only sets expectations/priority for later stages;
Town Meeting form (Open vs Representative) is not in the SQL and is read from the
document content at extraction time.

ASCII-only, explicit UTF-8 I/O (Windows).
"""
import csv
import re
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
XLSX = Path(r"C:\Users\Owner\Downloads"
            r"\MBTA Communities - Cohort Designations and Capacity Calculations (2) (1).xlsx")
SQL = Path(r"C:\Users\Owner\Downloads\election_results (3).sql")
OUT = ROOT / "config" / "mbtac_towns.csv"

# Compliance-deadline tier by community type (EOHLC 760 CMR 59 timeline).
DEADLINE = {
    "subway or light rail": 2023,   # rapid transit
    "commuter rail": 2024,
    "MBTA adjacent": 2024,
    "bus": 2025,                    # adjacent small town / bus
}


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def load_towns():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # header
        muni, ctype = row[0], row[1]
        if not muni:
            continue
        rows.append((str(muni).strip(), str(ctype).strip()))
    return rows


def load_governing_bodies():
    """Parse towns (Town_ID -> name) and municipalstructure (Town_ID -> body)
    from the SQL dump. Returns {town_norm: governing_body}."""
    text = SQL.read_text(encoding="utf-8", errors="replace")

    def grab_values(table):
        # Concatenate every INSERT ... VALUES block for the table (may be multi-row).
        blocks = re.findall(
            r"INSERT INTO `" + table + r"`[^;]*?VALUES\s*(.*?);",
            text, re.I | re.S)
        return " ".join(blocks)

    id2name = {}
    for m in re.finditer(r"\((\d+),\s*'((?:[^'\\]|\\.)*)'\)", grab_values("towns")):
        id2name[int(m.group(1))] = m.group(2).replace("\\'", "'")

    id2body = {}
    for m in re.finditer(r"\((\d+),\s*'(Select Board|City Council)'",
                         grab_values("municipalstructure")):
        id2body[int(m.group(1))] = m.group(2)

    body_by_town = {}
    for tid, name in id2name.items():
        if tid in id2body:
            body_by_town[norm(name)] = id2body[tid]
    return body_by_town


def main():
    towns = load_towns()
    bodies = load_governing_bodies()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_body = 0
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["town", "town_norm", "community_type", "governing_body", "deadline_year"])
        for muni, ctype in towns:
            body = bodies.get(norm(muni), "")
            if body:
                n_body += 1
            w.writerow([muni, norm(muni), ctype, body, DEADLINE.get(ctype, "")])
    print(f"wrote {OUT} : {len(towns)} towns, {n_body} with governing body")
    # quick sanity
    from collections import Counter
    print("  types:", dict(Counter(c for _, c in towns)))


if __name__ == "__main__":
    main()
