---
name: civicatlas-qa-tail-close
description: CivicAtlasMA QA tail closed 2026-08-13; C5 partition + B4 absence_testable bugs fixed, city seat counts applied, Acushnet repointed; real open work is 54 not 175 (wildcard-office trap); blind-prompt rule for vision reads
metadata:
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

State of the CivicAtlasMA QA sweep as of **2026-08-13**, after the apply pass.
Adjudications: 490 rows in `qa/reference/adjudications.csv`; **343 PROVEN**, 131 vision-read,
13 cite-no-span, and exactly **3 failures** (A5 OakBluffs2025, A5 Shutesbury2023, B4 Holbrook2022).
That 3 is the baseline to hold -- any new failure means a needle regressed.

**SUPERSEDED 2026-08-17: the baseline is now 1, and the verifier has more categories.**
501 rows; 349 PROVEN, 132 no-text-layer, 13 cite-no-span, 3 ocr-only-unconfirmed,
3 superseded, **1 failure (B4 Holbrook2022)**. OakBluffs2025 and Stow2025 left the failure
list because their documents were REPLACED, which is now detected rather than mistaken for a
false quote -- see [[civicatlas-doc-fingerprints]]. Shutesbury2023 left it because its A5
evidence was a PARAPHRASE (`'sample ballot' phrase matched in source text`) of a document that
prints `SAMPLE` on its own line and never the two words together; corrected to verbatim spans.
**Check for paraphrase before assuming a failing quote means a wrong finding.**

## THE BLIND-PROMPT RULE (the most transferable thing learned here)
`build_vision_packets.py` puts `What our record currently says: <finding message>` in every
prompt -- including our arithmetic, e.g. "implies 472 ballots vs town consensus 443". **Handing a
model the number it must explain makes it produce whichever figure reconciles.** Marblehead2025
proved it: the anchored read invented a candidate (Gregory W. Burt) into a race we store under a
different name and called it a one-digit fix. Re-asked BLIND -- no stored figure, no hint of a
dispute, plus an explicit "say NOT PRESENT" escape -- the same model on the same page volunteered
that no candidate named Ryan appears anywhere, the disconfirming fact the anchored prompt had
suppressed. Use `qa/add_reread_tasks.py` as the template. Always give an escape hatch; a model with
no way to say "not here" will find something.

## Applied this session (all with backups, all assert-old-value-before-write)
- `qa/apply_sweep_edits.py` -- 16 edits: 7 blanks/others corrections, 1 num_winners, 1 duplicate-row
  drop (Westfield2021 Kaminsky), 7 date fixes. Refuses any edit whose stated old value is absent.
- `qa/apply_marblehead_p7.py` -- Marblehead2025's sideways page 7 was a whole-page re-parse failure,
  not a digit: wrong heading (Meter vs Water & Sewer), wrong candidates (Mains/Ryan vs Maher/Burt),
  wrong figures. Corrected values close exactly: 4215+5+2401=6621 and 3977+3219+7+6039=2x6621.
- `qa/apply_sweep_edits2.py` -- Granville2024 Blanks 30->80; Montgomery2023 num_winners 2->1 on both
  School Committee positions (heading reads "2 POSITIONS AVAILABLE ... Vote For ONE").
- `qa/fix_turnout.py`, `qa/mark_bad_sources.py` -- see below.
- `civicqa/cli.py` now rebuilds **coverage.html** as well as spot_fixes.html on every full run.

## data/turnout.csv had a silent corpus-level defect
**55 town-years stored the REGISTERED-VOTER ROLL in `total_votes_cast`** (Becket2021 1691 where 102
voted; Brookline2026 42866). Identified deterministically, not by ratio: compared against the
MMA `Registered Voters` column in `qa/reference/mma_election_dates.csv`, within 15%. Becket 1691 vs
1692, Boxborough 4036 vs 4030, Belmont 18971 vs 18952. Moved to a new `registered_voters` column and
`total_votes_cast` BLANKED -- deliberately NOT refilled from `votes_recorded_est`, which is derived
from our own parsed JSON; promoting an estimate into a document-authority column is how this class
of error starts. turnout.csv was never linted, which is why QA never saw it.

