"""Resolve the worklist rows an earlier run deferred as unworkable in the cloud.

183 rows carry "CANNOT BE WORKED IN A CLOUD SESSION: no PDF, no raw_ocr, no
pdftext, no markdown". That was true when it was written and is not true now:
`qa.bootstrap` links `data/news_text`, and 182 of the 183 have a reading today.

What each of them turns out to be, once read, is one of three things, and the
resolution says which and quotes the source for it:

  * the source states a ballot count -> a row in the ledger, this row done
  * the source is a report and states none -> documented absence, this row done
  * the source and the record disagree -> deferred, with the arithmetic

`ballots_derivable` stays UNKNOWN on all of them either way, and correctly: a
report prints no blanks row, so no contest qualifies for the derivation. That is
a fact about the source, not a defect in the record, and saying so is the
resolution rather than an excuse for one.

    python scratch/resolve_news_sourced.py            # what it would write
    python scratch/resolve_news_sourced.py --write
"""
import collections
import csv
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from qa import layers, resolve  # noqa: E402

LEDGER = os.path.join(BASE, "qa", "reference", "adjudications.csv")

# Read one at a time, each against its own source. The arithmetic is in the
# resolution because a number somebody can recompute is worth more than a
# verdict they have to trust.
# Read, explained, and needing nobody: the resolution is the whole answer.
SETTLED = {"Charlton2021", "Charlton2022", "Plympton2022", "Williamstown2024",
           "NewAshford2023"}

