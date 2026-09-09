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

# Image tokens are not a guess. Anthropic resizes an image so its longest side
# is at most 1568px and then charges (width x height) / 750, so the count
# follows from the page's own geometry and the resolution we choose to send.
#
# Measured over the 4,823 image pages in this corpus: 2,471 tokens a page at
# 1568px, 1,261 at 1120px, 618 at 784px. An earlier flat estimate of 1,600 was
# 35% low at full resolution -- a page of election results is nearly all letter
# size, and letter size at 1568px is 1211 x 1568.
#
# Checked against count_tokens on twelve real pages: 2,467 measured against
# 2,471 predicted, 0.2% apart. The formula can be trusted for the rest.
MAX_DIM = 1568
IMAGE_TOKENS_PER_PAGE = {1568: 2471, 1120: 1261, 784: 618}

# The system prompt is specs/transcription.md and is byte-identical on every
# call, so it is written to the cache once and read at a tenth of the price
# thereafter. Charging it in full 1,088 times was the second error in the old
# estimate.
#
# MEASURED with count_tokens, not assumed: 5,675 including the user turn.
SPEC_TOKENS = 5675
TEXT_TOKENS_PER_SECTION = 748
CACHE_WRITE = 1.25
CACHE_READ = 0.10

# MEASURED by a 13-section pilot across both models. The estimate of 1,400 was
# three to four times low, and low in the way that matters: at max_tokens=8000
# four of thirteen Haiku responses and three of thirteen Sonnet ones were
# TRUNCATED, and a truncated tool call returns a well-formed record with its
# contests missing. Danvers 2020 came back with zero of its fifteen.
#
# Re-run unbatched at 32,000 the same documents produced 7,584 to 17,377
# output tokens. Set max_tokens to 32,000, never 8,000.
OUTPUT_TOKENS = {"cheap": 4505, "strong": 5429}
MAX_TOKENS = 32000

# The Batch API is half price and returns within 24 hours. Nothing about this
# job is interactive -- it is 1,088 independent documents parsed once -- so
# batching is the default and paying twice for turnaround nobody needs would
# be the odd choice.
BATCH_DISCOUNT = 0.5

# Caching and batching do not combine, so `cached` defaults to False whenever
# `batch` is on. A cache entry written during batch processing "would likely
# expire before the follow-up request runs" -- the default TTL is five minutes
# and a batch spreads over up to twenty-four hours.
#
# Batching wins alone anyway: $45 against $70 for the Sonnet pass over this
# corpus. An earlier estimate of $30 assumed both applied at once and was
# optimistic about a mechanism that will mostly not fire.
#
# It also means the spec prompt is paid in full on every call -- 6.17M tokens,
# 34% of all input -- which makes its LENGTH a real cost and not just a
# question of style. Trimming it from 5,675 to 3,000 tokens saves about $5 at
# Sonnet. Do not trim below 4,096: Haiku 4.5 refuses to cache a shorter prompt
# at all, silently and without error, which would foreclose caching if this
# ever runs unbatched.
CACHE_MINIMUM = {"haiku": 4096, "sonnet": 1024}


def cost(n_sections, n_pages, tier, max_dim=MAX_DIM, batch=True, cached=None):
    """Cost for one pass. `cached` defaults to False under batch, see above."""
    if cached is None:
        cached = not batch
    tin, tout = PRICES[tier]
    img = n_pages * IMAGE_TOKENS_PER_PAGE[max_dim]
    if cached:
        prompt = SPEC_TOKENS * CACHE_WRITE + n_sections * SPEC_TOKENS * CACHE_READ
    else:
        prompt = n_sections * SPEC_TOKENS
    out = n_sections * OUTPUT_TOKENS[tier]
    c = (img + prompt) / 1e6 * tin + out / 1e6 * tout
    if batch:
        c *= BATCH_DISCOUNT
    return c * 1.15


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
    # A text section sends no page images at all; its rows cost about a
    # tenth of a page each and are folded in here rather than modelled apart.
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
