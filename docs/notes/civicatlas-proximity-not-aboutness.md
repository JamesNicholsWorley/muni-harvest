---
name: civicatlas-proximity-not-aboutness
description: "a gate that condemns on what shares the date's window repeats the bug it was written to catch; read the run-up before the date, and a signed return outranks a forecast calendar"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95fbd27a-e675-4c91-b12c-e168765f5970
---

CivicAtlasMA's ATR sweep (1036 finds off 1091 local annual town reports) was
double-checked 2026-08-19 by `src/atr_verify.py`. The sweep held up — **40 of 40
sampled KEEP rows read correct against their own cited page, 0% error**. What the
check actually caught was a defect in the *verifier*.

The gates asked whether a disqualifying phrase appeared anywhere in the ±90-char
window around the date. In a fiscal-year report `Town of Bedford | FY2022 Annual
Report` is a **page footer printed on every page**, including the page carrying
the return. So all 5 `FISCAL_PERIOD` rejections were genuine election returns
condemned by their own page furniture. That is the same defect the verifier
exists to catch one level up — `atr_sweep.quote()` returned the first line
matching a pattern rather than the line the date came from.

**Why:** proximity is not aboutness. Written naively, a gate reproduces the bug
it was built against, because both ask "what is near this?" instead of "what is
this?"

**How to apply:**
- Judge a date on the ~70 characters **immediately before** it (`_LEAD`), never
  the symmetric window. The run-up names the date; the rest is just the page it
  shares. The window is still the right span to *quote* as evidence.
- Keep the heading pattern narrow, and let data pick the arms: a bare plural
  `Elections` matched Dover's `Annual Town Meeting Article 26 Elections` and
  would resurrect 4 wrong finds; a bare `Election Results` decided exactly 2 rows
  corpus-wide and got one wrong (Groveland's report carries the *Whittier*
  regional vocational district election). Requiring `annual` kept the good one.
- **A signed return outranks a forecast.** The MMA calendar is published in
  advance and towns move elections — Savoy's own report says its election "was
  held Wednesday, May 17, 2023" where the calendar had May 9. Log the
  disagreement, don't reject on it. Where no election heading is present the
  calendar's objection stands and correctly held Brookfield's "2024-11-18", which
  was a liquor licence list.
- Net: KEEP 423→431, FISCAL_PERIOD 5→0, **83 finds recover a town-year** (28 fill
  a gap, 55 supply a date). `src/atr_audit_sample.py` re-reads KEEP rows against
  the FULL page and is the reusable check.

Related: [[civicatlas-wrong-artifact-checks]], [[civicatlas-citation-not-source]],
[[civicatlas-ocr-is-not-the-page]], [[civicatlas-known-bad-url-is-a-verdict]].
