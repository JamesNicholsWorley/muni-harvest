---
name: civicatlas-ingest-restart
description: "CivicAtlas ingest restart: parse_gate.py (ADMIT/HOLD/DROP) built 2026-08-13 — the fabrication class, the stale-cache defect (data/pdfs keyed by stem not content), the heading guard and why a heading alone must never DROP; guard 1 shipped as a ratchet in save_rows"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

The QA sweep closed 2026-08-13 (see [[civicatlas-qa-tail-close]]) and the owner green-lit restarting
collection with the linter folded into ingest rather than run after it: *"I think we are actually on
good footing to incorporate the linter into the ingest with these lessons."*

**Why 136 published rows have an empty `native_url` — three causes, not one.**

| n | cause |
|---|---|
| 95 | the collector never wrote the field. `custom-search` (25), `custom-search-2026` (67), `manual-find` (2), `wayback` (1) are **100% blank**, while `LEO` is 3% and `NEWS` 5%. A 100%-vs-3% split is a missing field write, not attrition — those pathways fetched the PDF, saved `hosted_url`/`pdf_filename`, and never persisted the URL they had just fetched from. |
| 38 | deliberately blanked when the URL was condemned; `known_bad_url` holds the string on every one. Working as designed. |
| 3 | genuinely unexplained: Leominster2023, Dracut2021, Sandisfield2025 (all `LEO`/`hosted`, no hosted_url, no known_bad_url, no note). |

112 of the 136 still have a `hosted_url` mirror, so the **file** is retrievable — what was lost is
the **citation**. Diagnose this class by grouping on `provenance` and comparing blank-rates per
pathway; a per-pathway rate near 100% always means a code path, never data loss.

**The four guards the ingest linter must carry.**
1. **`native_url` required at write time.** Non-empty or the row does not get written. That one guard
   prevents all 95. Condemning a URL must MOVE it to `known_bad_url`, never erase it.
2. **Special-election detection in the parser.** Owner: *"we purposely aren't looking for special
   elections right now, but maybe we could add that to the parser and drop it after being collected."*
   Collect, flag, then drop before ingest — alongside the date check and a sparse-office-count flag.
   `election_type` is currently the constant `regular` on all 1572 published rows and has **never**
   been checked against a document; D3 is the only proxy.
3. **D5 at ingest, not after.** It reads stored office labels, so it works on 100% of records
   regardless of whether the source has a text layer.
4. **Turnout and coverage_state written together**, so `published` can never mean "no source".

**Terminology, owner's wording (2026-08-13):** say **"document needs upgrading"**, not "condemned
source URL" — and that class *merits inclusion in the next collection pass* rather than sitting as
QA debt. Applied to the F1 message in `qa/civicqa/checks.py` and the detail key
(`condemned` -> `needs_upgrade`).

**Three things the linter structurally cannot certify — accepted, not fixed.**
- **Provenance is unknown for 326/1572 (20.7%)** whose sources can't be searched (no text layer, OCR
  noise, opaque images). Owner: *"we just have to leave for now, if they pass every other check."*
  Never report these as passing B4 — unknown is not verified.
- **Compensating arithmetic errors are invisible** to every total-based check. Granville2024's
  Moderator stored 282+66=348 and Selectboard 190+152+6=348: both totals right, all four components
  wrong. Owner: *"nothing we can really do except maybe do better cropping on images."*
- Everything else was measured clean at 100% of published records: 0 state/county offices, 0 ballot
  questions, 0 empty office labels, 0 published rows without JSON.

**CORRECTION 2026-08-13 — "no false promises in the database" was WRONG, and the gate proved it.**
`src/parse_gate.py` (ADMIT/HOLD/DROP, built this day) ran the whole corpus and found what the closed
sweep could not, because the linter's rules each call `is_regular()` and so **filter specials out of
themselves instead of judging the record**. Published-row verdicts: ADMIT 1309, HOLD 156, DROP 107.
- **7 published town-years are single special elections** — Harvard2025, Marshfield2026, Mashpee2022,
  Oakham2023, Rowe2026, Wales2024, Wales2025. One race each, `type: Special`, off-cycle date.
- **Otis2024 is a state primary** ("State Committee Man -DEMOCRAT") published as Otis's annual
  election. D5 has no party-committee pattern; the gate has one and deliberately disagrees until D5
  is amended.
