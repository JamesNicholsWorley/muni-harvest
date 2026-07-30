"""Stage 1b (targeted live fetch) for the MBTA Communities Act 3A vote finder.

For the towns where the (Wayback-heavy) corpus yields no confirmed 3A vote, sweep each
town's CURRENT website with the existing docsweep.sweep_host and append the harvested
minutes / warrant / topic nodes to data/discover/nodes_mbtac_live.jsonl. Stage 1
(mbtac_candidates.py) already reads that file, so re-running candidates+screen after this
picks up the fresh docs.

This is deliberately run only on the browser-tier GAP HOSTS (config/mbtac_gap_hosts_local.txt,
produced by mbtac_coverage.py) -- the WAF/browser hosts that the sharded Actions sweep cannot
do (runners have no browser). The bulk (config/mbtac_gap_hosts.txt) goes through docsweep-shard.yml.

Input is one HOST per line; municipality is reverse-mapped from towns_websites.csv.

Usage: mbtac_livesweep.py <hosts.txt> [max_pages_per_host] [max_seconds_per_host] [use_browser=1]
ASCII-only, explicit UTF-8 I/O.
"""
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
from muni_harvest.discover.model import norm_host
from muni_harvest.discover.docsweep import sweep_host

TOWNS = ROOT / "config" / "mbtac_towns.csv"
TOWNS_WEB = Path(r"C:\Users\Owner\documents\CivicAtlasMA\data\inventory\sources\towns_websites.csv")
OUT = ROOT / "data" / "discover" / "nodes_mbtac_live.jsonl"

# Keep only nodes plausibly relevant to a 3A vote (bounds the live file).
KEEP = re.compile(r"minutes|warrant|town[ _-]?meeting|agenda|packet"
                  r"|mbta|section[ _-]?3a|\b3a\b|multi[ _-]?family|zoning|planning", re.I)


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def load_host2name():
    """host (normalized) -> Municipality display name, from towns_websites.csv."""
    m = {}
    for r in csv.DictReader(TOWNS_WEB.open(encoding="utf-8")):
        w = (r.get("Website") or "").strip().lower()
        if not w:
            continue
        host = norm_host(re.sub(r"^https?://", "", w).strip("/").split("/")[0])
        m[host] = r["Municipality"]
    return m


def main():
    if len(sys.argv) < 2:
        print("usage: mbtac_livesweep.py <hosts.txt> [max_pages] [max_seconds] [use_browser=1]")
        sys.exit(1)
    hosts_file = Path(sys.argv[1])
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    max_seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 600.0
    use_browser = (sys.argv[4] if len(sys.argv) > 4 else "1") == "1"

    hosts = [norm_host(ln.strip()) for ln in hosts_file.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    host2name = load_host2name()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    kept_total = 0
    with OUT.open("a", encoding="utf-8") as out:
        for i, host in enumerate(hosts, 1):
            town = host2name.get(host, host)
            try:
                nodes, stats = sweep_host(host, municipality=town, use_browser=use_browser,
                                          max_pages=max_pages, max_seconds=max_seconds)
            except Exception as e:
                print(f"[{i}/{len(hosts)}] {town} ({host}): SWEEP_FAIL {type(e).__name__}: {e}",
                      flush=True)
                continue
            kept = 0
            for n in nodes:
                hay = n.get("url", "") + " " + (n.get("anchor") or "")
                if KEEP.search(hay):
                    out.write(json.dumps(n) + "\n")
                    kept += 1
            out.flush()
            kept_total += kept
            print(f"[{i}/{len(hosts)}] {town} ({stats.get('host')}): pages={stats.get('pages')} "
                  f"files={stats.get('files')} kept={kept} "
                  f"budget_hit={stats.get('budget_hit')}", flush=True)
    print(f"\nappended {kept_total} relevant nodes to {OUT.name}")


if __name__ == "__main__":
    main()
