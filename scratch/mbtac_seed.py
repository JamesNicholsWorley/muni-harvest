"""Build scratch/mbtac_seed.csv -- one row per MBTA-C town, merging the EOHLC ground-truth
denominator (config/mbtac_groundtruth.csv) with whatever we already extracted from documents
(scratch/mbtac_votes.jsonl). This seed is what the per-town research workflow fills out (adding
the Planning Board recommendation + the legislative-body vote details from news/official sources).

ASCII-only, explicit UTF-8 I/O.
"""
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUND = HERE.parent / "config" / "mbtac_groundtruth.csv"
VOTES = HERE / "mbtac_votes.jsonl"
OUT = HERE / "mbtac_seed.csv"

LEG = {"town_meeting", "representative_town_meeting", "city_council"}


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def load_extracted():
    """town_norm -> {leg: best legislative event, pb: planning-board rec} from our doc extraction."""
    by = {}
    if not VOTES.exists():
        return by
    for line in VOTES.open(encoding="utf-8"):
        e = json.loads(line)
        tn = norm(e["municipality"])
        d = by.setdefault(tn, {"leg": None, "pb": None})
        body = e.get("meeting_body", "")
        if body in LEG:
            # prefer a terminal/decisive legislative event
            cur = d["leg"]
            better = cur is None or (e.get("is_terminal") and not cur.get("is_terminal"))
            if better:
                d["leg"] = e
        elif body == "planning_board" and d["pb"] is None:
            d["pb"] = e
    return by


def fmt(e):
    if not e:
        return ""
    tally = ""
    if isinstance(e.get("vote_yes"), int) and e["vote_yes"] >= 0:
        tally = f"{e['vote_yes']}-{e['vote_no']}"
        if isinstance(e.get("vote_abstain"), int) and e["vote_abstain"] > 0:
            tally += f"-{e['vote_abstain']}a"
    parts = [e.get("outcome", ""), e.get("meeting_date", ""), tally,
             ("art " + e["article_number"]) if e.get("article_number") else ""]
    return "; ".join(p for p in parts if p)


def main():
    ext = load_extracted()
    rows = []
    for g in csv.DictReader(GROUND.open(encoding="utf-8")):
        tn = g["town_norm"]
        e = ext.get(tn, {})
        leg, pb = e.get("leg"), e.get("pb")
        rows.append({
            "town": g["town"], "town_norm": tn,
            "community_type": g["community_type"], "governing_body": g["governing_body"],
            "eohlc_status": g["status"], "adoption_date": g["adoption_date"],
            "extracted_legislative": fmt(leg),
            "extracted_planning_board": fmt(pb),
            "extracted_source_url": (leg or pb or {}).get("doc_url", "") if (leg or pb) else "",
        })
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    have_leg = sum(1 for r in rows if r["extracted_legislative"])
    have_pb = sum(1 for r in rows if r["extracted_planning_board"])
    print(f"wrote {OUT.name}: {len(rows)} towns")
    print(f"  seeded from our doc extraction: {have_leg} legislative, {have_pb} planning-board")


if __name__ == "__main__":
    main()
