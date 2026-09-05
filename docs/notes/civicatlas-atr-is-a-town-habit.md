---
name: civicatlas-atr-is-a-town-habit
description: "whether the Annual Town Report carries the election is a property of the TOWN not the year, so one ATR-sourced town-year is a lead for every other open year in that town; 30 towns / 38 leads / 9 documents for zero human input, and the wrong-year trap that check must have"
metadata:
  node_type: memory
  type: project
---

2026-08-24, the owner's observation and it generalises well. A clerk who writes
the election results into the annual report writes them EVERY year. So a
town-year already sourced from an ATR is evidence about every other open year in
that town -- and the report is usually one year-substitution away from a citation
we already hold.

`src/find_atr_pattern_gaps.py` -> **30 towns, 38 (town,year) leads.**
`src/harvest_atr_years.py` varies the year and crops by content ->
**9 CROPPED, 16 NOT_FOUND, 11 NEEDS_ID_SWEEP, 2 NO_ELECTION_PAGE.**
Nine documents for zero human input. Corpus 1695 -> 1765 published across
Ingest 5+6, 90.9% town-years / 96.9% people-years, $0.72 total LLM spend.

**Classify by the CITATION, not source_kind.** Only 13 rows carry `source_kind=ATR`;
far more are identifiable from the URL -- annual/town report, `ArchiveCenter/ViewFile`,
a `#page=` fragment, `archives.lib.state.ma.us` bitstreams.

**THE WRONG-YEAR TRAP, and it is severe.** Substituting the year in a URL can
resolve to a REAL report that is not the year you asked for. Boxford, Mendon and
East Bridgewater all opened "Annual Town Election June 29, 2021". A check that
asks "does 2026 appear anywhere in the text" PASSES all of them, because an
annual report names a dozen years (fiscal columns, prior-year comparatives, terms
expiring). **Test the date attached to the election HEADING**, within ~90 chars,
and read two-digit clerk forms (`*4-10-21`) as well as four-digit. That caught 4
documents that would have published under the wrong year.

**DocumentCenter ids do not follow the year.** `DocumentCenter/View/3316/2022-Town-Report`
cannot become 2021 by editing the title -- the id resolves, the title is
decoration. Report those as NEEDS_ID_SWEEP; the id space is enumerable
(probe_town.py, muni-harvest dc-idsweep) and does not decay for back years.

**AN ATR's ELECTION TABLE IS OFTEN AN EMBEDDED IMAGE.** Bourne's p186 and
Yarmouth's p68 have ZERO text, so no page-number arithmetic finds them and no
vocabulary scorer scores them. Look for the low-text pages ADJACENT to the named
one (Yarmouth 69-75, Bourne 188+) and render-then-OCR. Also: Ingest 5's manifest
gave PRINTED page numbers, Ingest 6's gave PDF indexes -- always establish which
convention is in force, then verify the page by content anyway.

**North Andover 2021 is recovered.** The Drive folder became shared; it lists
`3-30-2021 Annual Town Election - Official.pdf`. The earlier pass was right that
the absence was a SHARING SETTING, not a missing file -- see
[[civicatlas-clerks-publish-to-google-drive]]. The Drive MCP was unavailable, but
the public folder HTML lists filenames and ids and `uc?export=download&id=` fetches.

**THE STATE ARCHIVES IS THE BEST ATR SOURCE, and it has an API.**
`archives.lib.state.ma.us` is DSpace: `/server/api/discover/search/objects?query=<town>+annual+report`
then items -> bundles(ORIGINAL) -> bitstreams -> content. One polite JSON call per town beats
any web search, and the depth is two centuries -- Rowley 1828-2024, Petersham 1848-2023,
Adams 1897-2024 (51 distinct years). `src/search_state_archives_atrs.py` +
`src/fetch_state_archive_atrs.py`. This closed 5 more town-years immediately.

Two guards it needs: **the year must be in the TITLE** (DSpace date metadata includes the
archive's own accession dates -- that tied 2026 to a Wachusett water-quality report; 46 leads
-> 16 when fixed), and **a containing town name is a different town** ("West Boylston" matches
a word-boundary search for Boylston, exactly like South Essex/Essex).

**A CLERK'S CROSS-REFERENCE IS NOT THE RESULTS.** Brimfield's FY2022 report says in the Town
Clerk's own section "See results from the local election further in this report" -- and they
are not in it (pp106-115 Town Meeting, 116-123 other departments, p124 blank). I first
concluded that from keyword scans and the owner rightly pushed back; reading the pages
confirmed it. The sentence still corroborates the date and turnout (June 21 2022, 671 ballots,
23%), which is worth recording even when the return is elsewhere.

Handoff for the pre-2021 extension: `research/pre2021_atrs/README.md`. Note that adding
pre-2021 years is a DENOMINATOR change, not a data task.

Related: [[civicatlas-batch-ingest-screening]], [[civicatlas-ungrounded-is-unread]].
