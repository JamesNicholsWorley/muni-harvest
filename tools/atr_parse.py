"""Parse the pre-2021 ATR corpus. Submit, then collect, resumably.

Everything the pilot cost is encoded here rather than remembered.

`max_tokens` is 32,000, never 8,000. At 8,000 four of thirteen pilot responses
were truncated, and a truncated tool call does not fail -- it returns a
well-formed record with its contests missing. Danvers 2020 came back with zero
of its fifteen and looked entirely healthy.

Results are written the moment each arrives. A run that writes at the end loses
everything to a timeout, which is exactly how the first untruncated
measurements were lost after they had already been paid for.

The run is resumable and idempotent on the stem: a sub-batch already submitted
is never submitted twice, and a stem already collected is never re-parsed.
5.7GB of base64 payload across some thirty sub-batches is far too much to redo
because a shell died.

`cache_control` sits on the system block alone -- the spec is byte-identical on
every call and the page images are not. The docs imply this cannot hit inside a
batch; in the pilot it hit, so it is worth having and costs nothing when it
misses.
"""
import argparse
import base64
import io
import json
import os
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.atr_tool import TOOL                            # noqa: E402

pymupdf.TOOLS.mupdf_display_errors(False)

MAX_DIM = 1568
MAX_TOKENS = 32000
BYTE_BUDGET = 170 * 1024 * 1024        # well under the 256MB API limit
MODELS = {"haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-5"}
PRICES = {"haiku": (1.0, 5.0), "sonnet": (3.0, 15.0)}

ASK = ("Transcribe the annual municipal election in this document. The "
       "filename says {stem}, which is a hypothesis about the town and the "
       "year, not evidence -- read both off the page.")


def render(path):
    blocks = []
    for page in pymupdf.open(path):
        scale = MAX_DIM / max(page.rect.width, page.rect.height)
        png = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale)).tobytes("png")
        blocks.append({"type": "image",
                       "source": {"type": "base64", "media_type": "image/png",
                                  "data": base64.b64encode(png).decode()}})
    return blocks


def request_for(stem, path, spec, model):
    blocks = render(path)
    blocks.append({"type": "text", "text": ASK.format(stem=stem)})
    return {"custom_id": stem,
            "params": {"model": model, "max_tokens": MAX_TOKENS,
                       "system": [{"type": "text", "text": spec,
                                   "cache_control": {"type": "ephemeral"}}],
                       "tools": [TOOL],
                       "tool_choice": {"type": "tool", "name": "emit_return"},
                       "messages": [{"role": "user", "content": blocks}]}}



def already_in_flight(client, stems, hours=48):
    """(blocking_reason, overlapping_stems) -- ask the ACCOUNT, not our state.

    Our state file records what THIS run submitted. It cannot record what a run
    whose state file was lost, or written elsewhere, submitted -- and that is
    exactly the case that duplicated a whole corpus. The account is what gets
    billed, so the account is what gets asked.
    """
    import datetime
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(hours=hours))
    want = set(stems)
    overlap, live = set(), []
    for b in client.messages.batches.list(limit=100):
        if b.created_at < cutoff:
            continue
        if b.processing_status != "ended":
            # An in-flight batch will not enumerate its requests, so nothing
            # can prove it is not ours. Treat it as a stop.
            live.append(b.id)
            continue
        try:
            for r in client.messages.batches.results(b.id):
                # Only a SUCCEEDED request is work we hold and have paid for.
                # A cancelled or expired one produced nothing and was not
                # billed, so blocking on it would refuse a legitimate submit
                # -- which it did, on the three requests of a cancelled test
                # batch. The question this guard asks is "are we about to buy
                # this twice", not "has this id ever appeared".
                if r.custom_id in want and r.result.type == "succeeded":
                    overlap.add(r.custom_id)
        except Exception:
            continue
    if overlap:
        return ("%d of these sections were already submitted in the last %dh"
                % (len(overlap), hours)), sorted(overlap)
    if live:
        return ("%d batch(es) are still in flight and cannot be enumerated: %s"
                % (len(live), ", ".join(live[:3]))), []
    return None, []


def load_state(path):
    if os.path.exists(path):
        return json.load(io.open(path, encoding="utf-8"))
    return {"batches": [], "collected": []}


def save_state(path, state):
    io.open(path, "w", encoding="utf-8").write(json.dumps(state, indent=1))


def manifest(path):
    rows = []
    for line in io.open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            stem, pdf = line.split("\t")
            rows.append((stem, pdf))
    return rows


def send(client, reqs, state, args, n):
    mb = len(json.dumps(reqs)) / 1e6
    if args.dry_run:
        print("  [dry] sub-batch %d: %d sections, %.0fMB" % (n, len(reqs), mb))
        return
    batch = client.messages.batches.create(requests=reqs)
    state["batches"].append({"id": batch.id, "model": args.model,
                             "stems": [r["custom_id"] for r in reqs]})
    save_state(args.state, state)              # recorded BEFORE anything else
    print("  sub-batch %d: %d sections, %.0fMB -> %s"
          % (n, len(reqs), mb, batch.id), flush=True)


