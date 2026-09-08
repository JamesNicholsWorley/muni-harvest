"""Read the pilot batches back and answer the three open questions.

Cost is reported from the usage the API actually returned, not from the model
that produced the estimate, because the point of a pilot is to find out where
the estimate was wrong rather than to confirm it.
"""
import io
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qa import escalate                                     # noqa: E402

PRICES = {"haiku": (1.0, 5.0), "sonnet": (3.0, 15.0)}
CORPUS_SECTIONS = 1088


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "pilot_out"
    from anthropic import Anthropic
    client = Anthropic()
    summary = {}

    for key in ("haiku", "sonnet"):
        p = os.path.join(out, f"batch_{key}.txt")
        if not os.path.exists(p):
            continue
        bid = io.open(p).read().strip()
        rows, parsed = [], {}
        for r in client.messages.batches.results(bid):
            stem = r.custom_id.split("--", 1)[1]
            if r.result.type != "succeeded":
                rows.append({"stem": stem, "error": r.result.type})
                continue
            m = r.result.message
            u = m.usage
            tool = next((b for b in m.content if b.type == "tool_use"), None)
            parsed[stem] = dict(tool.input) if tool else None
            rows.append({
                "stem": stem,
                "in": u.input_tokens,
                "out": u.output_tokens,
                "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
                "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
                "contests": len(parsed[stem].get("elections", [])) if parsed[stem] else 0,
            })
        io.open(os.path.join(out, f"parsed_{key}.json"), "w",
                encoding="utf-8").write(json.dumps(parsed, indent=1))
        summary[key] = rows

    for key, rows in summary.items():
        ok = [r for r in rows if "error" not in r]
        if not ok:
            print(f"{key}: no successful results")
            continue
        tin = sum(r["in"] + r["cache_write"] + r["cache_read"] for r in ok)
        tout = sum(r["out"] for r in ok)
        cw = sum(r["cache_write"] for r in ok)
        cr = sum(r["cache_read"] for r in ok)
        ci, co = PRICES[key]
        # Batch is half price; cache writes cost 1.25x and reads 0.1x.
        billed = (sum(r["in"] for r in ok) * ci
                  + cw * ci * 1.25 + cr * ci * 0.10
                  + tout * co) / 1e6 * 0.5
        outs = [r["out"] for r in ok]
        print(f"\n===== {key.upper()}  {len(ok)}/{len(rows)} succeeded")
        print(f"  input {tin/1e3:,.0f}k   output {tout/1e3:,.0f}k")
        print(f"  output per section: mean {statistics.mean(outs):,.0f}, "
              f"median {statistics.median(outs):,.0f}, max {max(outs):,}  "
              f"(estimate was 1,400)")
        print(f"  cache: {cw:,} written, {cr:,} read  -- "
              + ("CACHING FIRED IN BATCH" if cr else "no cache hits"))
        print(f"  billed ${billed:.2f} for {len(ok)} sections")
        print(f"  -> {CORPUS_SECTIONS:,} sections extrapolates to "
              f"${billed/len(ok)*CORPUS_SECTIONS:,.0f}")

    # Escalation rate: what would the cheap pass hand to the strong one?
    for key in summary:
        p = os.path.join(out, f"parsed_{key}.json")
        if not os.path.exists(p):
            continue
        parsed = json.load(io.open(p, encoding="utf-8"))
        esc = []
        for stem, rec in parsed.items():
            if not rec:
                esc.append((stem, ["no tool output"]))
                continue
            verdict, reasons = escalate.review(rec)
            if verdict == "escalate":
                esc.append((stem, reasons))
        print(f"\n{key}: {len(esc)}/{len(parsed)} would escalate "
              f"({len(esc)*100//max(len(parsed),1)}%)")
        for stem, why in esc[:6]:
            print(f"   {stem:<20} {why[0][:76]}")


if __name__ == "__main__":
    main()
