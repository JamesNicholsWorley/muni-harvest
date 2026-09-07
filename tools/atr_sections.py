"""Cut the election pages out of an Annual Town Report.

Runs one shard of `atr-section-shard.yml`. For each town-year: fetch the report,
find the page that carries the election return, and write those pages -- plus one
either side -- as a small PDF. The report itself is discarded.

## What counts as the election page

A page heads itself an election AND lists the offices a town elects.

The second half of that matters more than it looks. An earlier locator required
ballot vocabulary -- Blanks, Write-ins, Total Votes, Precinct -- and found
nothing at all in Hawley's report, whose election page reads

    Annual Town Election Results: May 5, 2025
    Selectmen/Board of Health - 3 years    Hussain Hamdan
    Assessor - 3 years                     Ed Brady
    ...

nine offices, nine names, and not one figure, because every race was
uncontested. Requiring figures throws away precisely the small-town returns the
ATRs are best at holding. So offices count as evidence, and figures are a bonus
that raises the score.

## Why it scores rather than takes the first match

A town report mentions its election three or four times: the warrant lists the
offices to be elected, the officers directory lists who holds them, and the
minutes reference the date. Those pages match a heading and some offices too.
The results page is the one with the most of both, so every page is scored and
the best wins -- and the runner-up is recorded, because when the top two are
close the choice is worth a human's eye.
"""
import csv
import io
import json
import os
import re
import time

import statistics

import pymupdf
from curl_cffi import requests

HEAD = re.compile(
    r"(ANNUAL\s+TOWN\s+ELECTION|TOWN\s+ELECTION|ANNUAL\s+ELECTION|"
    r"ELECTION\s+RESULTS|RESULTS?\s+OF\s+THE\s+ANNUAL)", re.I)
BALLOT = re.compile(
    r"(TOTAL\s+VOTES|BLANKS?|WRITE[- ]?INS?|BALLOTS\s+CAST|PRECINCT|VOTE\s+FOR)", re.I)
OFFICE = re.compile(
    r"(SELECT\s*(?:MAN|MEN|BOARD)|MODERATOR|ASSESSOR|TOWN\s+CLERK|SCHOOL\s+COMMITTEE|"
    r"LIBRARY\s+TRUSTEE|CONSTABLE|BOARD\s+OF\s+HEALTH|PLANNING\s+BOARD|TREE\s+WARDEN|"
    r"CEMETERY|WATER\s+COMMISSION|FINANCE\s+COMMITTEE|HOUSING\s+AUTHORITY|"
    r"TOWN\s+TREASURER|TAX\s+COLLECTOR)", re.I)

# A page can look like the return and be something else. Two shapes recur:
# the Town Clerk's departmental report, which heads itself an election and then
# writes prose about running one, and a SAMPLE BALLOT, which lists every office
# and every candidate and no result at all. Neither is excluded here -- a real
# results page often reprints the ballot instructions, so the test that catches
# the sample ballot also catches Abington 2014, which IS the return.
#
# So they are measured and recorded, not judged. Fetching 2,900 reports is the
# slow step; triaging a manifest afterwards is free and needs no network. Losing
# a real return to a clever filter would cost a re-fetch.
BALLOT_PAPER = re.compile(
    r"(INSTRUCTIONS\s+TO\s+VOTERS|OFFICIAL\s+BALLOT|SPECIMEN\s+BALLOT|"
    r"fill\s+in\s+the\s+OVAL)", re.I)


