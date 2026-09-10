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

## What a heading and some offices are not enough to distinguish

A table of CONTENTS is a heading and a list of offices, and it beat the return
on 89 of the 317 cuts that came back with no election in them at all. Avon
2013's cut is its contents page; the return is on page 50, printed with dot
leaders. Carver 2014's is the index, and nine contests with named candidates
and vote totals were read off it and published.

What separates a return from an index, a warrant and an officers directory is
that a return carries FIGURES against names. So a page that already shows
ballot vocabulary is scored on how many of its lines put a label against a
number, and on whether it heads itself the ANNUAL election rather than the
state one printed a few pages later. Both terms are gated on the ballot
vocabulary being there: ungated, the figures promoted a police department's
statistics table and the word ANNUAL promoted the contents line "Annual Town
Election Results .... 10".
"""
import csv
import io
import json
import os
import re
import subprocess
import time

import statistics

import pymupdf

try:
    from curl_cffi import requests
except ImportError:                                          # pragma: no cover
    requests = None


class _Response(object):
    def __init__(self, status_code, content):
        self.status_code, self.content = status_code, content


def fetch(url, timeout=90):
    """The report's bytes, by whichever client can reach the host.

    `curl_cffi` impersonates a browser's TLS fingerprint, which is what gets
    past a municipal WAF and is why it is tried first. It cannot be the only
    client: behind a TLS-terminating proxy the impersonated handshake is the
    thing that fails, and every fetch dies with an SSLError while plain `curl`
    on the same machine returns 200. Archive hosts do not need the
    impersonation, so falling back costs nothing where it is not needed.
    """
    if requests is not None:
        try:
            r = requests.get(url, impersonate="chrome", timeout=timeout)
            return _Response(r.status_code, r.content or b"")
        except Exception:
            pass
    out = subprocess.run(
        ["curl", "-sSL", "--max-time", str(timeout), "-w", "%{http_code}",
         "-o", "/dev/stdout", url], capture_output=True, timeout=timeout + 30)
    body = out.stdout or b""
    code, body = (int(body[-3:] or 0), body[:-3]) if len(body) >= 3 else (0, b"")
    return _Response(code, body)

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
OCR = os.environ.get("OCR", "") == "1"
OUT = "sections_out"

os.makedirs(os.path.join(OUT, "pdf"), exist_ok=True)


def page_texts(doc):
    """Text for every page, read or OCR'd.

    515 of the reports carry no text layer at all -- they are scans, and the
    locator was blind to them. Reading them costs an OCR pass over every page,
    because the election section can be on page 7 or page 261 and nothing but
    the words says which.

    150 dpi rather than 300: the question here is only "which page is this",
    which survives a coarse read. The page that gets cut is the ORIGINAL, at
    full resolution, so nothing downstream inherits this OCR.
    """
    if not OCR:
        return [p.get_text() for p in doc]
    out = []
    for i, page in enumerate(doc):
        t = page.get_text()
        if t.strip():
            out.append(t)
            continue
        pix = page.get_pixmap(matrix=pymupdf.Matrix(150 / 72, 150 / 72))
        png = os.path.join(OUT, f"_p{i}.png")
        pix.save(png)
        try:
            r = subprocess.run(["tesseract", png, "stdout", "-l", "eng", "--psm", "6"],
                               capture_output=True, text=True, timeout=120)
            out.append(r.stdout or "")
        except Exception:
            out.append("")
        finally:
            if os.path.exists(png):
                os.remove(png)
    return out


# 14 pages holds every ordinary return. It bound on 65 of 1,333 cuts -- Plymouth,
# Bedford, Chatham -- all towns whose returns run over a dozen precincts, and all
# of them were therefore still truncated. So it is settable, and a run that hits
# it says so in the manifest rather than trimming quietly.
MAX_SECTION = int(os.environ.get("MAX_SECTION", "14"))


# A results page is a table of tallies. A page of Town Meeting minutes is prose.
# Both are full of the words SELECTMEN, MODERATOR, ASSESSOR and FINANCE
# COMMITTEE -- the minutes are minutes ABOUT those offices -- which is why
# vocabulary alone cannot separate them, and why raising MAX_SECTION to 40
# returned North Reading 2018 as 42 pages that were mostly the June town meeting.
#
# Shape separates them where vocabulary cannot. A tally page runs 5 to 17
# characters a line; the minutes run 47 to 69.
MAX_CONTINUATION_LINE = 30

# But a return is not always contiguous. Plymouth 2011 heads its return on one
# page, prints the warrant and a ballot question on the next two, and then runs
# eleven pages of precinct tallies. Stopping at the first non-tally page throws
# all eleven away -- the same truncation this window exists to prevent, arrived
# at from the other direction. So a short prose gap is stepped over and a long
# one ends the section.
MAX_GAP = 2


def is_tally(text):
    """A page of the return proper: ballot vocabulary, laid out as a table.

    Stricter than the test that FINDS the section, which counts offices as
    evidence so that Hawley's all-uncontested return -- nine offices, nine
    names, no figures -- is not thrown away. That leniency is right for one
    page and wrong for continuation: an officers directory and a salary
    schedule are both office vocabulary in a table, and neither is a return.
    """
    return (len(BALLOT.findall(text)) >= 3
            and prose_score(text) < MAX_CONTINUATION_LINE)


def grow(texts, best, page_count):
    """Widen the window until the return stops, rather than assuming its length.

    A fixed four-page cut truncated 708 of 1,336 sections -- 52%. Chatham 2020
    was cut at pages 130-133 of 138 and its last cut page still carried 61
    ballot words; the return simply ran longer than the window. A town with
    twelve precincts and thirty offices does not fit in four pages, and those
    are the biggest towns, so the loss was concentrated where it mattered most.

    So the window grows while the pages keep tallying, steps over a gap of up to
    MAX_GAP, and stops when the tallies stop. `MAX_SECTION` is a guard against a
    report whose every page trips the test, not an expectation -- if it is hit,
    that is worth seeing in the manifest rather than silently truncating again.

    Measured over the 1,333 text-layer cuts, requiring a tabular tally rather
    than any election vocabulary removes 33% of the pages -- 8,558 to 5,437 --
    and every page it removes is a warrant, a salary schedule or a set of town
    meeting minutes.
    """
    lo = hi = best
    j = hi + 1
    while j < page_count and j - hi <= MAX_GAP + 1 and (j - lo) < MAX_SECTION:
        if is_tally(texts[j]):
            hi = j
        j += 1
    j = lo - 1
    while j >= 0 and lo - j <= MAX_GAP + 1 and best - lo < 3:
        if is_tally(texts[j]):
            lo = j
        j -= 1
    # One page either side, for the run-up that names the election and the
    # run-out that carries a stray final total. Cheap, and the alternative is
    # the truncation this function exists to fix.
    capped = (hi + 1) - lo >= MAX_SECTION
    return max(0, lo - 1), min(page_count - 1, hi + 1), capped


# A line that puts a label against a figure: the shape of a tally and of
# nothing else in a town report. Two spellings, because a clerk has two.
#
#     Robert A. Ogilvie, 28 Butler Ave ............................302
#     Blanks                                                        91
#
# The first is why this exists. Avon 2013 prints its whole return with dot
# leaders, and the locator took the report's TABLE OF CONTENTS instead --
# which is the same shape of failure that hid Topsfield's entire run for
# twelve years, and the same one that put Carver 2014's index page into the
# published corpus with nine invented contests read off it.
TALLY = (
    re.compile(r"^\s*[A-Za-z][^\n]{2,70}?[\.… ]{2,}(\d{1,3}(?:,\d{3})*|\d{1,5})\s*$", re.M),
    re.compile(r"^[^\d\n]{4,60}?\s(\d{1,3}(?:,\d{3})*|\d{1,5})\s*$", re.M),
)

# A report prints its own election, the state election and a primary, and the
# locator scores all three alike -- which is how four state elections came to
# be published in annual town-year slots. The town's own return usually says
# so in its heading.
ANNUAL = re.compile(r"ANNUAL\s+(TOWN|MUNICIPAL|CITY)\s+ELECTION|ANNUAL\s+ELECTION|"
                    r"RESULTS?\s+OF\s+THE\s+ANNUAL", re.I)


def score_pages(doc, texts=None):
    """(score, page index, headings, ballot words, offices) best first.

    Figures and the word ANNUAL only count where the page also carries ballot
    vocabulary. Without that guard the tally term promoted a police
    department's three-year statistics table over Boxborough 2015's return,
    and the word ANNUAL promoted the contents line "Annual Town Election
    Results .... 10" over the election itself.

    The office term is deliberately NOT capped. Capping it looked like the way
    to stop a contents page winning on office vocabulary alone, and it moved
    Mashpee 2014 off its return, because a real return names more offices than
    an index does. What separates them is that one carries figures.
    """
    out = []
    for i, t in enumerate(texts if texts is not None else [p.get_text() for p in doc]):
        h, b, o = (len(HEAD.findall(t)), len(BALLOT.findall(t)),
                   len(OFFICE.findall(t)))
        if not (h and (b >= 3 or o >= 3)):
            continue
        bonus = 0
        if b >= 3:
            tally = sum(len(rx.findall(t)) for rx in TALLY)
            bonus = 2 * min(tally, 20) + (8 if ANNUAL.search(t) else 0)
        out.append((b + 2 * o + 3 * h + bonus, i, h, b, o))
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
               "mean_line": 0, "ballot_paper": "", "capped": "", "detail": ""}
        t0 = time.time()
        try:
            r = fetch(row["url"])
            body = r.content or b""
            rec["bytes"] = len(body)
            if r.status_code != 200:
                rec["status"] = f"HTTP_{r.status_code}"
            elif not body.startswith(b"%PDF"):
                rec["status"] = "NOT_PDF"
            else:
                doc = pymupdf.open(stream=body, filetype="pdf")
                rec["pages"] = doc.page_count
                texts = page_texts(doc)
                scored = score_pages(doc, texts)
                if not scored:
                    # No text layer at all is a different answer from "the text
                    # is there and says nothing about an election".
                    has_text = any(t.strip() for t in texts)
                    rec["status"] = "NO_SECTION" if has_text else "NEEDS_OCR"
                else:
                    best = scored[0]
                    rec["score"] = best[0]
                    rec["runner_up"] = scored[1][0] if len(scored) > 1 else 0
                    lo, hi, capped = grow(texts, best[1], doc.page_count)
                    rec["capped"] = "yes" if capped else ""
                    cut = pymupdf.open()
                    cut.insert_pdf(doc, from_page=lo, to_page=hi)
                    path = os.path.join(OUT, "pdf", f"{stem}_atr.pdf")
                    cut.save(path, garbage=4, deflate=True)
                    page_text = texts[best[1]]
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
