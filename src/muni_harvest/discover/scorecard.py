"""Coverage scorecard — the progress KPI.

Every municipality should have four document classes: agendas, minutes, election
results, and budget/warrant/bylaws. We roll the discovered file nodes up to the
municipality (aggregating its multiple hosts) and report who has what. Canonical ->
view: writes scorecard.jsonl (truth) and scorecard.md (one-way render).
"""

from __future__ import annotations

from ..config import data_dir, load_settings, resolve_path
from ..core import iter_jsonl, write_jsonl

# fine doctype -> KPI bucket
BUCKET = {
    "agenda": "agendas",
    "minutes": "minutes",
    "election": "election_results",
    "budget": "budget_warrant_bylaws",
    "warrant": "budget_warrant_bylaws",
    "bylaw": "budget_warrant_bylaws",
}
CORE = ["agendas", "minutes", "election_results", "budget_warrant_bylaws"]


def _all_municipalities(inventory) -> set[str]:
    import csv
    out = set()
    if inventory.exists():
        with inventory.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("municipality"):
                    out.add(row["municipality"])
    return out


def build() -> dict:
    nodes_path = data_dir() / "discover" / "nodes.jsonl"
    inventory = resolve_path(load_settings()["paths"]["inventory_csv"])

    present: dict[str, set] = {}
    counts: dict[str, dict] = {}
    for n in iter_jsonl(nodes_path):
        if n.get("kind") != "file":
            continue
        muni = n.get("municipality") or f"(host:{n['seed_host']})"
        bucket = BUCKET.get(n.get("doctype", ""))
        present.setdefault(muni, set())
        counts.setdefault(muni, {b: 0 for b in CORE})
        if bucket:
            present[muni].add(bucket)
            counts[muni][bucket] += 1

    rows = []
    for muni in sorted(present):
        have = present[muni]
        rows.append({"municipality": muni,
                     **{b: (b in have) for b in CORE},
                     "counts": counts[muni],
                     "has_all_core": all(b in have for b in CORE)})

    all_munis = _all_municipalities(inventory)
    denom = len(all_munis) or len(rows) or 1
    summary = {
        "municipalities_with_any_doc": len(rows),
        "municipalities_total": len(all_munis),
        "pct_by_bucket": {
            b: round(100 * sum(1 for r in rows if r[b]) / denom, 1) for b in CORE
        },
        "with_all_core": sum(1 for r in rows if r["has_all_core"]),
        "pct_with_all_core": round(
            100 * sum(1 for r in rows if r["has_all_core"]) / denom, 1),
    }

    out_dir = data_dir() / "discover"
    write_jsonl(out_dir / "scorecard.jsonl", rows)
    _render(out_dir / "scorecard.md", summary, rows, denom)
    _print(summary, denom)
    return summary


def _print(s: dict, denom: int) -> None:
    print(f"\n  Coverage scorecard  ({s['municipalities_with_any_doc']} municipalities "
          f"with docs / {s['municipalities_total']} total)\n")
    for b in CORE:
        print(f"    {b:<24} {s['pct_by_bucket'][b]:>5.1f}%  "
              f"({round(s['pct_by_bucket'][b] * denom / 100)} towns)")
    print(f"    {'ALL FOUR core docs':<24} {s['pct_with_all_core']:>5.1f}%  "
          f"({s['with_all_core']} towns)\n")


def _render(path, s: dict, rows: list, denom: int) -> None:
    import time
    lines = [
        "# Coverage scorecard (generated — source: nodes.jsonl)",
        "",
        f"_Rendered: {time.strftime('%Y-%m-%dT%H:%M:%S')}_",
        "",
        f"Municipalities with any document: **{s['municipalities_with_any_doc']}** "
        f"of {s['municipalities_total']} known.",
        "",
        "| Document class | Coverage |",
        "|---|--:|",
    ]
    for b in CORE:
        lines.append(f"| {b} | {s['pct_by_bucket'][b]:.1f}% |")
    lines.append(f"| **all four core** | **{s['pct_with_all_core']:.1f}%** |")
    lines += ["", "## Per-municipality", "",
              "| Municipality | agendas | minutes | election | budget/warrant/bylaw | all core |",
              "|---|:-:|:-:|:-:|:-:|:-:|"]
    mark = {True: "Y", False: "-"}
    for r in rows:
        lines.append(f"| {r['municipality']} | {mark[r['agendas']]} | "
                     f"{mark[r['minutes']]} | {mark[r['election_results']]} | "
                     f"{mark[r['budget_warrant_bylaws']]} | {mark[r['has_all_core']]} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
