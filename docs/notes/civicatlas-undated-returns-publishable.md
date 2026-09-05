---
name: civicatlas-undated-returns-publishable
description: "owner's rule: an undated return publishes if you verify the election AND FIND the date; implemented in parse_gate as document.date_corroboration with strength corroborated (inferred does not qualify); plus the DocumentCenter id/title mismatch trap"
metadata:
  node_type: memory
  type: project
---

2026-08-24. **1792 published, 92.3% town-years / 97.8% people-years, 1 hold.**

**THE OWNER'S RULE, now in the gate.** A return that prints no date may still be published
if (1) it is verifiably the right election and (2) the actual date can be FOUND. Implemented
as `_corroborated_date` in `src/parse_gate.py`: a `document.date_corroboration` block naming
the same date, quoting evidence, `strength: corroborated` -> NOTE `DATE_FROM_CORROBORATION`
instead of holding on DATE_MISSING / DATE_NOT_ON_PAGE / DATE_UNEVIDENCED.
**`strength: inferred` deliberately does NOT qualify.**

Three shapes of evidence qualified, all re-checkable by someone else:
- **the town's own file naming, validated against a year we already publish** — Holbrook's
  `View/239/April-6-2024-Town-Election-Results` matches our published 2024-04-06, so
  `View/1678/2026-44-Annual-Town-Election-Results` is 4 April 2026
- **a date inside the return's own filename** — Merrimac's `...-Local-Election-512023`
- **publication stamp + the article's own weekday** — "Monday's annual town election" filed
  Tuesday 7 May 2024; also Scituate ("Saturday's", filed Sun 7 Jun 2026) and Mashpee
  ("Saturday's", filed Sun 12 May 2024)

What does NOT qualify: Groveland 2021, whose date comes only from its town voting the first
Monday in May for five straight published years. Persuasive, still a pattern, still held.

**A DOCUMENTCENTER ID AND ITS TITLE CAN DISAGREE.** Oakham 2023 cited
`/DocumentCenter/View/302/Fy2023-Annual-Town-Report-PDF`; the file at id **302** is
"Annual Report Fiscal Year **2021**". The id resolves, the title is decoration — I had
concluded "the report only has 2020 elections" and the owner asked why, which is what
exposed it. Probing the id space gave 302=FY2021, 303=FY2022, 304=FY2023, 305=FY2024. Neither
the real FY2023 nor FY2024 contains a 2023 ANNUAL election (FY2023: Sept-2022 special ->
Nov-2022 state; FY2024: Sept-2023 SPECIAL -> May-2024 annual), so Oakham may not have held one
in 2023 -- a `no_election` lead, not a gap.

**I WAS WRONG ABOUT TWO "WRONG DOCUMENTS".** Princeton 2023's crop holds BOTH the Nov-7
special state election and "ANNUAL TOWN ELECTION MAY 8, 2023" -- I read the first heading the
scanner surfaced and stopped; cropping to the annual page alone admits it. Plympton 2024's
annual report was already fetched and sitting in `source_parts` as a SECONDARY while the
town-year read no_source. **Re-read before disposing.**

**THE ATR SWEEP WAS SCOPED WRONG.** `find_atr_pattern_gaps` only considered towns that already
had an ATR-sourced published year -- 30 towns. `src/sweep_all_town_atrs.py` over every open
town-year found **67 of 100 open towns cite NO annual report at all**, which is exactly the
population the first pass could not see (Uxbridge, Dudley, Tyngsborough, Norwell, Brewster,
Plainville all publish theirs). Choose the population from the QUESTION, not from what the
corpus already happens to record.

Related: [[civicatlas-atr-is-a-town-habit]], [[civicatlas-a-hold-cannot-be-relabelled]].
