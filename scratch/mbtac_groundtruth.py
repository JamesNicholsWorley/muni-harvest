"""Build config/mbtac_groundtruth.csv -- the EOHLC compliance DENOMINATOR for the 175 MBTA-C
towns, from authoritative + news sources:

  * MassGIS "MBTA Communities 3A District Atlas" FeatureServer layer 0 (STATUS=Compliant + the
    district adoption/approval DATE_) -- the official EOHLC-certified compliant set.
  * Boston.com (Jan 2026) named lists for conditional + non-compliant communities.

Status precedence: Compliant (MassGIS) > Conditional > Non-Compliant > Interim/Unknown.
ASCII-only, explicit UTF-8 I/O.
"""
import csv
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
TOWNS = HERE.parent / "config" / "mbtac_towns.csv"
OUT = HERE.parent / "config" / "mbtac_groundtruth.csv"
FS = ("https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services/"
      "MBTA_Communities_3A_District_Atlas/FeatureServer/0/query")

# Boston.com "MBTA Communities Act: What's next for your town" (2026-01-27).
CONDITIONAL = {"Bridgewater", "Concord", "Everett", "Hopkinton", "Lancaster", "Plymouth", "Salisbury"}
NONCOMPLIANT = {"Carver", "Dracut", "East Bridgewater", "Freetown", "Halifax", "Holden",
                "Marblehead", "Middleton", "Rehoboth", "Tewksbury", "Wilmington", "Winthrop"}


ALIAS = {"manchesterbythesea": "manchester", "northattleboro": "northattleborough"}


def norm(s):
    n = re.sub(r"[^a-z]", "", (s or "").lower())
    return ALIAS.get(n, n)


def massgis_compliant():
    q = requests.get(FS, params={"where": "1=1", "outFields": "MUNI,DATE_,STATUS",
                                 "returnGeometry": "false", "f": "json",
                                 "resultRecordCount": 4000}, timeout=60).json()
    best = {}   # norm -> (iso_date, muni)
    for f in q.get("features", []):
        a = f.get("attributes", {})
        muni = a.get("MUNI")
        if not muni or (a.get("STATUS") or "").strip() != "Compliant":
            continue
        iso = ""
        d = a.get("DATE_")
        if isinstance(d, (int, float)):
            iso = datetime.fromtimestamp(d / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        n = norm(muni)
        # keep the EARLIEST adoption date per muni
        if n not in best or (iso and (not best[n][0] or iso < best[n][0])):
            best[n] = (iso, muni)
    return best


def main():
    towns = list(csv.DictReader(TOWNS.open(encoding="utf-8")))
    comp = massgis_compliant()
    cond = {norm(t) for t in CONDITIONAL}
    noncomp = {norm(t) for t in NONCOMPLIANT}

    rows = []
    from collections import Counter
    tally = Counter()
    for t in towns:
        tn = t["town_norm"]
        if tn in comp:
            status, date = "Compliant", comp[tn][0]
        elif tn in cond:
            status, date = "Conditional", ""
        elif tn in noncomp:
            status, date = "Non-Compliant", ""
        else:
            status, date = "Interim/Unknown", ""
        tally[status] += 1
        rows.append({"town": t["town"], "town_norm": tn,
                     "community_type": t["community_type"],
                     "governing_body": t["governing_body"],
                     "status": status, "adoption_date": date})

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"wrote {OUT} for {len(rows)} towns")
    print("  status mix:", dict(tally))
    # MassGIS compliant munis not in our 175 (statewide has 177) -- log, don't drop
    extra = sorted(comp[n][1] for n in comp if n not in {r["town_norm"] for r in rows})
    print(f"  MassGIS-compliant munis NOT in our 175 list ({len(extra)}): {', '.join(extra)}")


if __name__ == "__main__":
    main()