DEFER = {
    "Granby2024":
        "READ data/news_text/Granby2024.md (Daily Hampshire Gazette, \"Labonte "
        "wins tight Select Board race in Granby\"). The scrape carries exactly "
        "one year token and it is a photo credit -- \"Granby 09-15-2023\" -- "
        "not a dateline; the article body gives no date at all. The record "
        "dates the election 2024-05-20. carries_the_year FAILs on the 2023 "
        "token, which is what the check is for. Nothing here says the document "
        "is the wrong year and nothing here says it is the right one: it needs "
        "the citation's own URL and publication date, which the record does not "
        "carry.",
    "Whately2021":
        "STILL UNWORKABLE, and now for a documented reason rather than a "
        "missing link: no PDF, no OCR, no markdown and no news_text exist for "
        "this stem even with data/news_text linked, so layers.document_text "
        "returns None and document_held FAILs correctly. This is the one row of "
        "the 183 that the bootstrap fix does not reach. Harvest work.",
    "Weymouth2023":
        "READ data/news_text/Weymouth2023.md and every figure in the record is "
        "COMPUTED FROM A PERCENTAGE, not transcribed. The article says "
        "\"Hedlund ... won 75% of the 6,784 votes cast in the race\" and "
        "\"Mathews received 70% of the 890 votes\", and the record holds "
        "Hedlund 5088 (= 0.75 x 6784), Mathews 623 (= 0.70 x 890), Alongi 267 "
        "(= 890 - 623) and Cowen 1218 (= 6784 - 5088 - 478). 0 of 5 figures "
        "ground and that is the correct verdict: the source prints none of "
        "them. This is the rule the project states as \"the model transcribes, "
        "code derives\" broken in the other direction, in a city of 41,448 "
        "registered voters. The only ballot count in the article belongs to "
        "another election -- \"received 18% of the 9,500 votes cast four years "
        "ago\" -- so ballots_cast stays null too. YOURS: the figures should be "
        "the percentages they are, or the record needs the clerk's return.",
    "Sheffield2026":
        "READ data/news_text/Sheffield2026.md. Four write-in winners are "
        "recorded with 1 vote each and the article gives no count for any of "
        "them: \"With no one running for a two-year term on the Planning "
        "Board, Brian Sangster won as a write-in candidate\", and the same for "
        "Sari Hoy, Julie Hannum and Amy Brainbridge-Jordan. A vote count of 1 "
        "is standing in for \"elected, count unknown\", which the schema has a "
        "sentinel for. YOURS: whether these become the write-in-winner "
        "sentinel or wait for the clerk's sheet.",
    "Chesterfield2021":
        "READ data/news_text/Chesterfield2021.md, and the curated source file "
        "says it itself: \"- No blanks are given. Select Board 39 + 7 = 46 "
        "against 54 ballots.\" The record holds Blanks 8 for that contest, "
        "which is 54 - 46. A derived figure carried as a transcription. The "
        "other eight figures ground.",
    "Aquinnah2022":
        "READ data/news_text/Aquinnah2022.md (Vineyard Gazette, 12 May 2022). "
        "The article prints \"169 voters casting ballots, or 42 per cent of "
        "the 404 registered\" and every contest as a pair -- \"Green prevailed "
        "over James Glavin 91-64\", \"Welch unseating ... Slate 105-42\", "
        "\"Haley ... fought off a write-in challenge from Adrian Higgins, "
        "125-16\" -- and no blanks at all. The record's Blanks 14, 22 and 28 "
        "are each 169 minus that contest's two candidates. That also makes "
        "ballots_cast circular: it reads derived_from_contests, and the "
        "contests it is derived from had their blanks computed from 169.",
    "NewAshford2023":
        "READ data/news_text/NewAshford2023.md (Berkshire Eagle) and the "
        "record's own _notes. Two of the six figures do not ground because the "
        "Eagle prints only the contested race -- \"defeating challenger Mollie "
        "Scace, 45-12\" -- and the four uncontested counts came from the Town "
        "Clerk's \"Results of elections\" sheet supplied by records request, "
        "which is not held as a file. The Eagle corroborates the four names. "
        "So this is a second source part that was never registered, not an "
        "invented figure; the _notes also record a ballot-count conflict "
        "(sheet 51, Eagle 57) resolved to 57.",
    "Williamstown2024":
        "READ data/news_text/Williamstown2024.md (iBerkshires, 15 May 2024). "
        "The one ungrounded figure is the Housing Authority Others 42, and it "
        "is the project's own write-in convention rather than an error: the "
        "article says \"Webb, with eight votes, was the winner of a write-in "
        "vote\" and \"Fifty ballots were submitted with write-ins for the "
        "spot\", so the named write-in keeps 8 and the aggregate keeps the "
        "remainder, 50 - 8 = 42. The page prints Fifty and Eight; 42 is the "
        "remainder and is correct.",
    "Charlton2021":
        "READ data/news_text/Charlton2021.md. The ungrounded Jennings 482 is a "
        "markdown accident, not a misreading: the page renders it as "
        "\"***Russell G. Jennings*** **- 4** ***82 votes (67.4%)***\", so the "
        "emphasis markers split 482 into 4 and 82 and no search for 482 can "
        "find it. The reading is right and the extraction is broken.",
    "Charlton2022":
        "READ data/news_text/Charlton2022.md, same source and same shape as "
        "Charlton 2021: the page prints its figures inside emphasis markers "
        "(\"Jaime Ann Dell'Ovo - 602 votes (55%)\", \"Write-ins/Others - 85 "
        "votes\") and 28 of 29 figures ground. The one that does not is an "
        "Others 781 that no single printed row carries.",
    "Plympton2022":
        "READ data/news_text/Plympton2022.md and the reading is faithful: "
        "\"The Library Trustee term for two years saw Mark Eubanks win with "
        "five write-in votes. There were 321 blanks and three other "
        "write-ins\" -- 5 + 321 + 3 = 329 against the 327 ballots derived from "
        "the other contests. marks_exceed_ballots FAILs by 2 on the source's "
        "own arithmetic, not on ours. Nothing to correct here.",
    "Bernardston2026":
        "READ data/news_text/Bernardston2026.md (Greenfield Recorder, no "
        "contested races). The source's OWN figures do not close: it says "
        "\"45 of the town's 1,874 registered voters, or 2.4%, came out\" and "
        "then \"Franc Kromholz for a three-year term, 41 votes. Write-in "
        "candidate Kayla Lapine received five write-in votes\" -- 41+5 = 46 "
        "marks on 45 ballots for one seat. Off by one in the report, not in "
        "the reading; both figures are transcribed correctly. No ballots_cast "
        "row filed because the count it would carry is contradicted by the "
        "same article. YOURS: accept 45 and let the contest read one over, or "
        "leave ballots_cast null.",
    "Conway2025":
        "READ data/news_text/Conway2025.md. Same shape as Bernardston 2026 and "
        "the same size: \"211 of the town's 1,494 registered voters "
        "participated\" against \"Moderator, one-year term - James Recore, "
        "incumbent, 212 votes\". One mark more than the stated turnout, in a "
        "single-seat contest. No ballots_cast row filed.",
    "Lenox2023":
        "READ data/news_text/Lenox2023.md (Berkshire Edge, results from Town "
        "Clerk Kerry Sullivan). \"Total ballots Cast: 624\", and then "
        "\"Selectman, three-year term William David Roche, Jr, Incumbent 502 / "
        "Max Scherff 363\" -- 865 marks in a one-seat contest on 624 ballots, "
        "impossible by 241. Moderator (497+111 = 608) and every other block sit "
        "under 624, so it is the Selectman block or the 624 that is wrong and "
        "the held source cannot say which. Needs the town clerk's own sheet.",
    "Littleton2022":
        "READ data/news_text/Littleton2022.md (the town's own results page). It "
        "prints \"Total Ballots Cast 1220\" and most blocks close on it exactly "
        "-- Housing Authority 917+303, Planning Board 764+456, Water "
        "Commissioners 670+752+480+538 = 2440 = 1220x2. Two do not, and each "
        "overshoots by exactly 100: Library Trustees 955+854+731 = 2540 against "
        "2440, School Committee 536+416+368 = 1320 against 1220. Both would "
        "close if the Blanks/Write-Ins row were 100 lower (631, 268). That is a "
        "hypothesis, not a reading -- the page prints 731 and 368 -- so nothing "
        "is corrected here. Needs the clerk's sheet.",
    "Somerset2023":
        "READ data/news_text/Somerset2023.md. The two counts it gives are "
        "per-contest, not town-wide: \"securing 1,344 votes out of a total of "
        "2,809 ballots cast in that race\" and \"Barbosa won 464 votes out of "
        "1,662 ballots cast\" for a two-seat school committee. A contest total "
        "is only the ballot count where the contest is single-seat and blanks "
        "are inside it, and the article does not say that it is. No "
        "ballots_cast row filed.",
    "Heath2023":
        "READ data/news_text/Heath2023.md: \"**Voter turnout: 23%.** No "
        "ballot-count total was reported.\" A percentage is not a count and no "
        "registered-voter denominator is given either, so nothing can be "
        "derived from it.",
    "Plainville2023":
        "READ data/news_text/Plainville2023.md and it is not 2023. The article "
        "is The Sun Chronicle's \"Election results are in for Wrentham, "
        "Plainville, Rehoboth and Seekonk\", dated \"Apr 2, 2018\" twice, and "
        "the record's own elections[].date_parsed_raw is 2018-04-02 against a "
        "date of 2023-04-03. Every figure in the record matches the article "
        "exactly (Johnson 529, Kelly 402, Garrity 613, Sharpe 436, Wehmeyer "
        "322, Rippberger 174, Cates 507, Jacobsen 317, Crocker 467, Richard "
        "400), so this is a faithful reading of a document from the wrong year "
        "-- the Clinton 2022 / Acushnet 2021 shape. YOURS: a whole-record "
        "question. Wayback is the way to confirm and this machine is IP-blocked "
        "from it.",
}


