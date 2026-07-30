"""Consolidate the corpus: merge nodes.jsonl + nodes_docsweep + nodes_minutes +
nodes_idsweep, dedup by urlkey (lowercased path), backfill municipality from seed_host,
write a single clean nodes.jsonl. Component files kept for provenance; nodes.jsonl backed
up first."""
from __future__ import annotations
import json, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from muni_harvest.discover.model import urlkey, norm_host
from muni_harvest.discover.pipeline import host_to_municipality
from muni_harvest.config import resolve_path, load_settings

DISC = Path(__file__).resolve().parents[1] / "data" / "discover"
# richest metadata first: nodes.jsonl (muni-tagged wayback/crawl/cms) then the enrichers
SOURCES = ["nodes.jsonl", "nodes_docsweep.jsonl", "nodes_minutes.jsonl", "nodes_idsweep.jsonl"]

# host -> municipality (from the verified inventory) to backfill untagged nodes
inv = resolve_path(load_settings()["paths"]["inventory_csv"])
h2m = host_to_municipality(inv) if inv.exists() else {}

# also learn host->muni from any already-tagged node (covers hosts not in inventory)
learned: dict[str, str] = {}
for src in SOURCES:
    p = DISC / src
    if not p.exists():
        continue
    for line in p.open(encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        m = r.get("municipality")
        h = r.get("seed_host") or ""
        if m and h and h not in learned:
            learned[h] = m
print(f"host->muni: {len(h2m)} from inventory, {len(learned)} learned from tags")

def muni_for(rec):
    return (rec.get("municipality") or h2m.get(rec.get("seed_host", ""))
            or learned.get(rec.get("seed_host", "")) or "")

seen: set[str] = set()
out = DISC / "nodes_consolidated.jsonl"
kept = dupes = backfilled = 0
with out.open("w", encoding="utf-8") as w:
    for src in SOURCES:
        p = DISC / src
        if not p.exists():
            continue
        for line in p.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            u = r.get("url", "")
            if not u:
                continue
            k = urlkey(u)
            if k in seen:
                dupes += 1
                continue
            seen.add(k)
            if not r.get("municipality"):
                m = muni_for(r)
                if m:
                    r["municipality"] = m
                    backfilled += 1
            r["urlkey"] = k
            w.write(json.dumps(r) + "\n")
            kept += 1

print(f"kept {kept:,} distinct nodes | dropped {dupes:,} duplicates | "
      f"backfilled municipality on {backfilled:,}")

# swap into place (back up the old master once)
master = DISC / "nodes.jsonl"
bak = DISC / "nodes.pre_consolidate.jsonl"
if not bak.exists():
    shutil.copy2(master, bak)
    print(f"backed up old master -> {bak.name}")
shutil.move(str(out), str(master))
print(f"consolidated -> {master} ({kept:,} nodes)")