## Coverage restated 84.7% -> 77.6% (owner-approved)
`mark_bad_sources.py --apply` wrote 106 condemned URLs into `known_bad_url` (which
`logs/_build_batch3.py` and `_build_batch4_links.py` already subtract from finder candidates -- the
mechanism existed, it was just never fed) and demoted 137 rows off `published`. 1507/1941.
Open findings then went 11 -> **124**, which is CORRECT: 106 are F1 firing on records that hold
tallies while their source is condemned. F1 was amended to distinguish that from "uningested
coverage" -- when `known_bad_url` is populated the no_source state is explained, so it now reports
UPGRADE-SOURCE / "needs a replacement document". Those 106 ARE the doc-finding worklist, now
visible in the queue instead of hidden inside "adjudicated".

## The three "linter bugs" -- two were real, the third was a misdiagnosis (2026-08-13)
(a) and (b) were one regex. `_DISTRICT_RE` is now `(?:DISTRICT|WARD|PRECINCT|PCT|DIST)` with
`(?:[0-9]+[A-Z]?|[A-Z][0-9]?)`. **SEAT was far worse than the Charlton note said**: the plural leaked
through the `[A-Z]` branch, so `2 SEATS 3 YEAR` matched SEAT+"S" and **51 town-wide offices across 20
towns** (Pembroke, WestBoylston, Wenham, Shutesbury, Norfolk...) read as districts -- C5 then summed
sibling seats of ONE race as if they partitioned the town. The letter-ward fix makes Holyoke's 23
`Ward 1A`..`7B` districts real. Effect: 3 C5 findings that had been hand-waved ACCEPTED vanished
(Charlton2024, Charlton2026, Holyoke2021); no finding anywhere was lost. Verify diffs corpus-wide
with an old-vs-new regex script before touching this pattern -- reasoning about it is unreliable.

(c) **A2 is NOT buggy and `num_winners=0` is NOT "the outcome".** The prior note asserted that and it
was never tested -- exactly the circular-reasoning failure mode. `num_winners` means vote-for-N
everywhere it is used (C1 does `total % num_winners`, C4 does `total / num_winners`) and STANDARD.md
defines it as "a positive int". Proof: all 11 zero-seat races have a total that is an EXACT multiple
of their own town-year consensus ballots -- ten at 1x, Hubbardston Parks Commission at 2x. Two are
proved from the PDF: Freetown2026 prints "resulting in a tie and therefore a failure to elect" with
Total 608 (its sibling is "(Vote for Two)" at 1216), Shirley2026 prints "No Winner, 2 tied with 5
votes" with TOTAL 315. So the extractor put the OUTCOME in a field that holds the BALLOT.
`qa/apply_seat_counts.py` filled 10 of 11 and refused Pelham2024 (no stable consensus -- its offices
total 163/164/171/180, nothing repeating); A2 went 11 -> 1 open and **zero new findings appeared on
the newly-visible races**, which corroborates the seat counts. Recording "failure to elect" properly
is a schema question, still deferred.

## Weekdays: the concern was mostly unfounded (checked 2026-08-13)
Owner said only the date is needed. Audited all 487 adjudications: 32 mention a weekday, but in 28 it
is CORROBORATIVE -- the *document itself* prints the weekday and the adjudication checks the document
against itself (Blandford2025, Leyden2025, Savoy2025, WestBrookfield2025). Only 4 are load-bearing
(D3 Athol2026, Granby2026, Hinsdale2026, Lanesborough2026: source names a weekday and no date) and
all 4 were already left ADJUDICATE/unresolved. **Nothing rests on nothing.** Rule D4 fires only on
Sunday, catches real scrape contamination (4 UPGRADE-SOURCE), and was left in place.

