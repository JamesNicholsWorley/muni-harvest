---
name: civicatlas-blocked-is-a-tool-verdict
description: "BLOCKED/403 describes our client, not the town; browser-first transport turns ~30% of a worklist from research back into mechanics, and HOLD blocks should always be grouped by flag-combination first"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Recovering native_urls 2026-08-19: `requests` returned HTTP 403 on **20 of 69**
town-years. Those had sat as BLOCKED since the first pass. Every one of those
hosts has served this project a real page through the stealth browser
(`sync_to_github._browser_page`). So a third of the worklist was gated behind a
*transport choice*, not behind anything about the corpus.

**Why:** BLOCKED, 403, a connection timeout, and a sub-1200-char WAF interstitial
are all statements about our tool. Filing any of them as "no document" converts a
tooling gap into a false fact about a town — the same error class as
[[civicatlas-citation-not-source]] and [[civicatlas-ocr-is-not-the-page]].

**How to apply:**
- Make the browser the **default** transport for municipal hosts, not the
  fallback. Two routes cover the shapes: `context.request.get` (inline PDF, keeps
  the browser's TLS fingerprint) and `grab_download` (Content-Disposition
  attachment, where Playwright aborts navigation).
- Keep the acceptance test unchanged when changing transport: accept a URL only
  on `sha256(fetched) == sha256(held PDF)`. Better reach must never mean looser
  proof — the candidate logs are full of wrong-town lines (Berlin2026's best
  candidate points at shrewsburyma.gov).
- Stop re-implementing fetch+retry+threshold in one-off scripts. One shared
  helper returning OK / UNCHECKED / ABSENT, which can *never* return ABSENT for a
  403, timeout, or thin page.
- **Group any HOLD block by flag-combination before touching it.** 62 of the 75
  2026 holds carried a single flag (NO_NATIVE_URL). Holds are a handful of
  classes wearing 283 faces; one `Counter` over `hold_flags` finds the leverage
  before any research starts.
- When printing a page for diagnosis, slice from a content anchor (e.g. `You are
  here`), never the first N chars — on these CMS themes the head is all nav, and
  a truncated dump looks exactly like an empty page.
