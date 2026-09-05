---
name: civicatlas-flag-describes-the-citation
description: "NEEDS_UPGRADE is about the CITATION, not the document — reading it as 'bad document' destroyed Mansfield 2024's correct return and resurrected a condemned presidential-primary URL; but a citation condemned for SCOPE also disqualifies the file"
metadata:
  type: feedback
---

The owner caught this 2026-08-22: **"Mansfield 2024 was not uncitable, it was just unlinked, it should've had the URL."**

`NEEDS_UPGRADE` fires when `native_url` is empty BECAUSE the URL was moved into `known_bad_url`. It is a statement about the CITATION. I read it as "the held document is no good" and replaced the document — with a lead titled `Official-Results-Presidential-Primary-Election-3-6-2024`, which was out of scope AND already condemned on that very row (which is *why* the row said NEEDS_UPGRADE). `data/pdfs` is not git-tracked, so the correct return's bytes were lost; it survived only as `data/raw_ocr/Mansfield2024.txt`. Repaired from the town's own annual report p120 via `src/repair_mansfield2024.py`.

**Why:** an "upgrade" is the same act as a replacement and needs the same evidence. The resurrection rule (proving bytes match CONFIRMS a condemnation) had already been learned once this session and did not transfer, because this time it arrived wearing the word *upgrade*.

**But the inverse is also true, and is a lever:** if a URL was condemned for SCOPE, the document fetched from it is wrong too. Reading all 38 NEEDS_UPGRADE documents (OCR where no text layer) found 27 genuine returns waiting only on a live URL, 9 with no PDF, and 2 state elections (Chester2024, Sheffield2024) — retired.

**How to apply:**
- Before replacing any held document, read the CURRENT one first. `NEEDS_UPGRADE` / `NO_NATIVE_URL` mean *find a URL*; `NO_TALLIES` / `BALLOT_NOT_RETURN` / `EMPTY_PARSE` mean *find a document*. Groton 2022/2026 were legitimate upgrades on exactly that basis; Mansfield was not.
- Scope is neither identity nor date: a presidential primary genuinely names the town, prints the year, and reads as a return. `src/triage_wide_batch.py` now tests the first 400 chars for state/primary vocabulary, and `src/render_town_pages.py` excludes it at the lead stage. The shared classifier does NOT catch it — it answered RETURN_LIKELY and quoted "Presidential Primary Election" as its own evidence.
- `data/pdfs` is untracked. Overwriting a held document is unrecoverable; stage a copy before replacing.