## known_bad_url was over-broad -- owner caught it (2026-08-13)
**UPGRADE-SOURCE must never condemn a URL.** `mark_bad_sources.py` had
`CONDEMNING = {"WRONG-DOC","UPGRADE-SOURCE"}`; 66 of 142 condemned stems were UPGRADE-SOURCE only,
**56 of them G1** ("document is THIN") -- a thin return is a real return. Abington2025's own D4 row
said "scrape contamination, NOT a bad election date". Now `{"WRONG-DOC"}` only, plus a RESCUE list
for WRONG-DOC rows whose reason already said the page was right and only the capture failed
(Hanson2025, Winthrop2025, Worthington2025). `unmark_bad_sources.py` restores state from
`master_urls.csv.bak`. Coverage 77.6% -> **80.9%** (1571 published), pop-weighted 92.6%.

## B4 gate bug -- FIXED 2026-08-13, and the first diagnosis was wrong
Montgomery2021 was condemned "a community newsletter, not an election return" -- a GENRE judgement
made without reading the content. Page 10 carries the full tally (PIERCE 136, MORRISSEY 78,
CHRETIEN 140) matching our JSON exactly. **The earlier note blamed a document-wide-vs-page-wise char
gate and that is NOT the bug**: page 10 holds 3,616 chars of article text AND 23 images, so it
passes every char-count gate. The tally is a RASTER ON A TEXT PAGE, and no char threshold can ever
see it. Nor can image area -- Ayer2022 has a 1.00-coverage full-page image and is legitimately
testable, because it is a SCAN whose text layer is the OCR of that image.
What separates them is **whether extracted words lie INSIDE the image box**: OCR text sits on top of
its scan, an embedded graphic has words around it and none within. `build_source_index.py` now has
`opaque_images()` (image >=10% of page AND <5 words inside its bbox) and emits a new
**`absence_testable`** field, distinct from `testable`. B4 and the `faithful` computation in
`checks.py` gate on `absence_testable`; D5 and others keep `testable` untouched. Flags 26 of 965
testable PDFs; of the 17 B4 stems exactly Montgomery2021 goes untestable (17 -> 16 findings),
leaving Ayer2022/Orange2021/Holland2025/Wrentham2026 testable. Never condemn a source on genre.

## C5's partition assumption -- FIXED 2026-08-13
C5 sums a district family only because it assumes the members PARTITION the town (disjoint
electorates, so totals may be added). Newton breaks that: per
`C:\Users\Owner\usbwebserver\root\standard-district-formats.md` Newton has both district-specific
and at-large councillors *representing each district*, so `School Committee Ward N` carries no
at-large marker yet is elected CITY-WIDE. `_ATLARGE_RE` already caught `Councilor-at-Large Ward N`;
only the figures reveal the school-committee case. Fix is a measured, city-list-free guard: compute
implied ballots per member and `continue` if the **MEDIAN** is >=0.90 of the reference. Corpus
separation is total -- Newton 1.000 vs Everett 0.333, Haverhill 0.289, Braintree 0.182,
Newburyport 0.256, Lowell 0.470 -- nothing sits near 0.90. Median, not mean/max, so one mis-parsed
block cannot suppress a genuine partition. C5 9 -> 4 findings, no finding lost.

## num_winners on city at-large blocks held CANDIDATES, not SEATS (applied 2026-08-13)
`apply_city_seat_counts.py`, 13 edits. Everett2021 (10->5, 6->3), Newburyport2023 (8->5, 4->3),
Lowell2025 (5->3, 4->2), each proved by arithmetic internal to the document against a printed
ballot line: Everett `Ballots Cast: 7348` (its one-seat Mayor race totals 7348 independently),
Newburyport `Total Ballots 4630`, Lowell Voters total 8494. Matters beyond the field because C5
builds its reference from the MEDIAN implied ballots, so a doubled at-large block halves the median
and honest ward races then read as inflated. Also found 3 uncaught OCR name errors in Newburyport
(ANDREW CRAWFORD **BOGER**, LYNDI L. **LANPHEAR**, **JARED** J. EIGERMAN) and 3 vote corrections.
**Lowell2025's own C5 adjudication is WRONG** -- it says "the same shape as Newton"; Newton's ward
blocks carry the FULL citywide count while Lowell's carry genuine fractions and partition normally.
It reasoned from a resemblance instead of the figures.

