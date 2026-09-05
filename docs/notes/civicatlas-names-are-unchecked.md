---
name: civicatlas-names-are-unchecked
description: "every CivicAtlas check tests NUMBERS (ballots x seats, printed totals) and nothing ever tested NAMES, so garbled and missing candidates pass clean; the test is whether each published surname appears in the held source text"
metadata: 
  node_type: memory
  type: project
  originSessionId: fc3c6304-5ac7-4b88-b6ac-8e298e484dab
  modified: 2026-08-21T03:14:40.948Z
---

The 2025 readiness pass found the corpus's real blind spot: **arithmetic validates numbers,
and nothing validated names.** A record can close perfectly on ballots x seats while its
candidate names are OCR garbage and an entire candidate is missing.

Brockton 2025 (city of ~105k) passed every structural and arithmetic check with 6 of 7
Councillor-At-Large names wrong and an 8th candidate absent entirely. Actual:
Winthrop H. Farwell Jr / David C. Teixeira / Jeff Charnel / Carla M. DaRosa /
Matthieu C. Delisme / Joseph Edwald Francois / Judith Nelson / Michael Nunes.
Record had "CHRISTOPHER H. FARWELL", "JEFF CHANEL", "MELISSA M. DIROSA",
"MATTHEW C. DELISHE", "DOROTHY-NELSON-SON", and no Nunes.

**Cause:** big-town returns are wide precinct GRIDS whose candidate names are printed as
ROTATED (vertical) column headers. Text extraction returns the digits fine and turns the
headers into noise (`Cl:'., _,_, w s c2`). Numbers survive, names do not. Render the page
and `.rotate(-90, expand=True)` to read them.

**The detector** (cheap, run it over any year): for each published record, take every
candidate name that is not Blanks/Others/Write-in, and ask whether any token of >=4 chars
appears in the held derived text. Score = fraction found.
Over published 2025: 319 checkable, **16 scored under 50%**, and that list was almost pure
signal. It separates into three kinds, which must not be conflated:

1. **Genuinely wrong document** — and it proves some WRONG-DOC adjudications are REAL, not
   stale debt as `published_without_open_wrongdoc` assumes: Granby's source is the
   *nomination papers notice* (dated 2/10/2025, pre-election), Tisbury's is a
   *November 3 2020 presidential voting guide*, Hopedale's is a *"DATES TO REMEMBER"*
   calendar.
2. **Right document, unreadable extraction** — Brockton (rotated headers), Brewster (pure
   OCR noise), Canton (31 words of digits), Taunton (markdown is `<!-- image -->` repeated),
   and partially Newton / Needham / Norwood / Milford.
3. **Right data, wrong citation** — Egremont's data is correct (it came from the
   Berkshire Edge article shared with Great Barrington) but its indexed source is a
   Community Preservation Act story. See [[civicatlas-citation-not-source]].

**False positive to expect:** a record you just re-extracted still points at the OLD derived
text, so it scores low for a good reason. Exclude anything replaced in the same pass.

Related: [[civicatlas-arithmetic-cannot-see-a-lost-name]] (sum==printed proves you read the
NUMBERS not the names) — this is that lesson generalised into a runnable corpus-wide test.
Also [[civicatlas-unsearchable-blind-spot]] (wordless markdown) and
[[civicatlas-ocr-is-not-the-page]] (open the image before believing the text layer).

**What a low score MEANS.** It means "a human must look at the rendered page", not "the data
is wrong". Brockton still scores 5% AFTER being corrected, because a text layer physically
cannot represent a rotated header — the correct names were read off the image. So the score
is a triage queue for visual review; clearing an entry means recording that it was reviewed,
not making the number go up.

**Brockton, resolved.** Re-read from rendered images: 16 races, every one closing exactly on
ballots x seats (at-large 53864 = 13466 x 4). The old record's failure was a **one-position
shift of names against numbers**, plus the top vote-getter missing. Consequence, which is the
argument for taking this class seriously: the old record would have published the WRONG
WINNERS — Francois named a winner and DaRosa omitted.
  old top-4: Chanel 5663, Farwell 5282, Teixeira 5021, Francais 3524
  true top-4: Teixeira 7025, DaRosa 5563, Farwell Jr 5232, Charnel 5021

**The shift class recurred — it is not a Brockton one-off.** Deerfield 2025 had the identical
failure: a vertically-set one-page return read one row out of step, so every office carried the
NEXT office's candidates, plus a phantom TOWN CLERK race not on the ballot and a duplicated
ASSESSOR. Two vote totals were also wrong (866 for 998, 886 for 988).
**The detector that catches it is arithmetic, not names:** within a town, take town-wide races
that print a Blanks row, compute total/seats, take the modal value as ballots cast, and flag
races below it. Deerfield's shifted races could not close; the rebuilt ones all hit 1,376 exactly.

**Same sweep found a different, larger defect — a dropped hand-count row.** Needham's townwide
half prints each candidate's machine count and a separate `H/C` row beneath it; the parser took
only the machine row, undercounting EVERY candidate and every Blanks row in all 13 townwide
races. +4,461 votes recovered. Provable because the Town Meeting half of the same return prints
its own "Candidate Total" column = machine + H/C.

**Do not over-fix this signal.** Of 22 towns flagged, only 2 were defects. The rest are
source-side clerk arithmetic (1-14 votes), blanks reported per ballot rather than per mark in
multi-seat races, or a printed "vote for N" that correctly outranks the arithmetic
(Topsfield, Wilbraham). See [[civicatlas-seats-up-not-winners]].
