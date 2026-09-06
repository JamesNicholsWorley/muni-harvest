"""Turn a confirmed name mismatch into an adjudication row that quotes the line.

Only for records whose PDF has a real text layer: pdftotext reads the bytes the
document itself carries, so where it prints "JOSPEH J. MAGNANI, JR." that IS the
document's spelling -- verified once against the rendered page for Ashland2025,
where the clerk's typo is plainly on the sheet.  The record normalised it, which
is what name_original must never do: grounding matches against the transcription,
so a tidied name is a name no check can find.

Writes nothing.  Prints the rows for inspection.
"""
import csv, difflib, hashlib, json, os, re, sys
import qa.layers as L


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def line_with(text, token):
    for line in text.splitlines():
        if re.search(re.escape(token), line, re.I):
            return re.sub(r"\s{2,}", "  ", line.strip())[:300]
    return ""


def rows_for(stem):
    rec = json.load(open(f"data/json/{stem}.json", encoding="utf-8"))
    pt = open(f"data/pdftext/{stem}.txt", encoding="utf-8", errors="replace").read()
    text, _ = L.document_text(stem)
    pdf = f"data/pdfs/{stem}.pdf"
    words = sorted({w.lower() for w in re.findall(r"[A-Za-z]{3,}", pt)})
    out = []
    for i, e in enumerate(rec.get("elections") or []):
        for j, c in enumerate(e.get("candidates") or []):
            if L.is_tally_row(c):
                continue
            n = L.name_of(c)
            ps = [p for p in re.split(r"[^A-Za-z]+", n) if len(p) > 2]
            if not ps or all(re.search(re.escape(p), text, re.I) for p in ps[:2]):
                continue
            miss = [p for p in ps[:2] if not re.search(re.escape(p), text, re.I)]
            fixes = {}
            for p in miss:
                hit = difflib.get_close_matches(p.lower(), words, n=1, cutoff=0.75)
                if hit:
                    fixes[p] = hit[0]
            if len(fixes) != len(miss):
                continue
            quote = line_with(pt, list(fixes.values())[0])
            if not quote:
                continue
            printed = n
            for a, b in fixes.items():
                # keep the document's letters, keep the record's case pattern
                printed = re.sub(re.escape(a), b.upper() if a.isupper() else b.title(),
                                 printed)
            out.append({
                "stem": stem,
                "source_sha256": sha256(pdf) if os.path.exists(pdf) else "",
                "field": f"elections[{i}].candidates[{j}].name_original  "
                         f"({str(e.get('office_original') or e.get('office') or '')[:40]})",
                "was": n,
                "should_be": printed,
                "read": f'The PDF\'s own text layer prints: "{quote}"',
                "why": "name_original is the transcription and grounding matches "
                       "against it, so it has to carry the document's spelling, "
                       "misprint and all; the canonical form is derived by a later "
                       "pass that never sees the document. The record holds the "
                       "tidied spelling, so the name grounds nowhere. Read from "
                       "data/pdftext, which is pdftotext over the PDF's embedded "
                       "text -- not an OCR, so it is what the file itself carries. "
                       "Verified once against the rendered page (Ashland2025, where "
                       "the sheet plainly reads JOSPEH J. MAGNANI, JR.).",
                "status": "proposed",
                "decided_by": "civicatlas-qa (unattended run)",
                "decided_on": "2026-09-06",
            })
    return out


if __name__ == "__main__":
    w = csv.DictWriter(sys.stdout,
                       fieldnames=["stem", "source_sha256", "field", "was",
                                   "should_be", "read", "why", "status",
                                   "decided_by", "decided_on"])
    w.writeheader()
    for s in sys.argv[1:]:
        for r in rows_for(s):
            w.writerow(r)
