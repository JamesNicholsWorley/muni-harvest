"""Submit a small parse batch and measure what the estimate could not.

Three things are unmeasured in the quote and only a real call settles them:

  output tokens   estimated at 1,400 a section and 38% of the Sonnet figure --
                  the largest single uncertainty
  cache in batch  the docs say an entry written during batch processing "would
                  likely expire before the follow-up request runs", so the
                  system block is sent WITH cache_control and the response's
                  cache_read_input_tokens is read back to see whether it fired
  quality         one section in the sample has a known answer, so the output
                  can be checked against arithmetic rather than eyeballed

Both models get byte-identical requests, so their outputs are comparable and
the escalation rate can be measured rather than assumed.
"""
import argparse
import base64
import io
import json
import os
import sys
import time

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.atr_tool import TOOL                            # noqa: E402

pymupdf.TOOLS.mupdf_display_errors(False)

MAX_DIM = 1568
MODELS = {"haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-5"}
PRICES = {"haiku": (1.0, 5.0), "sonnet": (3.0, 15.0)}


def page_png(page):
    s = MAX_DIM / max(page.rect.width, page.rect.height)
    return page.get_pixmap(matrix=pymupdf.Matrix(s, s)).tobytes("png")


def content_for(rec, text_dir):
    """Images, or the agreed text where two readers produced the same rows."""
    blocks = []
    if rec["kind"] == "text":
        p = os.path.join(text_dir, rec["stem"] + ".txt")
        if os.path.exists(p):
            blocks.append({"type": "text",
                           "text": "=== TRANSCRIBED ROWS (two independent "
                                   "readers agreed on every line) ===\n"
                                   + io.open(p, encoding="utf-8").read()})
            return blocks
    for page in pymupdf.open(rec["path"]):
        blocks.append({"type": "image",
                       "source": {"type": "base64", "media_type": "image/png",
                                  "data": base64.b64encode(page_png(page)).decode()}})
    return blocks


def build(recs, spec, text_dir, model_key):
    reqs = []
    for r in recs:
        blocks = content_for(r, text_dir)
        blocks.append({"type": "text",
                       "text": f"Transcribe the annual municipal election in "
                               f"this document. The filename says "
                               f"{r['stem']}, which is a hypothesis about the "
                               f"town and year, not evidence -- read both off "
                               f"the page."})
        reqs.append({
            "custom_id": f"{model_key}--{r['stem']}",
            "params": {
                "model": MODELS[model_key],
                "max_tokens": 8000,
                # cache_control on the system block alone: the spec is
                # byte-identical on every call, the document content is not.
                "system": [{"type": "text", "text": spec,
                            "cache_control": {"type": "ephemeral"}}],
                "tools": [TOOL],
                "tool_choice": {"type": "tool", "name": "emit_return"},
                "messages": [{"role": "user", "content": blocks}],
            }})
    return reqs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", required=True)
    ap.add_argument("--text-dir", default="")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--models", default="haiku,sonnet")
    ap.add_argument("--out", default="pilot_out")
    ap.add_argument("--submit", action="store_true",
                    help="actually submit. Without it nothing is billed.")
    a = ap.parse_args()

    recs = json.load(io.open(a.sections, encoding="utf-8"))
    spec = io.open(a.spec, encoding="utf-8").read()
    os.makedirs(a.out, exist_ok=True)

    from anthropic import Anthropic
    client = Anthropic()

    for key in a.models.split(","):
        reqs = build(recs, spec, a.text_dir, key)
        size = len(json.dumps(reqs))
        print(f"{key}: {len(reqs)} requests, {size/1e6:.1f}MB payload")
        if not a.submit:
            continue
        batch = client.messages.batches.create(requests=reqs)
        io.open(os.path.join(a.out, f"batch_{key}.txt"), "w").write(batch.id)
        print(f"  submitted {batch.id}")

    if not a.submit:
        print("\nDRY RUN. Nothing was billed. Pass --submit to send it.")


if __name__ == "__main__":
    main()
