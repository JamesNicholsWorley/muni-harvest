"""Finalize the MBTA-C by-body results panel. Merges the research-workflow output with the
seed (EOHLC ground truth + our document extractions) into scratch/mbtac_results_full.csv --
one row per town, aligned with the relevant body (Planning Board + Open/Rep Town Meeting or
City Council). Dedupes towns, reconciles against all 175, flags any missing.

Usage: mbtac_finalize.py <workflow_output.json>
ASCII-only, explicit UTF-8 I/O.
"""
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = HERE / "mbtac_seed.csv"
OUT = HERE / "mbtac_results_full.csv"


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def completeness(t):
    keys = ["legislative_outcome", "legislative_date", "legislative_tally", "legislative_article",
            "planning_board_recommendation", "planning_board_date", "adoption_date"]
    score = sum(1 for k in keys if (t.get(k) or "").strip() and t.get(k) not in ("unknown",))
    conf = {"high": 2, "medium": 1, "low": 0}.get(t.get("confidence", ""), 0)
    return score * 3 + conf


def load_research(path):
    raw = Path(path).read_text(encoding="utf-8")
    top = json.loads(raw)
    res = top.get("result", top)
    if isinstance(res, str):
        res = json.loads(res)
    towns = res.get("towns", [])
    best = {}
    for t in towns:
        tn = norm(t.get("town", ""))
        if not tn:
            continue
        if tn not in best or completeness(t) > completeness(best[tn]):
            best[tn] = t
    return best


def main():
    if len(sys.argv) < 2:
        print("usage: mbtac_finalize.py <workflow_output.json>")
        sys.exit(1)
    research = load_research(sys.argv[1])
    seed = list(csv.DictReader(SEED.open(encoding="utf-8")))

    cols = ["town", "community_type", "governing_body", "legislative_form",
            "planning_board_recommendation", "planning_board_date", "planning_board_vote",
            "legislative_outcome", "legislative_date", "legislative_tally", "legislative_article",
            "threshold", "eohlc_status", "adoption_date", "confidence", "doc_source_url",
            "sources", "notes"]
    rows, missing = [], []
    for s in seed:
        tn = s["town_norm"]
        r = research.get(tn)
        if not r:
            missing.append(s["town"])
            rows.append({"town": s["town"], "community_type": s["community_type"],
                         "governing_body": s["governing_body"], "eohlc_status": s["eohlc_status"],
                         "adoption_date": s["adoption_date"], "legislative_outcome": "NOT_RESEARCHED",
                         "doc_source_url": s["extracted_source_url"]})
            continue
        rows.append({
            "town": s["town"], "community_type": s["community_type"],
            "governing_body": s["governing_body"],
            "legislative_form": r.get("legislative_form", ""),
            "planning_board_recommendation": r.get("planning_board_recommendation", ""),
            "planning_board_date": r.get("planning_board_date", ""),
            "planning_board_vote": r.get("planning_board_vote", ""),
            "legislative_outcome": r.get("legislative_outcome", ""),
            "legislative_date": r.get("legislative_date", ""),
            "legislative_tally": r.get("legislative_tally", ""),
            "legislative_article": r.get("legislative_article", ""),
            "threshold": r.get("threshold", ""),
            "eohlc_status": r.get("eohlc_status") or s["eohlc_status"],
            "adoption_date": r.get("adoption_date") or s["adoption_date"],
            "confidence": r.get("confidence", ""),
            "doc_source_url": s["extracted_source_url"],
            "sources": " | ".join(r.get("sources", []) or []),
            "notes": r.get("notes", ""),
        })

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

    from collections import Counter
    researched = len(rows) - len(missing)
    print(f"wrote {OUT.name}: {len(rows)} towns; researched {researched}, missing {len(missing)}")
    print("  legislative_form:", dict(Counter(r.get("legislative_form", "") for r in rows)))
    print("  legislative_outcome:", dict(Counter(r.get("legislative_outcome", "") for r in rows)))
    print("  PB recommendation:", dict(Counter(r.get("planning_board_recommendation", "") for r in rows)))
    print("  with legislative tally:", sum(1 for r in rows if (r.get("legislative_tally") or "").strip()))
    print("  confidence:", dict(Counter(r.get("confidence", "") for r in rows)))
    if missing:
        print(f"  MISSING (re-run): {', '.join(missing)}")
        (HERE / "mbtac_research_missing.txt").write_text(
            "\n".join(norm(m) for m in missing), encoding="utf-8")


if __name__ == "__main__":
    main()