def prose_score(text):
    """Mean line length. A results page is a table -- 11 to 17 characters a line.
    The Town Clerk writing about the election runs 34, and a departmental essay
    runs 70. Hawley's uncontested return sits at 26, which is why this is
    recorded rather than used as a cutoff."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return statistics.mean([len(l) for l in lines]) if lines else 0


SHARD = int(os.environ.get("SHARD", "0"))
SHARDS = int(os.environ.get("SHARDS", "1"))
URL_CSV = os.environ.get("URL_CSV", "config/atr_section_urls.csv")
PER_MINUTE = max(1, int(os.environ.get("PER_MINUTE", "20")))
LIMIT = int(os.environ.get("LIMIT", "0"))
OUT = "sections_out"

os.makedirs(os.path.join(OUT, "pdf"), exist_ok=True)


def score_pages(doc):
    """(score, page index, headings, ballot words, offices) best first."""
    out = []
    for i, page in enumerate(doc):
        t = page.get_text()
        h, b, o = (len(HEAD.findall(t)), len(BALLOT.findall(t)),
                   len(OFFICE.findall(t)))
        if h and (b >= 3 or o >= 3):
            out.append((b + 2 * o + 3 * h, i, h, b, o))
    out.sort(reverse=True)
    return out


def main():
    with io.open(URL_CSV, encoding="utf-8", newline="") as fh:
        rows = [r for n, r in enumerate(csv.DictReader(fh)) if n % SHARDS == SHARD]
    if LIMIT:
        rows = rows[:LIMIT]

    manifest = []
    gap = 60.0 / PER_MINUTE
    for row in rows:
        stem = f"{row['municipality'].replace(' ', '')}{row['year']}"
        rec = {"municipality": row["municipality"], "year": row["year"],
               "stem": stem, "url": row["url"], "status": "", "pages": 0,
               "picked": "", "score": 0, "runner_up": 0, "bytes": 0,
               "mean_line": 0, "ballot_paper": "", "detail": ""}
        t0 = time.time()
        try:
            r = requests.get(row["url"], impersonate="chrome", timeout=90)
            body = r.content or b""
            rec["bytes"] = len(body)
            if r.status_code != 200:
                rec["status"] = f"HTTP_{r.status_code}"
            elif not body.startswith(b"%PDF"):
                rec["status"] = "NOT_PDF"
            else:
                doc = pymupdf.open(stream=body, filetype="pdf")
                rec["pages"] = doc.page_count
                scored = score_pages(doc)
                if not scored:
                    # No text layer at all is a different answer from "the text
                    # is there and says nothing about an election".
                    has_text = any(p.get_text().strip() for p in doc)
                    rec["status"] = "NO_SECTION" if has_text else "NEEDS_OCR"
                else:
                    best = scored[0]
                    rec["score"] = best[0]
                    rec["runner_up"] = scored[1][0] if len(scored) > 1 else 0
                    lo = max(0, best[1] - 1)
                    hi = min(doc.page_count - 1, best[1] + 2)
                    cut = pymupdf.open()
                    cut.insert_pdf(doc, from_page=lo, to_page=hi)
                    path = os.path.join(OUT, "pdf", f"{stem}_atr.pdf")
                    cut.save(path, garbage=4, deflate=True)
                    page_text = doc[best[1]].get_text()
                    rec["mean_line"] = round(prose_score(page_text))
                    rec["ballot_paper"] = "yes" if BALLOT_PAPER.search(page_text) else ""
                    rec["picked"] = f"{lo+1}-{hi+1}"
                    rec["status"] = "OK"
                    rec["detail"] = (f"page {best[1]+1}: {best[2]} headings, "
                                     f"{best[3]} ballot words, {best[4]} offices")
        except Exception as e:
            rec["status"] = "ERROR"
            rec["detail"] = f"{type(e).__name__}: {str(e)[:120]}"
        manifest.append(rec)
        print(f"  {rec['status']:<11} {stem:<22} {rec['picked']:<7} {rec['detail'][:60]}",
              flush=True)
        slept = time.time() - t0
        if slept < gap:
            time.sleep(gap - slept)

    with io.open(os.path.join(OUT, f"manifest_{SHARD}.csv"), "w",
                 encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)
    ok = sum(1 for m in manifest if m["status"] == "OK")
    print(f"\nshard {SHARD}: {ok}/{len(manifest)} sections cut")


if __name__ == "__main__":
    main()
