"""Dynamic budget ledger — append-only data/budget.jsonl, one-way data/budget.md view.

Canonical->view discipline (per AbundanceHistory rule): budget.jsonl is the single
source of truth; budget.md is regenerated and never hand-edited.

Record types
------------
alloc     : set/adjust a category's reserve. Sum of all `alloc` amounts == total budget.
            A rebalance is just a pair of alloc deltas that net to zero.
spend     : real money charged by a vendor. Reduces that category's remaining.

Usage (via the top-level CLI)
-----------------------------
  muni-harvest budget seed                 # write the opening $40 allocation (once)
  muni-harvest budget spend --category llm --vendor openrouter --amount 3.50 --note "batch A"
  muni-harvest budget alloc --category vm  --amount -4.00 --note "move to unblocker"
  muni-harvest budget alloc --category unblocker --amount 4.00 --note "from vm"
  muni-harvest budget summary
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from ..config import data_dir
from ..core import append_jsonl, iter_jsonl

# Canonical category keys and their human labels (order = display order).
CATEGORIES = {
    "vm":          "Always-on VM (Hetzner)",
    "unblocker":   "Unblocker API (Zyte/ScraperAPI)",
    "llm":         "LLM/vision structuring",
    "storage":     "Object storage (R2/B2)",
    "contingency": "Contingency",
}

# Opening allocation — sums to the settings.toml total (40.0).
SEED_ALLOC = {
    "vm":          18.0,
    "unblocker":   8.0,
    "llm":         8.0,
    "storage":     4.0,
    "contingency": 2.0,
}


def _ledger_path() -> Path:
    return data_dir() / "budget.jsonl"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _record(rectype: str, category: str, amount: float, vendor: str, note: str) -> None:
    if category not in CATEGORIES:
        raise SystemExit(f"[ERR] unknown category '{category}'. "
                         f"choices: {', '.join(CATEGORIES)}")
    append_jsonl(_ledger_path(), [{
        "ts": _now(), "type": rectype, "category": category,
        "vendor": vendor, "amount_usd": round(float(amount), 2), "note": note,
    }])


def seed(force: bool = False) -> None:
    path = _ledger_path()
    existing = list(iter_jsonl(path))
    if existing and not force:
        raise SystemExit(f"[SKIP] ledger already has {len(existing)} records "
                         f"({path}). Use --force to re-seed.")
    for cat, amt in SEED_ALLOC.items():
        append_jsonl(path, [{
            "ts": _now(), "type": "alloc", "category": cat,
            "vendor": "", "amount_usd": amt, "note": "opening allocation",
        }])
    print(f"[OK] seeded opening allocation (${sum(SEED_ALLOC.values()):.2f}) -> {path}")
    _write_markdown()


def _tally() -> dict:
    """Return {category: {'alloc': x, 'spent': y, 'remaining': x-y}}."""
    tally = {c: {"alloc": 0.0, "spent": 0.0} for c in CATEGORIES}
    for rec in iter_jsonl(_ledger_path()):
        cat = rec.get("category")
        if cat not in tally:
            continue
        if rec["type"] == "alloc":
            tally[cat]["alloc"] += rec["amount_usd"]
        elif rec["type"] == "spend":
            tally[cat]["spent"] += rec["amount_usd"]
    for c in tally:
        tally[c]["remaining"] = round(tally[c]["alloc"] - tally[c]["spent"], 2)
    return tally


def summary() -> None:
    tally = _tally()
    tot_a = sum(t["alloc"] for t in tally.values())
    tot_s = sum(t["spent"] for t in tally.values())
    print(f"\n  muni-harvest budget  |  allocated ${tot_a:.2f}  "
          f"spent ${tot_s:.2f}  remaining ${tot_a - tot_s:.2f}\n")
    print(f"  {'category':<34}{'alloc':>9}{'spent':>9}{'remain':>9}")
    print(f"  {'-' * 34}{'-' * 9:>9}{'-' * 9:>9}{'-' * 9:>9}")
    for cat, label in CATEGORIES.items():
        t = tally[cat]
        print(f"  {label:<34}{t['alloc']:>9.2f}{t['spent']:>9.2f}"
              f"{t['remaining']:>9.2f}")
    print()
    _write_markdown()


def _write_markdown() -> None:
    """One-way render of the ledger to data/budget.md (never hand-edited)."""
    tally = _tally()
    tot_a = sum(t["alloc"] for t in tally.values())
    tot_s = sum(t["spent"] for t in tally.values())
    lines = [
        "# Budget (generated — do not edit; source: budget.jsonl)",
        "",
        f"_Last rendered: {_now()}_",
        "",
        f"**Allocated ${tot_a:.2f} | Spent ${tot_s:.2f} | "
        f"Remaining ${tot_a - tot_s:.2f}**",
        "",
        "| Category | Allocated | Spent | Remaining |",
        "|---|--:|--:|--:|",
    ]
    for cat, label in CATEGORIES.items():
        t = tally[cat]
        lines.append(f"| {label} | ${t['alloc']:.2f} | ${t['spent']:.2f} "
                     f"| ${t['remaining']:.2f} |")
    lines += ["", "## Ledger entries", "",
              "| Date | Type | Category | Vendor | Amount | Note |",
              "|---|---|---|---|--:|---|"]
    for rec in iter_jsonl(_ledger_path()):
        lines.append(f"| {rec['ts']} | {rec['type']} | {rec['category']} "
                     f"| {rec.get('vendor', '')} | ${rec['amount_usd']:.2f} "
                     f"| {rec.get('note', '')} |")
    (data_dir() / "budget.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(prog="muni-harvest budget")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("summary", help="print the budget table and regenerate budget.md")

    p_seed = sub.add_parser("seed", help="write the opening $40 allocation")
    p_seed.add_argument("--force", action="store_true")

    p_spend = sub.add_parser("spend", help="record real money charged by a vendor")
    p_spend.add_argument("--category", required=True, choices=list(CATEGORIES))
    p_spend.add_argument("--vendor", default="")
    p_spend.add_argument("--amount", type=float, required=True)
    p_spend.add_argument("--note", default="")

    p_alloc = sub.add_parser("alloc", help="adjust a category reserve (rebalance)")
    p_alloc.add_argument("--category", required=True, choices=list(CATEGORIES))
    p_alloc.add_argument("--amount", type=float, required=True)
    p_alloc.add_argument("--note", default="")

    args = ap.parse_args(argv)
    if args.cmd == "summary":
        summary()
    elif args.cmd == "seed":
        seed(force=args.force)
    elif args.cmd == "spend":
        _record("spend", args.category, args.amount, args.vendor, args.note)
        print(f"[OK] spend ${args.amount:.2f} on {args.category}")
        summary()
    elif args.cmd == "alloc":
        _record("alloc", args.category, args.amount, "", args.note)
        print(f"[OK] alloc {args.amount:+.2f} to {args.category}")
        summary()
