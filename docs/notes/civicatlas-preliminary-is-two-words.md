---
name: civicatlas-preliminary-is-two-words
description: "\"preliminary\" names an election and it names a figure; a check that matched the word alone was wrong about 19 of the 20 records it flagged, all of them annual returns printed on election night"
metadata:
  node_type: memory
  type: project
---

`preliminary_in_an_annual_slot` searched the first 600 characters of a document
for `\bpreliminar(y|ies)\b` and reported twenty town-years as preliminary
elections sitting where an annual belongs. Nineteen of them were annual returns.

Massachusetts uses the word for two unrelated things:

- a **Preliminary Election** — the municipal primary that narrows a field.
  Salem, Agawam, Boston, Holyoke hold them. A distinct election, and it must
  never occupy an annual slot.
- **preliminary results** — the unofficial figures of *any* election, read out
  on the night and finalised days later. Every clerk prints this.

The second meaning is what nineteen documents were saying, and they say it in
every possible word order:

    Needham 2026    "Preliminary Results of Annual Town Election 4/14/2026"
    Acton 2026      "Annual Town Election PRELIMINARY April 28, 2026"
    Agawam 2025     "MUNICIPAL ELECTION Preliminary"
    Kingston 2022   "ATE 2022 Preliminary 4/23/2022"
    Carlisle 2024   "Preliminary Election Results May 21, 2024"
    Acushnet 2026   "the figures listed below are preliminary and will be
                     finalized within four days following the election"
    West Newbury    "The Town Clerk announced the preliminary results at 8:05 PM"

**How to apply:** require the word to name the ELECTION, not the figures —
`preliminary` within two words of `election`, and not `preliminary … election
results`, which is how Carlisle 2024 and Holliston 2025 head a full annual
ballot. That is strictly narrower than the old pattern, so it can only un-flag;
it still fires on Salem's own `SPECIAL PRELIMINARY ELECTION MARCH 28, 2023`.

**What is left over.** A clerk who titles a genuine preliminary
"Preliminary Election Results" escapes it. Wording cannot close that, because
Carlisle 2024 uses the identical words for the annual. The distinguishing fact
is not a word at all: a preliminary is held *weeks before* the annual and runs
the *same offices with a longer field*. A date test would decide it; a string
test cannot.

**The twentieth was Salem 2023, and it is a different error.** The file is a
21-page compilation of every Salem election in 2023 and 2024 — special
preliminary, special final, September preliminary, November biennial, then the
2024 state elections. The check read page one and condemned the file. This is
[[civicatlas-empty-parse-is-wrong-doc]] again: never give a compilation a
whole-document verdict. It carries an override, not a weaker check.

Same shape as [[civicatlas-scope-municipal-only]] and the `district` trap: the
corpus keeps being bitten by one word that municipal English uses for two
things, and the fix is always to test the thing rather than the word.