## Acushnet2025 -- repointed, not deleted
`native_url` was a 51-page 21 MB scanned environmental **monitoring report**. The record cannot have
come from it (no text layer, and the record holds no tallies -- all seven offices are the -1
won-count-unknown sentinel). `publish/markdown/Acushnet2025.md` names its real source in line one:
Fairhaven Neighborhood News, Beth David, 23/24 April 2025, "Total ballots cast: 996". Repointed to
the news article, `source_kind` official->news, both bad URLs into `known_bad_url`, the 21 MB PDF
deleted. **`coverage_state` deliberately LEFT at `published`** -- `winner_only` is not in the
vocabulary (published/no_source/no_election/pending_parse) so inventing it is a schema change, and
16 published town-years are already entirely winner-only (Canton2022, Hawley2021, Leverett2024/2025,
Mashpee2025...). Demoting Acushnet alone would single out one member of a settled class.
The official return is a GENUINE LOSS, not an unsearched gap: `4-22-2025_town_election_results_to_fax.pdf`
404s, the town moved to CivicPlus Nov 2025, and Wayback's 10 captures of that uploads directory hold
no election file.

## MEASURING OPEN WORK -- the trap that cost a session
`outputs/triage_queue.csv` holds **ALL** findings (1048), not just open ones, and headline counts
like `VIOLATION 246 | LEAD 176` are meaningless as a worklist. To get real open work, subtract rows
whose `(rule, stem, office)` is in adjudications.csv **AND honor the wildcard**: an adjudication row
with a **blank `office` applies stem-wide to that rule**. Missing the wildcard inflated the figure
to 175 when the truth was **54** (F1 46, C4 3, D2 2, C1 1, E1 1, G1 1) -- A4/F3/A3 entirely closed.
The linter prints the same figure itself (`N OPEN findings across N town-years`); trust that line.

## THE QA SWEEP IS CLOSED as of 2026-08-13. 43 open, ALL of one class.
Those 11 non-F1 findings were worked and closed (`close_tail_findings.py`, 490 -> 501 rows). **Every
rule is now at zero open except F1 UPGRADE-SOURCE, which holds all 43** -- records carrying tallies
whose source was condemned. Each needs a REPLACEMENT DOCUMENT found on the web; none is closeable by
QA arithmetic, so this is the handoff to the next stage (muni-harvest / doc-finding), not QA debt.
Coverage 81.0%, 1572 published, 92.6% population-weighted. Verifier held at exactly 3 failures
through every change and findings went 1048 -> 1045 with no new finding in any rule.

