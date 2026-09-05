---
name: civicatlas-archive-recovery-levers
description: the levers that actually recover a vanished municipal return, and how to prove an absence is real - MemGator over all 15 archives, CivicPlus full-text search, vendor origin hosts, local-paper archive APIs, and the CC-robots-403 check
metadata:
  type: reference
---

> **Schema note, 2026-09-05.** This note predates the retirement of the `-1` and
> `-3` sentinels. Wherever it says `votes = -1`, the corpus now holds
> `votes: null` with `status: "uncontested"`; `-3` is `status:
> "write_in_winner"`. The reasoning below is unaffected -- only the spelling
> changed.

Recovery levers proven on the 2025 corpus, roughly in yield order.

1. **The town's own naming SERIES across years.** Find the 2023/2024/2026 results URL and swap the
   year. Highest-yield trick there is. Watch for Drupal's collision suffix: a second upload of the
   same basename becomes `..._0.pdf`, and news slugs go `annual-town-election`,
   `annual-town-election-0`, `-1`.
2. **Vendor origin hosts still serve after a CMS migration.** `<town>.civiccms.acsitefactory.com`,
   `cms2/cms5.revize.com/revize/<town>/`, `storage.googleapis.com/proudcity/<town>/`. This is the
   ONLY copy of Tolland's 2023-2026 returns. **But `*.civiccms.acsitefactory.com` is a WILDCARD** —
   a bogus name returns the same 28,585-byte Drupal 404, so a 404 proves nothing. Discriminate by
   probing a known-good name, or host-header probe the stack ELB.
3. **Local weekly newspaper archive APIs.** Recovered Southbridge's entire tally when the town had
   deleted its own posting: `POST stonebridgepress.com/PdfSource/ItemIndexGetData` returns public
   Azure-blob PDFs for all 2,281 issues. Turley Publications (Barre Gazette etc.) runs a similar
   e-edition system.
4. **CivicPlus full-text search**: `<town>.gov/Search/Results?searchPhrase=` searches INSIDE
   DocumentCenter PDFs, not just titles — strictly better than an offline title index.
5. **Headless-CMS JSON indexes.** Munibit/membershipware exposes the whole document tree:
   `app.membershipware.com/api/public/mwjsResources` (tokens in the page HTML) — 4,300 Granby files
   in one request. Sanity CMS likewise. Note Granby's blob URL needs a same-site `Referer` header
   or it 400s.
6. **The block ladder.** A non-200 is a fact about our client. urllib default UA -> browser UA ->
   `curl_cffi impersonate="chrome"` -> Playwright. Measured over 348 published 2025 citations:
   **77 resolved only with a browser UA and 30 more only with TLS impersonation** — 31% would read
   as "missing" to a naive fetcher, and EVERY 403 was a block, not an absence.

**Proving an absence is real** (Hinsdale 2025, the case that needed it):
- **MemGator** at `memgator.cs.odu.edu` fans out to ~15 archives (archive.today, Arquivo.pt,
  Perma.cc, BAnQ, NDL, Archive-It, UKWA...). The old `timetravel.mementoweb.org` is NXDOMAIN.
  Pass the URI-R **schemeless** — curl collapses `https://` to `https:/` and you get false 404s.
  If all mementos of a domain are web.archive.org, Wayback IS the whole universe for it.
- **Common Crawl silence is only evidence if CC wasn't refused.** Check whether the records are
  robots.txt fetches returning 403 to CCBot — Hinsdale's were, so CC never held a content page.
- **A month-by-month CDX histogram** localises the gap. Hinsdale: Apr 103 / **May 0** / Jun 15 /
  Jul 21. The election was 17 May. Asset-only captures (CSS/JS) don't count as coverage.
- **Search-index residue is evidence the file existed**: the exact filename was indexed with title
  metadata and has since been dropped, while a sibling file under the same vendor prefix is still
  indexed.

**Facebook is blocked, not empty.** Page listings serve a login wall unauthenticated, but an
individual post's *share* URL renders a public preview. Douglas 2025 and Weymouth 2025 were both
published to Facebook and nowhere else, so this matters. See [[civicatlas-names-are-unchecked]].

## Publication channels beyond the town website (2026-08-21)

A town's return is often NOT on its own site, and no crawl or archive sweep will ever reach it.
Every one of these produced a real recovery:

| Channel | Case | How to get the data |
|---|---|---|
| **Tableau Public** | **Norwell 2025** — the ENTIRE election, per-precinct, 12 offices | The viz downloads as `public.tableau.com/workbooks/<Name>.twb`, which is really a **ZIP** containing a `.hyper` extract. `pip install tableauhyperapi`, open with `HyperProcess`/`Connection`, `SELECT * FROM "Extract"."Extract"`. 69 rows including seat counts and a winner flag. |
| **Constant Contact newsletter** | **Richmond 2025** | Tally PDF hosted on `files.constantcontact.com`, linked only from the town's newsletter index page. Off-domain; follow `conta.cc` shortlinks. |
| **Local weekly newspaper archive API** | **Southbridge 2025**, after the town DELETED its own posting | `POST stonebridgepress.com/PdfSource/ItemIndexGetData` returns public Azure-blob PDFs for all 2,281 issues. Turley Publications runs an equivalent e-edition archive. |
| **Facebook (only)** | **Douglas 2025**, **Weymouth 2025** | Page listings need a login; an individual post's **share** URL renders a public preview. |
| **Google Docs / Drive** | **Gosnold 2025** (public Google Doc), **West Springfield** (clerk's Drive folder) | Cite the doc URL directly. |
| **WordPress POST BODY** | **Blandford 2025** | Results typed into the post, NOT uploaded as a file — a media-library sweep misses it. `/wp-json/wp/v2/posts?search=election`. |
| **Following year's annual report** | **Blandford 2025** | The 2025 return sat in the ADDENDA of the **2025-2026** volume; there was no 2024-2025 volume. |

**The lesson:** before calling a town-year unrecoverable, ask "where else could a clerk publish?" — not "did I crawl the site hard enough". Norwell had been declared a records-request case after nine levers were exhausted correctly; the data was on Tableau Public the whole time.

**Cross-checking value:** Norwell's Tableau data corrected BOTH newspapers, which agreed with each other and were both wrong (Select Board +16/+12/+11). News figures usually cannot be checked because outlets do not print Blanks; a clerk's tally can be checked against ballots x seats. **When a source reconciles across many independent races and the press does not, trust the source.**

**A distinction worth keeping:** "uncontested" is NOT "no record exists". If ANY race in a town-year carries a real count, the clerk tallied every race and a full return exists somewhere. Plympton and Hatfield each have one contested race with counts, so their `-1` rows are an availability problem, not an absence. Contrast Leverett and Gosnold, which elect at Town Meeting by voice vote — there genuinely are no counts to find.
