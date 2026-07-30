"""Stage 3a (extraction prep) for the MBTA Communities Act 3A vote finder.

For each CONFIRMED doc (per-town PROBABLE fallback when a town has no confirmed source), fetch
once and crop to TIGHT SNIPPETS: ~2000-char windows around each 3A-topic anchor (the topic is
rare, the vote/tally sits next to it), page-labeled, capped per doc. Then BATCH ~12 docs into
one self-contained text file so a single extractor agent handles many docs -- cutting both the
token payload (snippets, not whole pages) and per-agent fixed overhead.

Outputs:
  scratch/mbtac_batches/batch_NNN.txt   -- each holds up to BATCH docs, each block headed by a
                                           metadata line: ### DOC <id> | town | ... | url
  scratch/mbtac_extract_index.csv       -- doc_id -> full metadata (for final enrichment)
Fetching here (once, WAF fallback) means downstream agents read local text and never re-hit sites.

Usage: mbtac_extract_prep.py [batch=12] [win_chars=2000] [cap_chars=10000]
ASCII-only, explicit UTF-8 I/O.
"""
import csv
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mbtac_screen import fetch_raw, pages_text, TOPIC, VOTE   # noqa: E402 (guarded main)

SCREEN = HERE / "mbtac_screen.csv"
TOWNS = HERE.parent / "config" / "mbtac_towns.csv"
BATCHDIR = HERE / "mbtac_batches"
INDEX = HERE / "mbtac_extract_index.csv"


def gov_map():
    return {r["town_norm"]: r["governing_body"]
            for r in csv.DictReader(TOWNS.open(encoding="utf-8"))}


_TOPIC_NEAR = re.compile(r"mbta|3a\b|multi[ _-]?family|overlay", re.I)


def snippets(pages, win, cap):
    """Windows around 3A TOPIC anchors AND vote-lines near a topic term (+/- win chars),
    merged, page-tagged, capped -- so a results table stated apart from the topic heading is
    still captured."""
    full = "".join(f"\n[PAGE {i + 1}]\n{t}" for i, t in enumerate(pages))
    anchors = [m.start() for m in TOPIC.finditer(full)]
    # Also anchor on vote-language whose +/-250-char neighborhood mentions a topic term.
    for m in VOTE.finditer(full):
        s = m.start()
        if _TOPIC_NEAR.search(full[max(0, s - 250):s + 250]):
            anchors.append(s)
    anchors.sort()
    if not anchors:                       # HTML/no page info -> lightly trimmed whole text
        return full[:cap]
    wins = sorted((max(0, a - win), min(len(full), a + win)) for a in anchors)
    merged = []
    for a, b in wins:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    out = []
    tot = 0
    for a, b in merged:
        seg = full[a:b]
        out.append(seg)
        tot += len(seg)
        if tot >= cap:
            break
    return "\n. . .\n".join(out)[:cap]


def select_rows():
    """Per-town rule: a town's CONFIRMED docs; PROBABLE only if the town has no CONFIRMED."""
    by_town = defaultdict(list)
    for r in csv.DictReader(SCREEN.open(encoding="utf-8")):
        by_town[r["town_norm"]].append(r)
    rows, nc, npb = [], 0, 0
    for rs in by_town.values():
        conf = [r for r in rs if r["verdict"] == "CONFIRMED"]
        if conf:
            rows.extend(conf); nc += 1
        else:
            prob = [r for r in rs if r["verdict"] == "PROBABLE"]
            if prob:
                rows.extend(prob); npb += 1
    print(f"selected {len(rows)} docs: {nc} towns via CONFIRMED, {npb} via PROBABLE-fallback")
    return rows


def main():
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    win = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 10000

    rows = select_rows()
    gm = gov_map()
    for r in rows:
        r["governing_body"] = gm.get(r["town_norm"], "")
    BATCHDIR.mkdir(exist_ok=True)
    for old in BATCHDIR.glob("batch_*.txt"):
        old.unlink()

    docs = []
    for i, r in enumerate(rows, 1):
        doc_id = hashlib.sha1(r["url"].encode("utf-8")).hexdigest()[:10]
        try:
            raw = fetch_raw(r["url"])
            pages, npp = pages_text(raw, r["url"])
            text = snippets(pages, win, cap)
            status = "OK" if text.strip() else "EMPTY"
        except Exception as e:
            text, status = "", f"FAIL:{type(e).__name__}"
        docs.append({**r, "doc_id": doc_id, "text": text, "status": status})
        if i % 25 == 0:
            print(f"  fetched {i}/{len(rows)}", flush=True)

    ok = [d for d in docs if d["status"] == "OK"]
    print(f"{len(ok)}/{len(docs)} docs have usable snippet text")

    # Write batches.
    nb = 0
    for b in range(0, len(ok), batch):
        chunk = ok[b:b + batch]
        nb += 1
        lines = []
        for d in chunk:
            lines.append(
                f"\n### DOC {d['doc_id']} | town={d['town']} | community_type={d['community_type']} "
                f"| governing_body={d['governing_body']} | screened_board={d['board']} "
                f"| screened_doctype={d['doctype']} | url={d['url']}\n{d['text']}\n")
        (BATCHDIR / f"batch_{nb - 1:03d}.txt").write_text("".join(lines), encoding="utf-8")

    with INDEX.open("w", encoding="utf-8", newline="") as f:
        cols = ["doc_id", "town", "town_norm", "community_type", "governing_body", "board",
                "doctype", "year", "verdict", "url", "status"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for d in docs:
            w.writerow(d)
    # rough token estimate
    chars = sum(len(d["text"]) for d in ok)
    print(f"wrote {nb} batch files (<= {batch} docs each) to {BATCHDIR.name}/")
    print(f"  total snippet chars: {chars:,}  (~{chars // 4:,} tokens of doc text, pre-overhead)")
    print(f"wrote {INDEX.name}")


if __name__ == "__main__":
    main()
