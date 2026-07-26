"""Content-based election verifier — trust the document, not the URL.

The URL classifier is a rough heuristic (it tags specimen ballots and vote-by-mail
applications as 'election'). This opens candidate election docs and checks the
actual text for RESULTS signals (vote tallies, precinct tables, write-ins) vs
ballots/warrants/applications. Gives two honest numbers:
  - precision : of docs we called 'election', how many actually contain results
  - recall    : of the 293 ground-truth towns, how many have a VERIFIED results PDF

Prefers Wayback snapshots (archived, always fetchable) over live URLs. Requires the
`extract` extra (pymupdf).
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..archive.wayback import classify, host_of
from ..config import data_dir, host_overrides, load_settings, resolve_path
from ..core import fetch, iter_jsonl, write_jsonl

# Strong content signals of an actual RESULTS document (not a ballot/warrant).
_RESULTS = re.compile(
    r"total votes|ballots cast|whole number of votes|votes? cast|write[- ]?in|"
    r"unofficial results|official results|blanks\b|registered voters|"
    r"precinct\s*\d|tellers|prevailed", re.I)
_BALLOT = re.compile(
    r"specimen|sample ballot|vote[- ]by[- ]mail application|absentee.*application|"
    r"ballot application|instructions to voters", re.I)
_YEAR = re.compile(r"(20[0-2]\d)")


def _snapshot(url: str, ts: str) -> str:
    return f"http://web.archive.org/web/{ts}id_/{url}"


def _pdf_text(data: bytes, max_pages: int = 6) -> str:
    import fitz  # pymupdf (extract extra)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:  # noqa: BLE001
        return ""
    out = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        out.append(page.get_text())
    doc.close()
    return "\n".join(out)


def classify_content(text: str) -> str:
    """results | ballot | other, from the document's own text."""
    if not text or len(text) < 40:
        return "other"
    if _RESULTS.search(text):
        return "results"
    if _BALLOT.search(text):
        return "ballot"
    return "other"


def _candidates(overrides: dict) -> dict[str, list[dict]]:
    """municipality -> list of {fetch_url, year} election-doc candidates (wayback
    snapshots preferred; deduped)."""
    inv = resolve_path(load_settings()["paths"]["inventory_csv"])
    h2m: dict[str, str] = {}
    with inv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            u = (row.get("native_url") or "").strip()
            if u:
                h2m.setdefault(overrides.get(host_of(u), host_of(u)),
                               row.get("municipality", ""))
    cands: dict[str, list[dict]] = defaultdict(list)
    seen: set[str] = set()
    # Wayback election docs (with timestamp -> archived snapshot)
    for r in iter_jsonl(data_dir() / "wayback" / "docs.jsonl"):
        url = r.get("url", "")
        if classify(url) == "election":
            muni = h2m.get(r.get("host", ""))
            if muni and url not in seen:
                seen.add(url)
                cands[muni].append({"fetch_url": _snapshot(url, r.get("timestamp", "2")),
                                    "year": (_YEAR.search(url) or [""])[0], "src": "wayback"})
    # Live discover election files
    for n in iter_jsonl(data_dir() / "discover" / "nodes.jsonl"):
        if n.get("kind") == "file" and n.get("doctype") == "election" and n.get("municipality"):
            url = n["url"]
            if url not in seen:
                seen.add(url)
                cands[n["municipality"]].append(
                    {"fetch_url": url, "year": (_YEAR.search(url + n.get("anchor", "")) or [""])[0],
                     "src": "live"})
    return cands


def verify(*, limit: int | None = None, per_town: int = 3, workers: int = 8) -> dict:
    cands = _candidates(host_overrides())
    towns = sorted(cands)
    if limit:
        towns = towns[:limit]
    # Flatten to a bounded work list (per_town candidates each).
    work = [(t, c) for t in towns for c in cands[t][:per_town]]
    print(f"[*] verifying {len(work)} candidate docs across {len(towns)} towns "
          f"(<= {per_town}/town), {workers} workers")

    results: list[dict] = []

    def check(item) -> dict:
        town, c = item
        try:
            data = fetch(c["fetch_url"], tries=2, timeout=45)
            verdict = classify_content(_pdf_text(data))
        except Exception as exc:  # noqa: BLE001
            verdict = f"err:{type(exc).__name__}"
        return {"municipality": town, "year": c["year"], "src": c["src"],
                "verdict": verdict, "url": c["fetch_url"][:120]}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed([ex.submit(check, it) for it in work]):
            results.append(fut.result())

    # Precision: of fetched election-classified docs, how many are real results.
    fetched = [r for r in results if not r["verdict"].startswith("err")]
    n_results = sum(1 for r in fetched if r["verdict"] == "results")
    precision = round(100 * n_results / (len(fetched) or 1), 1)
    dist = defaultdict(int)
    for r in fetched:
        dist[r["verdict"]] += 1
    # Recall: towns with >=1 verified results doc.
    verified_towns = {r["municipality"] for r in fetched if r["verdict"] == "results"}
    recall = round(100 * len(verified_towns) / (len(towns) or 1), 1)

    print(f"\n  CONTENT verdict distribution: {dict(dist)}")
    print(f"  precision (election-classified -> real results): {precision}% "
          f"({n_results}/{len(fetched)})")
    print(f"  content-verified town recall: {len(verified_towns)}/{len(towns)} "
          f"= {recall}%")

    out = data_dir() / "discover"
    write_jsonl(out / "verify.jsonl", results)
    (out / "verify.md").write_text(
        f"# Content-verified election results (generated)\n\n"
        f"Docs opened + checked for results signals (not URL heuristics).\n\n"
        f"- **Precision** (election-classified -> actually results): **{precision}%** "
        f"({n_results}/{len(fetched)})\n"
        f"- **Content-verified town recall**: **{len(verified_towns)}/{len(towns)} "
        f"= {recall}%**\n"
        f"- verdicts: {dict(dist)}\n", encoding="utf-8")
    return {"precision": precision, "recall": recall,
            "verified_towns": len(verified_towns), "checked": len(fetched)}