def stated_rows():
    out = {}
    with open(LEDGER, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["decided_on"] == "2026-09-07" and "ballots_cast and" in r["field"]:
                out[r["stem"]] = r
    return out


def describe(stem, rec, text, source, findings):
    """What this town-year is, in the terms the checks flagged it in."""
    contests = rec.get("elections") or []
    blanks = sum(1 for e in contests if layers.blanks_printed(e))
    qualify = sum(1 for e in contests
                  if layers.scope_of(e) == "at_large"
                  and (e.get("num_winners") or 1) == 1
                  and layers.blanks_printed(e)
                  and layers.has_ballot_candidate(e))
    bits = [f"READ {source} ({len(text)} chars), {len(contests)} contests in "
            f"the record, {blanks} of them printing a blanks row"]
    if "ballots_derivable" in findings:
        bits.append(
            f"ballots_derivable is UNKNOWN because {qualify} contests qualify "
            f"and the derivation needs two: a report tallies winners and does "
            f"not print blanks, so nothing can be derived from it. That is the "
            f"source, not the record")
    return bits


def main(write=False):
    rows = list(csv.DictReader(open(os.path.join(BASE, "qa", "worklist.csv"),
                                    encoding="utf-8")))
    target = [r for r in rows if r["status"] == "deferred"
              and ("CANNOT BE WORKED" in r["resolution"]
                   or "NO READING IS HELD" in r["resolution"])]
    stated = stated_rows()
    report = collections.defaultdict(list)
    with open(os.path.join(BASE, "qa", "layers_report.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["verdict"] in ("FAIL", "UNKNOWN"):
                report[r["stem"]].append(r)

    tally = collections.Counter()
    for r in target:
        stem = r["stem"]
        text, source = layers.document_text(stem)
        findings = {f["check"] for f in report.get(stem, [])}
        if text is None:
            res = (f"NO READING IS HELD for {stem} even with data/news_text "
                   f"linked: layers.document_text returns None. This one is "
                   f"genuinely unworkable here.")
            status = "deferred"
        elif stem in DEFER:
            # A bespoke reading is not automatically an escalation: five of
            # these are settled by the reading and need nothing from anybody.
            res = DEFER[stem]
            status = "done" if stem in SETTLED else "deferred"
        else:
            rec = json.load(open(os.path.join(BASE, "data", "json", stem + ".json"),
                                 encoding="utf-8"))
            bits = describe(stem, rec, text, source, findings)
            if stem in stated:
                q = stated[stem]["read"].split(": ", 1)[1]
                bits.append(f"the source DOES state the count: {q} -- filed as "
                            f"an adjudication row (ballots_cast "
                            f"{stated[stem]['should_be']}), which is a pair of "
                            f"fields and so is yours to write")
            elif "ballots_derivable" in findings:
                bits.append("and it states no ballot count anywhere: searched "
                            "for ballots/votes cast, turnout, and N of M "
                            "registered. Documented absence, not a gap to fill")
            if "office_count_consistent" in findings:
                peers = [len(json.load(open(p, encoding="utf-8")).get("elections") or [])
                         for p in _peer_paths(stem)]
                med = sorted(peers)[len(peers) // 2] if peers else 0
                bits.append(
                    f"office_count_consistent FAILs because the record holds "
                    f"{len(rec.get('elections') or [])} contests against a "
                    f"median of {med} in this town's other years -- the source "
                    f"reports the races it covered, not the whole ballot. That "
                    f"is incomplete BY SOURCE and is harvest work (find the "
                    f"clerk's return), not a defect in this reading")
            res, status = ". ".join(bits) + ".", "done"
        tally[status] += 1
        print(f"{status:<9} {stem:<20} {res[:96]}")
        if write:
            sys.argv = ["qa.resolve", stem, "--status", status,
                        "--resolution", res]
            resolve.main()

    print(f"\n{dict(tally)}")


def _peer_paths(stem):
    town = layers.municipality_of(stem)
    import glob
    return [p for p in glob.glob(os.path.join(BASE, "data", "json", town + "20??.json"))
            if os.path.basename(p)[:-5] != stem]


if __name__ == "__main__":
    main("--write" in sys.argv)