def cmd_submit(args):
    from anthropic import Anthropic
    client = Anthropic()
    spec = io.open(args.spec, encoding="utf-8").read()
    state = load_state(args.state)
    seen = set(state["collected"])
    for b in state["batches"]:
        seen.update(b["stems"])
    todo = [(s, p) for s, p in manifest(args.manifest) if s not in seen]
    print("%d sections to submit (%d already batched or collected)"
          % (len(todo), len(seen)))
    if todo and not args.dry_run:
        reason, overlap = already_in_flight(client, [s for s, _ in todo])
        if reason:
            print("REFUSING TO SUBMIT: " + reason)
            if overlap:
                print("  e.g. " + ", ".join(overlap[:8]))
            print("  Collect the existing work, or pass --force if you are "
                  "certain it is unrelated.")
            if not args.force:
                return
            print("  --force given; submitting anyway.")
    if args.limit:
        todo = todo[:args.limit]

    pending, size, n_sub = [], 0, 0
    for i, (stem, pdf) in enumerate(todo, 1):
        req = request_for(stem, pdf, spec, MODELS[args.model])
        nbytes = len(json.dumps(req))
        if pending and size + nbytes > BYTE_BUDGET:
            n_sub += 1
            send(client, pending, state, args, n_sub)
            pending, size = [], 0
        pending.append(req)
        size += nbytes
        if i % 25 == 0:
            print("  rendered %d/%d" % (i, len(todo)), flush=True)
    if pending:
        n_sub += 1
        send(client, pending, state, args, n_sub)
    print("submitted %d sub-batches" % n_sub)


def cmd_collect(args):
    from anthropic import Anthropic
    client = Anthropic()
    state = load_state(args.state)
    os.makedirs(args.out, exist_ok=True)
    collected = set(state["collected"])
    spend = {"in": 0, "out": 0, "cw": 0, "cr": 0}
    truncated = []

    for b in state["batches"]:
        info = client.messages.batches.retrieve(b["id"])
        if info.processing_status != "ended":
            print("  %s  %s (%d in flight)"
                  % (b["id"], info.processing_status,
                     info.request_counts.processing))
            continue
        got = 0
        for r in client.messages.batches.results(b["id"]):
            stem = r.custom_id
            if stem in collected:
                continue
            if r.result.type != "succeeded":
                print("    %s: %s" % (stem, r.result.type))
                continue
            msg = r.result.message
            tool = next((x for x in msg.content if x.type == "tool_use"), None)
            io.open(os.path.join(args.out, stem + ".json"), "w",
                    encoding="utf-8").write(json.dumps(
                        {"stem": stem, "model": b["model"],
                         "stop_reason": msg.stop_reason,
                         "output_tokens": msg.usage.output_tokens,
                         "record": dict(tool.input) if tool else None},
                        indent=1, ensure_ascii=False))
            use = msg.usage
            spend["in"] += use.input_tokens
            spend["out"] += use.output_tokens
            spend["cw"] += getattr(use, "cache_creation_input_tokens", 0) or 0
            spend["cr"] += getattr(use, "cache_read_input_tokens", 0) or 0
            collected.add(stem)
            got += 1
            if msg.stop_reason == "max_tokens":
                truncated.append(stem)
        state["collected"] = sorted(collected)
        save_state(args.state, state)          # after every batch, not at the end
        print("  %s  ended, %d collected" % (b["id"], got))

    model = state["batches"][0]["model"] if state["batches"] else args.model
    cin, cout = PRICES[model]
    billed = (spend["in"] * cin + spend["cw"] * cin * 1.25
              + spend["cr"] * cin * 0.10 + spend["out"] * cout) / 1e6 * 0.5
    print("\n%d sections collected. cache read %d tokens. billed $%.2f"
          % (len(collected), spend["cr"], billed))
    if truncated:
        print("TRUNCATED (raise MAX_TOKENS and re-run these): %s"
              % ", ".join(truncated[:20]))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("submit", "collect"):
        q = sub.add_parser(name)
        q.add_argument("--manifest", default="parse_manifest_local.txt")
        q.add_argument("--spec", default="specs/transcription.md")
        q.add_argument("--state", default="atr_run_state.json")
        q.add_argument("--out", default="atr_parsed")
        q.add_argument("--model", default="haiku", choices=sorted(MODELS))
        q.add_argument("--limit", type=int, default=0)
        q.add_argument("--dry-run", action="store_true")
        q.add_argument("--force", action="store_true",
                       help="submit even though the account shows "
                            "overlapping or in-flight work")
    args = ap.parse_args()
    (cmd_submit if args.cmd == "submit" else cmd_collect)(args)


if __name__ == "__main__":
    main()
