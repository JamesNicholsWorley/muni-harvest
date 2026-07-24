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
import re
from collections import defaultdict

from ..archive.wayback import host_of
from ..config import data_dir, host_overrides, load_settings, resolve_path
from ..core import iter_jsonl, write_jsonl
from .model import classify_doc

_ELECTION = {"election"}
_YEAR = re.compile(r"(20[0-2]\d)")


def _years(text: str) -> set[str]:
    return set(_YEAR.findall(text or ""))


def _ground_truth(inventory) -> dict[str, set]:
    """municipality -> set(years) that have a collected election-result PDF."""
    gt: dict[str, set] = defaultdict(set)
    with inventory.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            yr = (row.get("year") or "").strip()
            if row.get("has_pdf") == "yes" and row.get("municipality") and yr:
                gt[row["municipality"]].add(yr)
    return gt


def _discovered(overrides: dict) -> dict[str, set]:
    """municipality -> set(years) of election-classified files the sweep found.

    A full-site crawl surfaces the actual document URL; we read the year out of the
    URL/anchor so a known (town, year) result can be matched to the URL we found.
    """
    found: dict[str, set] = defaultdict(set)
    for n in iter_jsonl(data_dir() / "discover" / "nodes.jsonl"):
        if n.get("kind") == "file" and n.get("doctype") in _ELECTION and n.get("municipality"):
            found[n["municipality"]] |= _years(n["url"] + " " + n.get("anchor", ""))
    # Wayback docs carry host only -> map host to municipality
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
        url = rec.get("url", "")
        if classify_doc(url) in _ELECTION:
            muni = host2muni.get(rec.get("host", ""))
            if muni:
                found[muni] |= _years(url)
    return found


def build() -> dict:
    inv = resolve_path(load_settings()["paths"]["inventory_csv"])
    gt = _ground_truth(inv)
    found = _discovered(host_overrides())

    # Document-level recall: each known (town, year) result must be re-found.
    gt_pairs = [(m, y) for m, ys in gt.items() for y in ys]
    hit_pairs = [(m, y) for (m, y) in gt_pairs if y in found.get(m, set())]
    doc_recall = round(100 * len(hit_pairs) / (len(gt_pairs) or 1), 1)
    # Town-level (secondary): did we find ANY election doc for the town?
    gt_towns = set(gt)
    town_hits = {m for m in gt_towns if found.get(m)}
    town_recall = round(100 * len(town_hits) / (len(gt_towns) or 1), 1)
    miss_pairs = sorted(set(gt_pairs) - set(hit_pairs))

    summary = {
        "gt_documents": len(gt_pairs), "gt_towns": len(gt_towns),
        "doc_recall_pct": doc_recall, "documents_recalled": len(hit_pairs),
        "town_recall_pct": town_recall, "towns_recalled": len(town_hits),
        "missing_documents": len(miss_pairs),
    }
    print(f"\n  Ground-truth election recall (document-level: town+year):")
    print(f"    {len(hit_pairs)}/{len(gt_pairs)} known result PDFs re-found "
          f"= {doc_recall}%")
    print(f"  Town-level (found any election doc): "
          f"{len(town_hits)}/{len(gt_towns)} = {town_recall}%")
    if miss_pairs:
        print(f"  missing docs (first 12): {miss_pairs[:12]}")

    out = data_dir() / "discover"
    write_jsonl(out / "groundtruth.jsonl",
                [{"municipality": m, "year": y, "found": (y in found.get(m, set()))}
                 for (m, y) in sorted(gt_pairs)])
    (out / "groundtruth.md").write_text(
        f"# Ground-truth election recall (generated)\n\n"
        f"**Document-level (town+year): {len(hit_pairs)}/{len(gt_pairs)} known "
        f"election PDFs re-found = {doc_recall}%**\n\n"
        f"Town-level (any election doc found): {len(town_hits)}/{len(gt_towns)} "
        f"= {town_recall}%\n\n"
        f"A known (town, year) election result counts as recalled only if the sweep "
        f"found an election-classified file for that town whose URL/anchor carries "
        f"that year. Missing: {len(miss_pairs)} documents.\n",
        encoding="utf-8")
    return summary
