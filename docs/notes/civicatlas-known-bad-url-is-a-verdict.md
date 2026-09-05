---
name: civicatlas-known-bad-url-is-a-verdict
description: known_bad_url rows already carry the verdict in the verification column; a refetch that ignores it lands real returns under the wrong town
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

In CivicAtlasMA, `known_bad_url` is NOT a bin of leads nobody followed. For many
rows the `verification` column already records who followed it and what they
found: `duplicate:file declares Royalston`, `mishost:source is ashlandmass.com`,
`wrongyear:document dated 2014-05-13`. A refetch driver that reads the URL and
ignores the adjacent verdict landed 10 documents on 2026-08-19 and all 10 were
wrong — Oxford's return under Russell, Ashland's under Warren — and 4 of them
overwrote *published* rows that had good citations. Reverted from
`master_urls.csv.bak_preurl`; `src/revert_refetch.py` does it.

**Why:** every one of the 10 was a genuine, well-formed annual town election
return, so a content test ("is this a return?") passes them. That is the right
answer to the wrong question. See [[civicatlas-wrong-artifact-checks]] — this is
the same defect from a new angle.

**How to apply:** a fetched document must pass BOTH tests before landing — it
reads as a return, AND it names this municipality and this year. The document's
own date beats the URL's date (a Mount Washington return headed 2023 sat at a
`2022-05-09` slug). Skip any row whose `verification` starts with
`duplicate:/mishost:/wrongyear:`. A town meeting is not an election, and
"results of the" is not enough to prove one — test for the word `election`.
After this hardening the 183-lead sweep lands zero documents: those URLs are
genuinely bad, so recovery must come from new citations, not refetching.

---

*Revised 2026-09-05 by the owner during the migration review. The correction is his; the note is otherwise as originally written.*
**Retired 2026-09-05. "Known bad" is not a verdict, it is an absence of one.**

The convention says a URL is bad without saying what it is, and the reason then lives in
whatever column happened to be free. Across 322 rows and 410 URLs the `verification` column
holds a mix of real findings (`ocr_triage:wrong_doc`, `local_triage:not_results`) and process
notes (`manual_ingest`, `landed 2026-09-01 from the round-9 gap sweep`) -- so the same label
covers a document proven to be the wrong election and one nobody has looked at since ingest.

**Never describe a document as bad. Say what it is.** A citation gets a status naming the
finding -- `not_a_return`, `wrong_election`, `wrong_town`, `wrong_year`, `landing_page`,
`dead_link`, `out_of_scope` -- and a document that has merely failed to fetch is none of
those, it is unfetched.

The reason this matters beyond tidiness: `wrong_year` is recoverable and `dead_link` may
resolve tomorrow, but both were filed under the same word as `not_a_return`, so nothing could
tell which condemnations were worth revisiting.