- **~74 published records assert a date their searchable source never prints.** Ashburnham2024 is
  headed `ELECTION RESULTS - 2024 TOWN ELECTION` and Tisbury2024 is a news article saying "won
  re-election Tuesday"; **neither page prints a date at all** and the parser invented `2024-11-05`
  across 22 races. 705 of 1773 documents have no text layer, so the true count is higher. Guards:
  `DATE_UNEVIDENCED` (no `date_verbatim`) and `DATE_NOT_ON_PAGE` (no date in any form on a searchable
  page). An invented date is worse than a missing one — leave the field empty.

**THE FABRICATION CLASS — found 2026-08-13 by test-parsing 2025, the worst defect yet.**
Winthrop2025's source is **489 characters of website navigation**; its only content is the page
title `11-4-25 ELECTION DRAFT RESULTS` repeated three times. The parser returned **9 races, 43,024
votes**, a heading `TOWN OF WINTHROP / MUNICIPAL ELECTION` and a date `TUESDAY NOVEMBER 4, 2025` —
none of it on the page, and the candidate names are **real Winthrop officials recalled from training
knowledge**. Every existing guard passed it: there ARE votes (so NO_TALLIES and BALLOT_NOT_RETURN
stayed quiet) and `11-4-25` IS on the page (so the date checks were satisfied by the very title that
was all the model had). A fabricated return is internally consistent by construction — the totals
add up precisely because nobody transcribed them — so **no downstream arithmetic check can ever
catch this.**

Guard: `Gate._check_grounding` — take candidate surnames, check they appear in the source. <15% =
DROP (`CONTENT_NOT_IN_SOURCE`), 15-50% = HOLD. Corpus-wide it found **13 DROP + 6 HOLD**. The true
class is *wrapper pages*: Hanson2025 is a landing page reading "Attached are the OFFICIAL RESULTS"
(the attachment was never fetched), Quincy2021 is a results *index*, Weston2021 is a Facebook post.
The document was never in hand and the model filled the gap.

**Two false-positive classes it initially produced, both now fixed in `_searchable`** — and the fix
matters more than the guard, because *a false accusation of invention discredits the guard that
catches the real ones*: (1) **mojibake** — Dunstable2025 extracts 1255 chars of U+FFFD from a PDF
whose font has no encoding map, which is as unreadable as an image but passed a length test;
(2) heavy OCR symbol-noise (Brockton2025). `_searchable` now also requires <10% replacement chars
and >=25% ASCII letters. This same fix cut `DATE_NOT_ON_PAGE` from 87 to 52, so the earlier
"~74 invented dates" was itself inflated by unreadable text.

**Date reality after checking against the MMA calendar (and rules extrapolated back to 2021-22):**
**58 corroborated, 19 genuinely disagree, 7 untestable.** Most disagreements preserve the DAY OF
WEEK and are off by a whole number of weeks (±7/±28/±35) — the signature of a date *computed from a
weekday rule* rather than read. Do NOT blanket-overwrite with the MMA date: a disagreement is often
the signal that the document is not the annual election at all (Ashburnham2024, Tisbury2024).

**THE STALE-CACHE DEFECT — found 2026-08-13, and it nearly destroyed five good records.**
`data/pdfs/<stem>.pdf` is keyed by **stem, not by content**. When a row's `native_url` was upgraded
the superseded document **kept the filename**, so the cache silently holds the wrong document under
the right name. This was invisible until the OCR backfill read those files and wrote them to
`data/raw_ocr/<stem>.txt`, where `source_text()` serves them as *that row's text*. The new heading
guard then read STATE ELECTION and condemned Barre2023, Chatham2024 and Cohasset2024 — all three of
which are **good municipal records**. Fetching Chatham2024's own cited URL returns
`TOWN OF CHATHAM / THURSDAY, MAY 16, 2024 / ANNUAL TOWN ELECTION`. Lancaster2024 and Carlisle2024
failed the same way with the cache faithful and the **citation** wrong instead.
`src/verify_local_pdfs.py` now byte-compares each cached PDF against its live URL and quarantines the
OCR of any mismatch. **A cache keyed by an identifier is a promise about the bytes that nothing
enforces — check it before reading it as evidence.**

**Guard 7, `_check_heading` — identify a document by what it calls ITSELF.** `_check_scope` reads
stored office labels, so a document headed STATE ELECTION whose parse kept municipal-looking rows
walks straight through. Runs on OCR (a heading is large isolated type and OCRs reliably). Two hard
lessons in its design:
- **A heading alone must never DROP.** Becket2023 reads *'the State Election was held in the Becket
  Town Hall ... on May 20th, 2023'* and then tallies Select Board. May 20 2023 is a Saturday; there
  was no state election. It is a town election on the clerk's state-election template.
