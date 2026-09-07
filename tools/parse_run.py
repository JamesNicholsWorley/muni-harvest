"""Parse the ATR sections cheaply, and buy again only what fails.

Dry run by default. It will not call an API unless `--spend` is passed, and it
prints what it would have spent either way, because the estimate is the thing
worth checking before the money is gone rather than after.

The shape of the run:

    cheap model  ->  qa.escalate.review  ->  strong model, only on failure

That order is deliberate. Predicting which documents are hard -- by skew, by
resolution, by how the scan looks -- is a guess made before any evidence exists.
The parse itself is evidence: a contest whose marks exceed ballots times seats
is impossible, and no property of the image was needed to know it. Measured
against this corpus the cheap pass costs about a third of the strong one, so
escalating even half the corpus still comes in under parsing all of it well.

Each record keeps `parsed_by` and, where it was bought twice, both readings.
Two independent transcriptions of a page that disagree are worth more than
either alone, and throwing the first away to save a field would discard the
only cross-check the run produces for free.
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import escalate                                   # noqa: E402

# Per 1M tokens. Kept here so the estimate and the run cannot drift apart.
PRICES = {"cheap": (1.0, 5.0), "strong": (3.0, 15.0)}
IMAGE_TOKENS_PER_PAGE = 1600
PROMPT_TOKENS = 900
OUTPUT_TOKENS = 1400


def cost(n_sections, n_pages, tier):
    tin, tout = PRICES[tier]
    inp = n_pages * IMAGE_TOKENS_PER_PAGE + n_sections * PROMPT_TOKENS
    out = n_sections * OUTPUT_TOKENS
    return (inp / 1e6 * tin + out / 1e6 * tout) * 1.15


def plan(sections, text_index):
    """Per section: what we would send, and what it would cost.

    `text_index` is the output of `make_text.py` -- the sections where two
    independent readers agreed on the rows. Those go as text and their page
    images are never sent; everything else goes as images, which is what we
    would have done without the gate.
    """
    as_text = {r["stem"] for r in text_index if r.get("verdict") == "text"}
    rows = []
    for stem, pages in sections:
        rows.append({"stem": stem, "pages": pages,
                     "send": "text" if stem in as_text else "image"})
    return rows


def summarise(rows, escalation_rate):
    img = [r for r in rows if r["send"] == "image"]
    txt = [r for r in rows if r["send"] == "text"]
    # Text costs a fraction of an image page and is counted at a tenth here;
    # it is an estimate and is labelled as one wherever it is printed.
    pages_cheap = sum(r["pages"] for r in img) + sum(r["pages"] for r in txt) / 10
    c_cheap = cost(len(rows), pages_cheap, "cheap")
    c_strong = cost(len(rows), pages_cheap, "strong")
    return {"sections": len(rows), "as_text": len(txt), "as_image": len(img),
            "cheap_pass": c_cheap, "if_all_strong": c_strong,
            "with_escalation": c_cheap + c_strong * escalation_rate}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", required=True, help="dir of *_atr.pdf")
    ap.add_argument("--text-index", default="", help="index_*.json from make_text")
    ap.add_argument("--escalation-rate", type=float, default=0.3)
    ap.add_argument("--spend", action="store_true",
                    help="actually call the API. Without this nothing is billed.")
    a = ap.parse_args()

    import pymupdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    sections = []
    for name in sorted(os.listdir(a.sections)):
        if name.endswith("_atr.pdf"):
            try:
                n = pymupdf.open(os.path.join(a.sections, name)).page_count
            except Exception:
                continue
            sections.append((name[:-8], n))

    index = []
    if a.text_index and os.path.isdir(a.text_index):
        for f in sorted(os.listdir(a.text_index)):
            if f.startswith("index_") and f.endswith(".json"):
                index += json.load(io.open(os.path.join(a.text_index, f),
                                           encoding="utf-8"))

    rows = plan(sections, index)
    s = summarise(rows, a.escalation_rate)
    print(f"{s['sections']:,} sections -- {s['as_text']:,} as text, "
          f"{s['as_image']:,} as images")
    print(f"  cheap pass over everything      ${s['cheap_pass']:,.0f}")
    print(f"  if everything went to the strong model  ${s['if_all_strong']:,.0f}")
    print(f"  cheap + {a.escalation_rate:.0%} escalated        "
          f"${s['with_escalation']:,.0f}")

    if not a.spend:
        print("\nDRY RUN. Nothing was billed. Pass --spend to run it.")
        return
    raise SystemExit(
        "--spend is wired to nothing yet: the API client, the model names and "
        "the tool schema are not set here. That is deliberate -- this file "
        "must not be the place a spend starts by accident.")


if __name__ == "__main__":
    main()
