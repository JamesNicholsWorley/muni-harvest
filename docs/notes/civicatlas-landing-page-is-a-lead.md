---
name: civicatlas-landing-page-is-a-lead
description: "18 CivicAtlas stems filed as BLOCKED were never fetched: page.goto returns 200, only context.request.get 403s, and the candidates were HTML landing pages that sha256 could never accept; resolving page-to-attachment recovered 11 of 18"
metadata:
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

CivicAtlasMA URL recovery filed 18 stems as BLOCKED across three passes: HTTP 403
with `requests`, then the same 403 through the stealth browser, which read as
"even the browser is refused." One line of diagnosis broke it — `page.goto`
returns **200** on all of them. Only `context.request.get` 403s; this CMS vendor
refuses non-navigation requests. **Seventeen different towns failing identically
was never seventeen WAFs, it was one shared platform.**

The deeper error was in the question, not the transport. Those candidates are
`/home/news/annual-town-election-results`, `/town-clerk/pages/elections-voting` —
**HTML landing pages**. The acceptance test is `sha256(fetched) == sha256(held
PDF)`, so even a perfect 200 could never have accepted one. The tool asked a
question the candidates could not answer and filed the non-answer as a fact about
the town.

**Why:** a landing page is a LEAD in exactly the sense a date in a URL is (see
[[civicatlas-mine-before-scrape]]) — it names where the document is without being
it. Rehoboth's page says so in words: *"Attachment Size / 4-7-2026-Official Annual
Town Election Results / 257.07 KB"*, with the real file under
`/sites/g/files/.../f/news/...`. That static path fetches fine; the page's own
address does not.

**How to apply:**
- `src/resolve_landing_pages.py`: goto the page, harvest document links, rank,
  fetch the best few, keep the sha256 test unchanged. **11 of 18 recovered**
  (ADMIT 1442→1451, coverage 74.3%→74.8%). Better reach, identical proof.
- **Rank hard or you fetch the whole town.** Rehoboth's page yields 80+ links,
  nearly all global footer — cemetery rosters, a swimming pool code, Light Up
  Rehoboth. Require election vocabulary in the link's own text/href as a floor,
  prefer the target year, penalise a *neighbouring* year and state/primary words.
- **The document still beats the URL.** Berkley2026's accepted file is named
  `ATE-5-9-2025-Unofficial-Results.pdf`, but the PDF's own heading reads `ANNUAL
  TOWN ELECTION UNOFFICIAL RESULTS MAY 9, 2026`. A town's filename typo is not a
  wrong-year finding — open the file. See [[civicatlas-known-bad-url-is-a-verdict]].
- Every recovery stage writes the SAME ledger schema and `--from-csv` reads all
  of them; keep the files separate so a stem reading STILL_BLOCKED in one and
  ACCEPTED in the next stays legible as the finding it is.
- **Shell trap:** never pipe a script that writes files through `head` — the
  broken pipe kills it after the summary prints but before the write, so it looks
  like it succeeded. Redirect to a log and grep the log.
