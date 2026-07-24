"""Ground-truth recall — does a sweep re-find the election results we KNOW exist?

The inventory records 942 already-collected municipal election-result PDFs
(has_pdf=yes) across 293 towns. That is our ground truth: any honest sweep must
re-discover a municipal election document for those towns. This computes recall of
the discovered manifest (discover nodes + Wayback docs, classified doctype=election)
against that ground truth, per municipality. Low recall flags coverage gaps to
investigate; it is the validation contract for the whole pipeline.
"""

from __future__ import annotations

import csv
from collections import defaultdict

from ..archive.wayback import host_of
from ..config import data_dir, host_overrides, load_settings, resolve_path
from ..core import iter_jsonl, write_jsonl
from .model import classify_doc

_ELECTION = {"election"}


def _ground_truth(inventory) -> dict[str, set]:
    """municipality -> set(years) that have a collected election-result PDF."""
    gt: dict[str, set] = defaultdict(set)
    with inventory.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if (row.get("has_pdf") == "yes") and row.get("municipality"):
                gt[row["municipality"]].add((row.get("year") or "").strip())
    return gt


def _discovered_election_towns(overrides: dict) -> set[str]:
    """Municipalities for which our sweep found >=1 election-classified file."""
    found: set[str] = set()
    # discover nodes already carry municipality
    for n in iter_jsonl(data_dir() / "discover" / "nodes.jsonl"):
        if n.get("kind") == "file" and n.get("doctype") in _ELECTION and n.get("municipality"):
            found.add(n["municipality"])
    # wayback docs carry host only -> map to municipality
    inv = resolve_path(load_settings()["paths"]["inventory_csv"])
    host2muni: dict[str, str] = {}
    if inv.exists():
        with inv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                u = (row.get("native_url") or "").strip()
                if u:
                    h = host_of(u)
                    host2muni.setdefault(overrides.get(h, h), row.get("municipality", ""))
    for rec in iter_jsonl(data_dir() / "wayback" / "docs.jsonl"):
        if classify_doc(rec.get("url", "")) in _ELECTION:
            muni = host2muni.get(rec.get("host", ""))
            if muni:
                found.add(muni)
    return found


def build() -> dict:
    inv = resolve_path(load_settings()["paths"]["inventory_csv"])
    gt = _ground_truth(inv)
    found = _discovered_election_towns(host_overrides())

    gt_towns = set(gt)
    hit = gt_towns & found
    miss = sorted(gt_towns - found)
    recall = round(100 * len(hit) / (len(gt_towns) or 1), 1)

    summary = {
        "ground_truth_towns": len(gt_towns),
        "towns_swept_election_doc_found": len(hit),
        "recall_pct": recall,
        "missing_towns": len(miss),
    }
    print(f"\n  Ground-truth election recall: {len(hit)}/{len(gt_towns)} towns "
          f"= {recall}%")
    print(f"  (towns with a known election PDF that our sweep also found an "
          f"election doc for)")
    if miss:
        print(f"  missing (first 15): {miss[:15]}")

    out = data_dir() / "discover"
    write_jsonl(out / "groundtruth.jsonl",
                [{"municipality": m, "found": (m in found),
                  "gt_years": sorted(gt[m])} for m in sorted(gt_towns)])
    (out / "groundtruth.md").write_text(
        f"# Ground-truth election recall (generated)\n\n"
        f"Recall: **{len(hit)}/{len(gt_towns)} towns = {recall}%**\n\n"
        f"Ground truth = municipalities with a collected election-result PDF "
        f"(has_pdf=yes). A town counts as recalled if the sweep found >=1 "
        f"election-classified document for it.\n\n"
        f"Missing towns ({len(miss)}): {', '.join(miss) or 'none'}\n",
        encoding="utf-8")
    return summary
