"""File one adjudication row per town-year whose source prints a ballot count.

Read `scratch/inspect_stem.py` first if a row here looks surprising: every stem
below was opened, the sentence carrying the count was read, and the count was
checked against every contest in the record before it was written down. The
list is typed out rather than matched because two of the sentences a pattern
finds are about a DIFFERENT election -- Weymouth 2023's source says "received
18% of the 9,500 votes cast four years ago" and Williamstown 2021's says "Last
year ... about 700 ballots were cast" before giving this year's 1,823 -- and no
arithmetic test can tell those from the real thing.

Run once. It refuses to write a row for a stem it already wrote one for.
"""
import csv
import hashlib
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers  # noqa: E402

LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")
TODAY = "2026-09-07"
WHO = "civicatlas-qa (unattended run 2026-09-07)"

# stem -> the ballot count its source prints, read off the page.
STATED = {
    "Mashpee2025": 2052, "Tisbury2023": 678, "Chesterfield2021": 54,
    "Williamstown2024": 438, "Warren2023": 265, "Ipswich2024": 4507,
    "Millis2026": 1418, "NewAshford2023": 57, "Monson2022": 991,
    "Hatfield2022": 652, "Sheffield2021": 279, "Cheshire2023": 255,
    "Royalston2026": 121, "Petersham2026": 116, "Worthington2022": 266,
    "Hancock2026": 334, "Heath2021": 240, "Washington2021": 66,
    "Huntington2024": 98, "Clarksburg2021": 106, "WestSpringfield2023": 3388,
    "WestSpringfield2021": 3573, "Carver2025": 252, "Nantucket2023": 2138,
    "Carver2021": 1037, "Hampden2022": 480, "OakBluffs2021": 714,
    "Lenox2022": 140, "Lenox2026": 926, "Cheshire2024": 1465,
    "Lanesborough2022": 664, "Williamsburg2026": 160, "Bernardston2021": 205,
    "Bernardston2023": 60, "Huntington2023": 71, "Shelburne2024": 164,
    "Conway2024": 545, "Conway2023": 271, "Shelburne2021": 144,
    "Shelburne2022": 144, "Ashfield2021": 253, "Richmond2026": 225,
    "Whately2025": 114, "Richmond2023": 51, "Egremont2021": 245,
    "Charlemont2026": 131, "Chester2023": 82, "Wendell2024": 133,
    "Wendell2021": 96, "Wendell2022": 91, "Montgomery2022": 148,
    "Williamstown2021": 1823, "Sudbury2026": 3045,
}

QUOTE = re.compile(
    r"[^.]{0,120}(?:ballots?|votes?|voters?|turnout)[^.]{0,120}\.", re.I)


def quote_for(text, n):
    """The sentence the count is printed in, bounded to a citation."""
    for m in re.finditer(r"(?<![\d,])" + f"{n:,}".replace(",", "[,]?") + r"(?!\d)", text):
        s = text[max(0, m.start() - 130):m.end() + 130]
        w = QUOTE.search(s)
        return layers.snippet((w.group(0) if w else s).strip())
    return None


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def source_file(stem):
    for rel in (f"data/news_text/{stem}.md", f"data/markdown/{stem}.md",
                f"data/raw_ocr/{stem}.txt", f"data/pdftext/{stem}.txt"):
        p = os.path.join(BASE, rel)
        if os.path.exists(p):
            return rel, p
    return None, None


def main(write=False):
    with io.open(LEDGER, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
    already = {r["stem"] for r in rows
               if "ballots_cast" in (r.get("field") or "") and r["decided_on"] == TODAY}

    new = []
    for stem, n in sorted(STATED.items()):
        if stem in already:
            print(f"  skip     {stem}: a row for today already exists")
            continue
        rec = json.load(open(os.path.join(BASE, "data", "json", stem + ".json"),
                             encoding="utf-8"))
        if rec.get("ballots_cast") is not None:
            print(f"  skip     {stem}: the record already holds "
                  f"{rec['ballots_cast']}")
            continue
        text, src = layers.document_text(stem)
        # every contest must fit under the count, or the count is not the count
        over = [(e.get("office_original"), layers.marks_in(e))
                for e in rec.get("elections") or []
                if layers.scope_of(e) != "regional_district"
                and layers.marks_in(e) > n * (e.get("num_winners") or 1)]
        if over:
            print(f"  REFUSED  {stem}: {over} exceeds {n} x seats")
            continue
        q = quote_for(text, n)
        if not q:
            print(f"  REFUSED  {stem}: {n} is not in {src}")
            continue
        rel, path = source_file(stem)
        new.append({
            "stem": stem,
            "source_sha256": sha256_of(path),
            "field": "ballots_cast and ballots_cast_source",
            "was": "null (ballots_cast_source: cannot_derive)",
            "should_be": f"{n} / stated_in_source",
            "read": f"{rel}: \"{q}\"",
            "why": (
                f"The source states the ballot count and the record holds null. "
                f"Checked against every contest before filing: no at-large or "
                f"sub-town contest in this record exceeds {n} x its seats. "
                f"ballots_derivable is UNKNOWN here and correctly so -- the "
                f"source is a report rather than a return, it prints no blanks "
                f"row for any contest, and derive_ballots needs two contests "
                f"that print blanks. NOT APPLIABLE BY qa.apply AS IT STANDS: "
                f"this is a PAIR of fields, and applying ballots_cast alone "
                f"would leave ballots_cast_source reading cannot_derive. No "
                f"record in the corpus holds a figure with that source today "
                f"(1273 derived_from_contests, 64 stated_in_record, 553 null), "
                f"and this must not be the first."),
            "status": "needs-owner",
            "decided_by": WHO,
            "decided_on": TODAY,
            "applied_on": "",
        })
        print(f"  row      {stem}: {n}")

    print(f"\n{len(new)} rows")
    if write and new:
        with io.open(LEDGER, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for r in rows + new:
                w.writerow({k: r.get(k, "") for k in fields})
        print("written")


if __name__ == "__main__":
    main("--write" in sys.argv)