- **The discriminator is the RECORD's own offices, not the document.** State heading + non-municipal
  offices = DROP (Sherborn2024, six STATE COMMITTEE MAN races). State heading + municipal offices =
  `SOURCE_DOC_MISMATCH`, a **HOLD**: record and artifact are different documents, one of them is
  wrong, and the tallies may be perfectly sound.
- **Never match "general election".** In a Massachusetts CITY the municipal election *is* the general
  election (the preliminary is its primary). All ten corpus hits — Watertown, Pittsfield, Haverhill,
  Leominster, Everett, Brockton, Barnstable, Taunton, Easthampton, Plymouth — were **odd years**,
  when no state general exists. Matching it condemns ten good city returns to catch nothing.
- Strip nav chrome before reading a heading (`_heading_region`): a scraped CMS homepage puts
  'State Election' in a menu, which condemned Stoughton2022 for the wrong reason.

**"What cannot be seen is not a pass" applies PER QUESTION, not per document.** OCR reads a *heading*
reliably and a *vote table* badly — Ayer2026 OCRs its title as `Annual Town Election May 12, 2026`
perfectly while rendering the table as `Precinet2` and `AyerRegistered`. So the same text supports the
scope/date/heading guards and **cannot** support `_check_grounding`: in an OCR read a missing name is
not evidence of absence. Scoring names against OCR measures OCR quality and calls the result
fabrication. `Gate._text_is_ocr` (set from `source_kind()`) gates this.

**The 2025 parser test result (owner asked for it): the gate agrees with the human.** Re-fetching the
21 condemned 2025 URLs (`src/stage_2025_retry.py`) staged 10; of those **9 were rightly condemned** —
6 came back sample ballots (`BALLOT_NOT_RETURN`), 2 fabrications, 1 bad date. Only Holliston2025
ADMITted. **Re-fetching a condemned URL only re-proves it is condemned; closing a year needs
DIFFERENT documents**, which is what `src/prospect_2025.py` (scored best-first crawl of the town's
own site) is for. Rank hub links, never take them in page order — Boxford's homepage offers nine
'election' links and the town clerk is the seventh. Penalise Annual Town **Meeting**: it is the
town's legislature, not its election.

**The prospector's 2025 harvest, and why link text is not evidence (2026-08-13).** 68 towns crawled,
15 produced a candidate. The lesson is the one this project keeps relearning: **the prospector scores
LINK TEXT, and a link is a promise about bytes nobody has opened.** Stow's top-scored link (9/9) read
`May 17, 2025 Annual Town Election Draft Results` and the file behind it is `SAMPLE BALLOT` repeated
nine times; the *lower*-scored link was the real return. `src/inspect_2025_candidates.py` fetches and
prints the first 400 characters of every candidate before a single token is spent on parsing, and
that step alone caught it. Never submit a prospector hit to the parser unread.

What the 68-town crawl actually yielded: **4 documents with clean text layers** (Lynnfield, Stow,
Leyden, Haverhill), **3 image-only needing OCR** (Canton -- whose text layer is a column-scrambled
617 chars of bare numbers, Oak Bluffs, Wales 05-28), **2 link-rotted** (Townsend, Westport: the URLs
carry a `?t=` cache-buster token and 404 without it *and* with it; Westport's clerk page builds its
links in JS), and **2 annual town reports** whose election pages are *scanned images inside a
digital PDF* -- Rowe's pages 138-148 extract as nothing but a page number. 53 towns produced nothing,
several because the crawl resolved their homepage to a NEWS site or, for Mattapoisett and Norwood, to
**our own published mirror on github.io** -- a circular crawl worth guarding against.

**Two real upgrades and two no-ops, measured by diffing against the superseded file.** Stow2025's
document on record WAS the sample ballot (that is why it held `BALLOT_NOT_RETURN`), and Leyden2025's
was the *unofficial* posting superseded by the official one. Lynnfield and Haverhill re-found the
byte-identical document already on file. **Diff every "new" source against the old one before
claiming an upgrade** -- half of these were not upgrades at all.