Closed by EDIT (`apply_image_reads.py`, `apply_turnout_and_chatham.py`):
Rowe2021 C1, Hatfield2024 E1 (turnout 506/2731 -- the article states it twice and the two agree),
Chatham2026 F1 (real uningested coverage: correct readable PDF present, coverage_state
no_source -> published; native_url still empty and that pointer gap left visible, not papered over).
Closed by DECLARATION in three distinct kinds, worth keeping separate:
**document DEFECTIVE** (EXCEPTION/ACCEPTED -- Charlemont2024, Granville2024 Assessor);
**document INSUFFICIENT** (EXCEPTION/UPGRADE-SOURCE -- Shutesbury2024, Acushnet2025, and
Hatfield2026/Shutesbury2026 which have no local source at all);
**downstream of a CONDEMNED source** (EXCEPTION/WRONG-DOC -- Colrain2026, Middlefield2022, whose
`no_source` state is CORRECT and whose tallies are the wrong document's contents).

## Reading handwritten tally sheets: crop hard, and check the components not the total
Rowe2021 and Granville2024 have no text layer. Rendering the full page at 1568px is **unreadable**;
crop to a quarter-page region and render at 2-3x (`fitz.Rect` clip + `Matrix(z,z)`), then read the
crop directly -- no API call needed, and it settles digits a batch prompt would guess at.
Rowe2021: Ellen Miller WI is **2** not 1, making 166 = 2 x 83 exactly. Granville2024 yielded three
corrections the linter could never have seen because **the errors cancelled**: Moderator stored
282+66=348 where the page prints 282+63 and page 2 (a separate PENCIL write-in sheet never read into
the record) adds John Audet 3; Selectboard stored 190+152+6=348 where the page prints 190+158 with
the Write in and Blank cells EMPTY. Both raced totalled correctly while both components were wrong.
Library Trustee 289 -> 287 (289+61=350 exceeds the 348 ballots, so it was impossible either way).
Granville2024 Assessor is genuinely defective: 291 + 80 + 1 write-in = 372 vs 348, both figures
re-cropped at full resolution to be sure. **Lesson: a race whose total matches is not thereby
correct -- and if a scanned return has a second page, check whether anything ever read it.**

## Still outstanding
2. **G1 is blind to a town thin in every year** -- it compares a town to its own history, so
   EastLongmeadow at 2 offices in 2021/2023/2024 never fires. **17 published records hold 1-2
   offices and no rule has ever flagged them** (Cambridge2021 has ONE office; FallRiver2021 two).
   Needs an absolute floor or a peer-size comparison.
3. **Alford2025 is mis-parsed wholesale** -- candidate names and street addresses sit in office
   slots ("Joan Caroll Rogers", "LAWRENCE ROAD"). Re-extract the file, do not patch races.
4. **~32 published town-years have no retrievable pointer** -- 26 with an empty `native_url`, 6
   reading `wayback-recovery`/`manual-find`. Hatfield2026 and Shutesbury2026 are in this group and
   additionally carry wrong-year dates. All need refinding.
5. Boxborough2026 town-year consensus 470 -> 705.
6. **3 cross-rule contradictions to restate**: Chester2024 (D3 ACCEPTED + D5/G1 WRONG-DOC),
   Truro2021 (A3 ACCEPTED + A5 WRONG-DOC), Rowe2024 (B4 RE-PARSE + C4/D3 WRONG-DOC).

## Goal-named items -- CLOSED 2026-08-13 (`close_named_findings.py`, 487 -> 490 rows)
Closed by DECLARATION, which is what the goal authorised when no edit can close a finding:
Brookfield2021 C4 (the return prints `Total Ballots Cast for the Election = 305 out of 2,518 Voters`
but the Selectmen block prints no race total -- deriving one would invent data);
Granville2022 C4 UPGRADE-SOURCE (no text layer; read from the page image);
Alford2025 A3 (two lines both reading `Write-In Candidate` with empty boxes).
`apply_turnout_recovered.py` wrote 6 document-proved turnout figures (Alford2025 54, Brookfield2021
305/2518, Montgomery2021 145/639, Everett2021 7348/22042, Newburyport2023 4630/15067, Lowell2025
8494) -- `votes_recorded_est` untouched, it is the only independent check on these. Brookfield's and
Montgomery's doc figures matched our est exactly. Make such scripts **idempotent**: same value =
ALREADY, different value = CONFLICT-refuse; a plain "refuse if non-empty" blocks all later re-runs.

## Method notes that keep paying
Evidence spans must avoid **apostrophes**, **square brackets** and **double quotes**; needles match
RAW text so they must be newline-free; Newbury2023 joins its headline with **non-breaking spaces**.
Vision batch: render each page to its OWN long edge of **1568px**; orientation is a checked table
(`UPRIGHT`), not a heuristic. Batch cost is trivial -- 11 requests/66 images = **$1.52**.
Subagents with self-contained prompts and an UNRESOLVED escape hatch performed well and correctly
refused to close 4 of 9 findings; still re-test every span mechanically. See
[[civicatlas-qa-standard]] and [[civicatlas-scope-municipal-only]].

Credentials: `ANTHROPIC_API_KEY` in `CivicAtlasMA/config/.env`. Print key NAMES and LENGTHS only.
