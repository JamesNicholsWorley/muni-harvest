---
name: civicatlas-clerks-publish-to-google-drive
description: "Some MA town clerks publish election returns ONLY to a Google Drive folder linked from their website, which is invisible to every crawler; the Drive MCP can list those folders, and 'no document' may really be a sharing setting"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

West Springfield 2025 was filed as `PROSE_NAMES_WINNER` — we cite a Reminder
story about the mayoral race and hold no council result. Its Town Clerk >
Elections page has **zero document links**. Not "no results posted": the page
defers entirely to

    drive.google.com/drive/folders/1rlOsM6GvddUKWpYP3lMM8sS99NWQcY1W
    ("Current Election Information", owner ofrizzell@townofwestspringfield.org)

**A Drive folder is not in nodes.jsonl, not in Common Crawl, not in Wayback, and
not reachable by any of the fetchers in this repo.** No amount of mining the
harvest could ever have found it — the town's whole document library for this
department lives off-web. Mining-before-scraping is still right, but a null
result from the harvest for a town with a thin website should raise "where does
this clerk actually publish?", not "this town publishes nothing".

**The Drive MCP lists them.** `search_files` with `parentId = '<folder id>'`
enumerates children, and the returned `contentSnippet` carries extracted PDF
text — enough to read a whole certified return without downloading it. The 2023
subfolder gave the complete West Springfield return (eight precincts, Councilor
at Large, four district councilors, school committee, over the clerk's
certification letter) straight out of the snippet.

**And the negative result is a different KIND of negative.** The parent holds a
subfolder titled `Election Results` created **2025-11-05, the day after the 4
Nov 2025 city election** — exactly where the missing return belongs. Its metadata
enumerates; its children return `{}`. That is a **sharing setting**, not an
absence. So the records request should ask the clerk to open the folder rather
than to produce a document, and the folder is worth re-listing before asking,
since a clerk may simply not have finished publishing. Compare
[[civicatlas-blocked-is-a-tool-verdict]]: the 403 described our client, and here
the empty listing describes our credentials.

Worth sweeping for: any town-year in `logs/records_requests_2025.csv` whose
`town_website` yields no document links at all is a candidate for the same
pattern. Related: [[civicatlas-mine-before-scrape]],
[[civicatlas-landing-page-is-a-lead]], [[civicatlas-citation-not-source]].