**Haverhill2025's stored date is provably wrong, and the signature is the day of the week.** The
record asserts `2025-11-01`, which is a **Saturday**; Massachusetts city elections are Tuesdays and
the document prints only `GENERAL ELECTION - NOV 2025`, no day. The day was computed from a rule and
not read -- the same signature as the ±7/±28 date class. Lynnfield2025 is the honest opposite: its
page prints `April 8th` with **no year at all**, so its 2025 comes from the filename. That is
citation-level evidence, not page-level, and `DATE_NOT_ON_PAGE` is right to keep holding it.

**Overwriting `publish/markdown/` is recoverable -- `publish/` is a git repo.** Staging new text with
`measure_parse_cost.MD_DIR` writes straight over the existing markdown with no backup and no warning.
`git show HEAD:markdown/<stem>.md` recovered all four; they now live in `data/superseded_markdown/`.
Check `git status` before trusting that a staging step was non-destructive.

**Two ballot-derived records replaced with real returns (2026-08-17), via `src/wire_2025_replacements.py`.**
Stow2025 and OakBluffs2025 were both `no_source` rows whose published parse came from a SAMPLE BALLOT
(OakBluffs: 15 races, every candidate row 0 votes). Replacements: Stow DocumentCenter/1687, OakBluffs
DocumentCenter/**12358** (the condemned URL was 12344 -- a neighbouring ID on the same CMS). OakBluffs
re-parsed from OCR gives 15 races where every single-seat race totals exactly **928** and multi-seat
races 2x/3x it: 15 races reconciling to one turnout figure is the strongest internal check available.
Corpus went to ADMIT=1343 HOLD=305 DROP=125. **Order of operations matters and is encoded in the
script: update the CITATION first, then write artifacts to match it**, never the reverse, or the
stale-cache defect is recreated. Superseded artifacts go to `data/superseded_pdfs/` -- the ballot is
the evidence the A5/A3 findings were written against and cannot be deleted.

**TWO DIFFERENT `source_text()` IMPLEMENTATIONS DISAGREE ABOUT WHAT A DOCUMENT IS.** `src/parse_gate.py`
looks up publish/markdown -> data/markdown -> **data/raw_ocr**. `qa/dossier.py` is driven by
`qa/reference/source_index.json` (built by `qa/build_source_index.py`), which searches publish/pdfs,
data/pdfs, _oversized, pdfs_upright and publish/markdown -- and **has no OCR tier at all**. So the
entire OCR backfill is invisible to QA. Consequence, found the hard way: after wiring OakBluffs2025
its 4 adjudications did not resolve, they became *unverifiable* -- the verifier's failure count fell
from 4 back to 3 while "source has no text layer" rose 136 -> 140. **A failure count that improves
because a source became unreadable is not an improvement**; unknown is not verified. Adding
`data/raw_ocr` to the QA source index is the fix and would make a chunk of the 140 checkable.

**The adjudication-supersession problem, sized.** `qa/reference/adjudications.csv` (501 rows; fields
`rule, stem, office, disposition, fix, reason, evidence, adjudicated_on`) binds a finding to a stem
but **not to a document identity**, so replacing a source silently invalidates every finding written
against it. Stow2025's A5 quotes 'sample ballot'; we replaced the ballot, so the span vanished and the
verifier reported successful remediation AS A FAILURE. This is pre-registered to recur: **89
UPGRADE-SOURCE findings across 75 stems and 131 WRONG-DOC across 76 stems** -- ~150 findings that will
all invert as the collection work they request gets done. Findings need a lifecycle (close as RESOLVED
when the named source is replaced) before the upgrade backlog is worked, or QA signal degrades exactly
as the corpus improves.

**Gate design rules worth keeping.** *Content condemns; dates only raise* — a date may HOLD but never
DROP, since a date-vs-calendar disagreement is evidence of nothing on its own. *What cannot be seen
is not a pass* — every absence test first checks the text is searchable (image-only PDFs convert to
the literal string `<!-- image -->`, and asserting "no date here" about 14 characters nobody read is
a false positive, not a finding). *Sparse is intent, never a drop* — SUPPLEMENT when the document
says the rest of the ballot was uncontested (a sample ballot completes it), SUPERSEDE when what is
missing is unknown.

**Guard 1 is built, as a ratchet at the choke point.** It lives in `sync_to_github.save_rows()`, not
in one collector, because five scripts write `native_url`. A row claiming a document (hosted_url,
pdf_filename, or published) with neither `native_url` nor `known_bad_url` is unciteable; the
offenders already on disk (223) are grandfathered and read from disk each run, so a NEW one raises
and the bar rises on its own as the backlog is re-sourced. A hard rule would have failed every run
and been deleted.
