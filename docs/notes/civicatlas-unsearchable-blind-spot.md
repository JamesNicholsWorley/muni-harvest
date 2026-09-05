---
name: civicatlas-unsearchable-blind-spot
description: "a pure scan's derived markdown is '<!-- image -->' repeated -- non-empty but wordless, so the gate's headline counted 8 unreadable documents when the real figure is 153, 142 of them ADMITted"
metadata:
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

Found 2026-08-20. `parse_gate.py` ended every run with "8 document(s) have no text layer -- the text-reading guards could not run on them. Unknown, not clean." The true figure is **153**, of which **142 are ADMITted**.

**Why:** the headline counted `sum(1 for s in texts.values() if not s)` — empty strings. But `source_text()` returns *derived* text (hosted markdown, then the OCR cache), and a pure scan converts to the literal string `<!-- image -->` repeated once per page. Taunton 2025's 34 sheets arrive as **1184 bytes of markup and not one word** — a non-empty string, so `not s` was False and it never counted.

**The gate itself was never wrong.** `_searchable()` strips those stubs *before* the length test (it was written for exactly this, naming Alford2025 and Chicopee2021, plus a mojibake test for Dunstable2025's 1255 U+FFFD characters). So the text-reading guards correctly stood down on all 153 and no verdict was ever affected. Only the HEADLINE was wrong — but a blind spot understated 19-fold is precisely how an unread document comes to read as clean ([[civicatlas-silence-is-not-a-default]]).

**How to apply:**
- Report what the guard *actually* refused to read (`not _searchable(s)`), never a proxy for it. The fixed line also prints how many of the blind set are ADMITted, because that is the number that matters: **142 ADMITs rest on the parse alone and never on reading the document.**
- Do not measure this off the PDF's text layer either — that gives 283, over-counting, because many scans do have a real OCR cache the gate falls back to. The question is always "what did the gate get", not "what does the file contain".
- This is the standing residual behind [[civicatlas-ocr-is-not-the-page]]: 142 town-years where a re-read at 400dpi could still change something. Provincetown, Taunton and Lee were three of them and all three were wrong in some way.

---

*Revised 2026-09-05 by the owner during the migration review. The correction is his; the note is otherwise as originally written.*
**The fix is upstream, not in the checker.** Counting how many documents extract to nothing
treats the symptom. `<!-- image -->` should never be written into a markdown store in the
first place: an extractor that produces only placeholders has failed, and writing its output
records a reading that does not exist. Have the extraction step refuse to write a file whose
content is placeholders and whitespace, and send the document to OCR instead. Then a missing
markdown file means "not yet read", which is true and visible, rather than a present file
meaning "read, and it was blank", which is neither.
