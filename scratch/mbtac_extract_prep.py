"""Stage 3a (extraction prep) for the MBTA Communities Act 3A vote finder.

For each CONFIRMED (and optionally PROBABLE) doc in scratch/mbtac_screen.csv, fetch it once
and dump focused text to scratch/mbtac_text/<town_norm>__<hash>.txt -- the pages carrying the
3A TOPIC plus a little context, page-labeled so an extractor agent can cite page numbers.
Writes scratch/mbtac_extract_manifest.csv (the work-list the extraction workflow consumes).

Fetching here (once, with WAF fallback) means the downstream agents read local text and never
re-hit muni sites. Reuses fetch helpers from mbtac_screen.

Usage: mbtac_extract_prep.py [include_probable=0|1] [context_pages=1]
ASCII-only, explicit UTF-8 I/O.
"""
import csv
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mbtac_screen import fetch_raw, pages_text   # noqa: E402  (safe: guarded main)

SCREEN = HERE / "mbtac_screen.csv"
TXTDIR = HERE / "mbtac_text"
MANIFEST = HERE / "mbtac_extract_manifest.csv"


def focused_text(pages, topic_pages, ctx):
    """Return page-labeled text for topic pages +/- ctx (or whole doc if no page info)."""
    if not pages:
        return ""
    n = len(pages)
    if not topic_pages:
        want = set(range(n))                       # HTML or no topic page -> all
    else:
        want = set()
        for p in topic_pages:                      # topic_pages are 1-based
            for j in range(p - 1 - ctx, p + ctx):
                if 0 <= j < n:
                    want.add(j)
    out = []
    for i in sorted(want):
        out.append(f"\n===== PAGE {i + 1} =====\n{pages[i]}")
    return "".join(out)


def main():
    ctx = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    # Per-town fallback (user rule): extract a town's CONFIRMED docs; only fall back to its
    # PROBABLE docs when that town has NO confirmed source.
    from collections import defaultdict
    by_town = defaultdict(list)
    for r in csv.DictReader(SCREEN.open(encoding="utf-8")):
        by_town[r["town_norm"]].append(r)
    rows = []
    n_conf_towns = n_prob_towns = 0
    for tn, rs in by_town.items():
        conf = [r for r in rs if r["verdict"] == "CONFIRMED"]
        if conf:
            rows.extend(conf)
            n_conf_towns += 1
        else:
            prob = [r for r in rs if r["verdict"] == "PROBABLE"]
            if prob:
                rows.extend(prob)
                n_prob_towns += 1
    print(f"prepping {len(rows)} docs: {n_conf_towns} towns via CONFIRMED, "
          f"{n_prob_towns} towns via PROBABLE-fallback")
    TXTDIR.mkdir(exist_ok=True)

    man = []
    for i, r in enumerate(rows, 1):
        h = hashlib.sha1(r["url"].encode("utf-8")).hexdigest()[:12]
        tf = TXTDIR / f"{r['town_norm']}__{h}.txt"
        try:
            raw = fetch_raw(r["url"])
            pages, npp = pages_text(raw, r["url"])
            tpages = [int(x) for x in r["topic_pages"].split(",") if x.strip()]
            text = focused_text(pages, tpages, ctx)
            tf.write_text(text[:400_000], encoding="utf-8")
            status, chars = "OK", len(text)
        except Exception as e:
            status, chars, npp = f"FAIL:{type(e).__name__}", 0, 0
        man.append({"town": r["town"], "town_norm": r["town_norm"],
                    "community_type": r["community_type"], "governing_body": r.get("governing_body", ""),
                    "board": r["board"], "doctype": r["doctype"], "year": r["year"],
                    "verdict": r["verdict"], "url": r["url"], "npages": npp,
                    "topic_pages": r["topic_pages"], "textfile": str(tf), "status": status,
                    "chars": chars})
        if i % 25 == 0:
            print(f"  {i}/{len(rows)}", flush=True)

    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(man[0].keys()))
        w.writeheader()
        w.writerows(man)
    ok = sum(1 for m in man if m["status"] == "OK")
    print(f"wrote {MANIFEST.name}: {ok}/{len(man)} text dumps OK -> {TXTDIR.name}/")


if __name__ == "__main__":
    main()
