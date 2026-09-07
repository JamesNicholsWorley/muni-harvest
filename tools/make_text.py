"""Turn a cut ATR section into the text a parser should see -- or decide it cannot.

Two readers disagree in different ways and neither is trusted alone.

`zones` cuts the page at full-height gutters and reads each zone's rows. It is
free and instant, it is exact when it works, and it produces nothing at all on
pages whose columns have no clean gutter.

`docling` runs a layout model and recovers structure geometry cannot see. It
wins more often -- 6 sections to 0 over a head-to-head -- but it fuses adjacent
cells when a table is dense: on Danvers 2020 it merged a candidate's row with
BLANKS and returned a total that does not match her own precincts, which zoning
got exactly right.

So a row is sent as text only when both readers agree on it. Agreement between
two readers that fail differently is worth far more than either reader's
confidence in itself, and where they disagree the page goes to the model as an
image, which is what we would have done anyway. The cost of the gate is zero.

Output per section: a .txt of agreed rows, and a .json saying which rows agreed,
which did not, and what the document's own arithmetic says about them.
"""
import io
import json
import os
import re
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import text_arith, zones                      # noqa: E402

pymupdf.TOOLS.mupdf_display_errors(False)

NUM = re.compile(r"^[0-9]{1,7}$")
AGREE_MIN = 0.60            # share of rows two readers must agree on


def _collapse(nums):
    """Drop runs of the same figure repeated back to back.

    Not a tolerance -- a fact about how the readers differ. Docling emits a
    table's merged total column once per spanned cell, so Danvers 2020's
    `732 * 732 *` arrives as (732, 732) where zoning gives (732,). Comparing
    those raw scored the two readers as disagreeing on 99% of rows they had
    both read correctly. Genuine repeats inside a return -- two precincts
    casting the same count -- are lost to this, which costs a little agreement
    and never manufactures any.
    """
    out = []
    for n in nums:
        if not out or out[-1] != n:
            out.append(n)
    return tuple(out)


def row_name(line):
    """The letters of a row's non-numeric text, upper-cased.

    One reader keeps a comma or a period the other drops; that is not a
    disagreement about the return.
    """
    toks = line.split()
    return "".join(c for c in " ".join(
        t for t in toks if not NUM.match(t)) if c.isalpha()).upper()


def row_nums(line):
    return _collapse([int(t) for t in line.split() if NUM.match(t)])


def row_key(line):
    return row_name(line), row_nums(line)


def docling_rows(path):
    """Docling's tables as flat rows, or None when docling is unavailable."""
    try:
        from docling.document_converter import DocumentConverter
    except Exception:
        return None
    try:
        res = DocumentConverter().convert(path)
    except Exception:
        return None
    out = []
    for tb in res.document.tables:
        try:
            df = tb.export_to_dataframe(doc=res.document)
        except Exception:
            continue
        for _, row in df.iterrows():
            cells = [str(c).strip() for c in row.tolist()
                     if str(c).strip() and str(c).strip() != "nan"]
            if cells:
                out.append(" ".join(cells))
    return out


def zone_rows(path):
    """Zoning's rows, and whether the document has a text layer to zone at all.

    A scan has none. Zoning returns nothing, docling OCRs the page and returns
    plenty, and the agreement score reads 0% -- which is true and misleading:
    the readers did not disagree, one of them was never able to look. Saying so
    matters because "two readers disagreed" and "only one reader could read
    this" call for different work, and a scan reading 0% forever would look
    like a gate that is failing rather than a gate correctly declining to
    guess.
    """
    doc = pymupdf.open(path)
    out = []
    has_text = False
    for page in doc:
        if page.get_text().strip():
            has_text = True
        text, _, _ = zones.best_text(page)
        out.extend(l for l in text.splitlines() if l.strip())
    return out, has_text


def reconcile(path):
    z, has_text = zone_rows(path)
    if not has_text:
        # Only one reader can see this document, so nothing can corroborate it.
        # It goes to the model as an image, which for a scan is the right
        # answer anyway: the image IS the document.
        return {"verdict": "image", "reason": "scanned -- no text layer, so "
                "only one reader is available and nothing can corroborate it",
                "agreed": [], "n_zone": 0, "n_docling": 0}
    d = docling_rows(path)
    zmap = {}
    for line in z:
        k = row_key(line)
        if k[0] and k[1]:
            zmap.setdefault(k, line)
    if d is None:
        return {"verdict": "image", "reason": "docling unavailable",
                "agreed": [], "n_zone": len(zmap), "n_docling": 0}
    dmap = {}
    for line in d:
        k = row_key(line)
        if k[0] and k[1]:
            dmap.setdefault(k, line)
    if not zmap and not dmap:
        return {"verdict": "image", "reason": "neither reader found rows",
                "agreed": [], "n_zone": 0, "n_docling": 0}
    # Agreement is judged per NAME. Two readers that both found Fraizer and
    # both read her eight precincts agree about her, whether or not one of
    # them also repeated the total column.
    both = {k for k in zmap if k in dmap}
    zn = {k[0] for k in zmap}
    dn = {k[0] for k in dmap}
    union = {k for k in zmap if k[0] in dn} | {k for k in dmap if k[0] in zn} or (
        set(zmap) | set(dmap))
    share = len(both) / len(union) if union else 0.0
    agreed = [zmap[k] for k in sorted(both, key=lambda k: z.index(zmap[k]))]
    # Of the rows both readers produced, how many does the document's own
    # arithmetic confirm? A row two readers agree on AND that closes against
    # its printed total is about as settled as an unparsed figure gets.
    closes = 0
    for _, nums in both:
        if len(nums) >= 4 and nums[-1] and text_arith.closes(list(nums[:-1]), nums[-1]):
            closes += 1
    verdict = "text" if share >= AGREE_MIN and len(both) >= 4 else "image"
    return {"verdict": verdict,
            "reason": f"readers agree on {share:.0%} of rows ({len(both)}/{len(union)})",
            "agreed": agreed, "n_zone": len(zmap), "n_docling": len(dmap),
            "agreed_rows": len(both), "rows_closing": closes}


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    shard = int(os.environ.get("SHARD", "0"))
    shards = int(os.environ.get("SHARDS", "1"))
    paths = sorted(p for p in os.listdir(src) if p.endswith("_atr.pdf"))
    paths = [p for i, p in enumerate(paths) if i % shards == shard]
    index = []
    for name in paths:
        stem = name[:-8]
        r = reconcile(os.path.join(src, name))
        if r["verdict"] == "text":
            io.open(os.path.join(out, f"{stem}.txt"), "w",
                    encoding="utf-8").write("\n".join(r["agreed"]))
        index.append({"stem": stem, **{k: v for k, v in r.items() if k != "agreed"}})
        print(f"  {r['verdict']:<6} {stem:<22} {r['reason']}", flush=True)
    io.open(os.path.join(out, f"index_{shard}.json"), "w",
            encoding="utf-8").write(json.dumps(index, indent=1))
    n = sum(1 for r in index if r["verdict"] == "text")
    print(f"\nshard {shard}: {n}/{len(index)} sections can go as text")


if __name__ == "__main__":
    main()
