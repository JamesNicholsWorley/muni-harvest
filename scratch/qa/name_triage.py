"""Why a name did not ground: is it in the document under a different spelling,
or is it not in the document at all?

The grounding check is exact substring matching on the first two alphabetic
parts of the name.  That fails two very different ways.  The document may print
the name and the reading may have mangled it -- an OCR that turns "Salamone"
into "Salarnone" -- in which case the record is fine and the reading is not.
Or the name may simply not be there, which is the case worth a person's time:
nine of forty ungrounded records were materially FALSE.

This separates them by looking for the best near-match in the text and printing
what sits around it, so the resolution can quote the document rather than assert
about it.  It decides nothing.
"""
import csv, difflib, json, os, re, sys
import qa.layers as L


def parts_of(name):
    return [p for p in re.split(r"[^A-Za-z]+", name) if len(p) > 2]


def best_match(token, tokens, text_words):
    hits = difflib.get_close_matches(token.lower(), text_words, n=1, cutoff=0.75)
    return hits[0] if hits else None


def context(text, needle, width=70):
    m = re.search(re.escape(needle), text, re.I)
    if not m:
        return ""
    return text[max(0, m.start() - width):m.end() + width].strip()


def triage(stem):
    rec = json.load(open(f"data/json/{stem}.json", encoding="utf-8"))
    text, src = L.document_text(stem)
    if text is None:
        return src, []
    words = sorted({w.lower() for w in re.findall(r"[A-Za-z]{3,}", text)})
    out = []
    for e in rec.get("elections") or []:
        for c in e.get("candidates") or []:
            if L.is_tally_row(c):
                continue
            n = L.name_of(c)
            ps = parts_of(n)
            if not n or not ps:
                continue
            if all(re.search(re.escape(p), text, re.I) for p in ps[:2]):
                continue
            miss = [p for p in ps[:2]
                    if not re.search(re.escape(p), text, re.I)]
            near = {p: best_match(p, ps, words) for p in miss}
            anchor = next((p for p in ps if re.search(re.escape(p), text, re.I)), None)
            ctx = context(text, anchor) if anchor else ""
            if not ctx:
                got = [v for v in near.values() if v]
                ctx = context(text, got[0]) if got else ""
            out.append({
                "stem": stem,
                "office": str(e.get("office_original") or e.get("office") or "")[:40],
                "name": n,
                "votes": c.get("votes"),
                "missing": "|".join(miss),
                "near": "|".join(f"{k}->{v}" for k, v in near.items() if v),
                "context": ctx[:200],
            })
    return src, out


if __name__ == "__main__":
    stems = sys.argv[1:]
    if not stems:
        rows = list(csv.DictReader(open("qa/worklist.csv", encoding="utf-8")))
        stems = [r["stem"] for r in rows
                 if r["bucket"].startswith("ungrounded-names")
                 and r["status"] == "open"]
    w = csv.DictWriter(sys.stdout,
                       fieldnames=["stem", "source", "office", "name", "votes",
                                   "missing", "near", "context"])
    w.writeheader()
    for s in stems:
        src, rows = triage(s)
        for r in rows:
            r["source"] = src
            w.writerow(r)
