# Transcribing an election return

You are copying a printed table into fields. You are not interpreting it,
tidying it, or completing it. Every judgement you are tempted to make is made
later by code that can be inspected and reversed; a judgement made here is
indistinguishable from the document afterwards.

Read these in order. The first rule outranks the rest.

## 1. Copy. Do not normalise.

Emit `_original` fields and nothing else:

- `name_original` — the candidate exactly as printed. Not Title Case. Not
  expanded. `WM. J. O'BRIEN, JR` stays `WM. J. O'BRIEN, JR`.
- `office_original` — the office heading exactly as printed. Where the heading
  spans two printed rows — `Town Meeting Members` above
  `Precinct 1 - Vote for 6 for 3 Years` — join them with a **single space** and
  keep both. Dropping either half loses the office or loses the seat count.
  A single space and not a separator, because grounding collapses runs of
  whitespace before matching, so a space is what the document's own text
  becomes and any other joiner fails to match it.
- Trim leading and trailing whitespace; never alter whitespace inside a value.
- `district_original` — whatever the document prints for precinct, ward,
  district or region. Empty if it prints nothing.

Canonical names are derived later by a pass that reads only these fields and
never sees the document. That pass can be re-run and corrected. Your
transcription cannot, because once `SELECTMEN` becomes `Select Board` there is
no way to check it against the page.

**A grounding check matches your output against the document character by
character.** Every tidy you apply turns a passing record into a failing one.

## 2. Do not reorder.

Keep candidates in the order the document prints them, including `BLANKS` and
`WRITE-INS` wherever they fall. Do not sort by votes.

Document order is evidence. A return that prints two races in one block is
detectable only from the order and position of its rows; sorted output looks
identical to a correct single race, and the arithmetic cannot tell them apart
either — if one block closes at ballots x k1 and another at ballots x k2, the
merged block closes at ballots x (k1+k2) exactly.

## 3. `num_winners` is SEATS UP, not people who won.

If the page prints `Vote for not more than TWO`, `2 for 3 Years`, or
`Vote for THREE`, then `num_winners` is that number — **even if only one
candidate stood, even if nobody won, even if three were elected.**

Record where you got it in `num_winners_source`, which has exactly four values:

- `printed` — **the return itself** states the seat count. Quote it verbatim in
  `seats_quote`. A warrant, an officers directory or a table of contents
  elsewhere in the report is not the return; that is `derived`.
- `marked` — the return marks winners (asterisks, bold, `ELECTED`) and you
  counted the marks. Say what the mark was in `num_winners_basis`.
`seats_quote` is the printed line that carries the seat count, not the whole
heading — and it counts as `printed` wherever it sits in the contest's own
block, including a subheading above the office name. `Recount Tabulator Final
for 1 seat` is a seat count printed by the return.

- `derived` — neither of the above, and you worked it out from the arithmetic:
  a contest's figures sum to about the ballot count times the seats, so a race
  totalling roughly twice another race's total is a two-seat race. Put the
  reasoning in `num_winners_basis`.
- `null` — you could not tell. **This is a permitted answer and often the right
  one.** `num_winners: null` with a note beats a confident guess, because a
  null is visible to every later pass and a wrong number is not.

`printed` outranks everything downstream, including arithmetic. The other three
are re-checked. Saying which you did is worth more than being right, because a
wrong `printed` is caught and a wrong guess wearing `printed` is not.

**Deriving the seat count is the one place arithmetic is allowed to choose a
value**, and only because the alternative is a number with no basis at all.
It never applies to a vote figure — see rule 4.

## 3a. Precinct columns on a town-wide race

The commonest layout in this corpus prints one town-wide race across a row of
precinct columns and then a `Total` column:

    Precinct                 1    2    3    4   Total
    MATTHEW E. DUGGAN       92   71   48   80     291

That is **one `at_large` contest**, not four `sub_town` contests. The precincts
are how the town counted, not what it elected.

Put the printed total in `votes`, and the precinct figures, in printed order,
in `votes_by_precinct`, with the column headings in `precinct_labels`. Both are
transcription, so both are allowed; neither is derived.

Keeping them is not decoration. The row states its own total, so the precinct
figures let code check the total without a model and without the document —
the only check in this pipeline that can catch a misread digit in a figure that
is otherwise perfectly plausible.

A precinct contest is `sub_town` only when the precinct elects its own officer:
`Town Meeting Members, Precinct 3` is a `sub_town` contest, because Precinct 3
alone chooses them.

## 4. Never compute. Never complete.

Do not emit a total you did not read. Do not emit `ballots_cast` at all — it is
derived from the return and compared against any printed figure, and that
comparison is only a check because you did not supply it.

**You may add figures up in order to REPORT a disagreement. You may never emit
the result as a value.** If a column of figures does not match the total printed
beneath it, both numbers are transcribed exactly as printed and the discrepancy
goes in `problems`. Transcribing a corrected total would destroy the evidence
that the document disagrees with itself, which is often the most useful thing on
the page.

If a cell is blank, empty, illegible or absent, the value is `null`. Not zero.
Not the row total. Not what the arithmetic implies.

A zero written into a blank cell is the one error that no later check can catch:
it is arithmetically consistent, indistinguishable from a real zero, and wrong.
Five records in this corpus had winners' totals invented as the turnout figure
and it took a human reading the page to find them.

If you cannot read a figure, set `votes: null` and put what you can see in
`votes_note` — `"smudged, first digit 1 or 4"`. A described gap is recoverable.
A guess is not.

## 5. Scope is a field, and the word "district" is the trap.

Set `scope` to exactly one of:

- `at_large` — the whole municipality votes.
- `sub_town` — a precinct or ward *within* this municipality. Its figures are a
  part of the town's total.
- `regional_district` — a regional school or fire district spanning several
  municipalities. **Its figures routinely exceed this town's ballots, and that
  is correct**, so it is exempt from the ballot arithmetic.

A regional contest printed inside a town's return is its own record, whether
the figures shown are this town's share or the whole district's. Say which in
`regional_note`.

Getting this wrong is not cosmetic: a `regional_district` contest mislabelled
`at_large` fails arithmetic that should never have applied to it, and a
`sub_town` contest mislabelled `at_large` double-counts the town.

## 6. One annual municipal election.

This document may also contain a state primary, a presidential election, a
special election, town meeting minutes, a warrant, an officers directory and a
salary schedule. Transcribe **only the annual municipal election**.

- A state or federal office — Senator in Congress, Governor, Representative in
  General Court, Register of Probate — is not a municipal race. Skip it.
- A special election has its own date and fills a vacancy. Skip it, and set
  `saw_special: true` so it is not lost.
- A ballot question is not a candidate race. Put it in `questions` if it is on
  the municipal ballot, never in `elections`.

If the section holds more than one election date, transcribe the annual
municipal one and list the others in `other_dates_seen`.

`saw_special` means a **municipal** special election. A state or federal special
is skipped under the rule above and does not set the flag; it goes in
`other_dates_seen` like any other date.

### A recount is the same election, not another one

A recount block carries a later date and often precinct-level figures, and it is
still the annual municipal election — Sterling 2010's return was recounted on
8 June for a single seat. Do not list it as another date and do not merge it
into the original figures.

Transcribe it as its own contest with `is_recount: true`, `recount_date`, and
the office it recounted. Which figures stand is a question about the town's
certification, decided later by somebody who can read the clerk's record; the
transcription's job is to make both readings available rather than to choose.

## 7. Say what you could not do.

Populate `problems` with anything that would change how a reader treats the
record. This is not a confidence score and not an apology — it is the list of
things a human should look at:

- a race where the printed total disagrees with the figures above it
- a candidate whose row is missing a precinct column
- a name you could not read
- an office heading you could not attach to a block of figures
- a block of figures with no office heading at all

An empty `problems` list on a page you found difficult is worse than a wrong
transcription, because it removes the only signal that anyone should look.

`problems` is per-contest. Anything about the document as a whole — no
municipality named, two elections on one page, a heading you could not place —
goes in the record's top-level `document_problems`.

### Marks the document makes that are not figures

Returns annotate. An asterisk beside a name marks a winner; `CFR` marks a
candidate for re-election; a dagger marks a write-in who qualified. These are
printed information and they need somewhere to go, so:

- `elected_marked` — `true` when the row carries a winner mark, `false` when it
  does not, and `null` for any row that is not a candidate (`Blanks`,
  `Write-Ins`, `Totals`), which can never be marked.
  Whether the document marks winners **at all** is a property of the document,
  not of a row, so it goes in `winner_marks_used` at the top level. Without it,
  a page that marks nobody and a row that merely lost are both `null` and
  nothing downstream can tell them apart.
- `annotation_original` — any other mark beside the name, verbatim: `"CFR"`.

`elected_marked` is **not** `num_winners`. It records who the document says
won; `num_winners` records how many seats were up. A race can mark two winners
for three seats, and that difference is a fact about the election, not an error.

## 8. The shape of the output

One JSON **object** per document — not a bare array:

```json
{
  "municipality_original": "DANVERS",
  "municipality_printed": true,
  "date_original": "June 2, 2020",
  "elections": [
    {
      "office_original": "Selectmen - 1 for 3 Years",
      "district_original": "",
      "scope": "at_large",
      "num_winners": 1,
      "num_winners_source": "printed",
      "seats_quote": "Selectmen - 1 for 3 Years",
      "num_winners_basis": null,
      "is_recount": false,
      "precinct_labels": ["1", "2", "3", "4", "5", "6", "7", "8"],
      "candidates": [
        {"name_original": "MATTHEW E. DUGGAN", "votes": 575,
         "votes_by_precinct": [92, 71, 48, 80, 96, 76, 68, 44],
         "elected_marked": false, "annotation_original": null},
        {"name_original": "BLANKS", "votes": 10,
         "votes_by_precinct": [2, 4, 9, 3, 9, 2, 3, 4],
         "elected_marked": null, "annotation_original": null}
      ],
      "printed_total": 1807,
      "problems": []
    }
  ],
  "questions": [],
  "winner_marks_used": true,
  "saw_special": false,
  "other_dates_seen": [],
  "document_problems": ["no municipality named in this section"]
}
```

Rules that follow from the shape:

- `municipality_printed` is `false` when the section never names the town. The
  municipality field exists to disagree with the filename, so an invented value
  silences the only wrong-town detector there is. Say you did not see it.
- `printed_total` is the `TOTALS` line the document prints for the contest, or
  `null`. It is transcription, not a sum you performed.
- `votes_by_precinct` is `null` where the return prints no precinct columns.
- Omit no key **of those listed above**. A key you leave out is
  indistinguishable from a document that said nothing, and those are different
  facts.
- Three keys are conditional and are simply absent where they do not apply:
  `recount_date` (only when `is_recount`), `regional_note` (only when
  `scope` is `regional_district`), and `votes_by_precinct` (only where the
  return prints precinct columns — `null`, not absent, when it does not).
- `municipality_original` is copied exactly as the page prints it. If it says
  `TOWN OF STERLING`, that is the value. The canonical name is derived later,
  and the whole purpose of this field is to be able to disagree with the
  filename.
- `is_recount` is `false` on an ordinary contest; `true` adds `recount_date`.
- `num_winners_basis` is `null` when `num_winners_source` is `printed`, and a
  sentence otherwise.

## 9. What "the document" means

Where you are given both an image and extracted text, **the image is the
document.** Text extraction reorders columns, fuses adjacent races and drops
digits, and does so silently. Where the two disagree, read the image and record
the disagreement in `problems`.

Where you have only text, say so in `document_problems` and transcribe it
anyway. A born-digital return whose text layer is clean is not a lesser source,
but the record must show that nothing was checked against an image, because
"the text was right" and "the text was never doubted" look identical afterwards.

## 10. Small things that recur

- **A heading that wraps.** `office_original` is the whole heading, across
  however many printed lines it occupies, joined with a single space. Stopping
  at the line break drops the seat count, which is usually on the second line.
- **A heading that repeats itself.** `Assessor - One year Unexpired Term - One
  year Unexpired Term` is copied exactly as printed. It is the document's
  duplication, not yours, and tidying it is normalisation.
- **An unheaded final column.** A column of larger figures at the right of a
  precinct table, with no heading, is the total column; put it in `votes`. Say
  so in `problems` — it is a reading of the layout, not something printed.
- **`district_original` for a regional contest.** If the only district text is
  inside the office heading, leave `district_original` empty. Copying it across
  invents a field the document did not print, and `office_original` already
  holds it.
- **A qualifier printed inside a name.** `Lance E. Harris (Write-In)` keeps the
  parenthetical in `name_original`, because it is printed as part of the name.
  `annotation_original` is for a mark set *beside* the name, in its own column
  or margin.
- **A contest with no candidates.** A block with only `Blanks` and `Write-Ins`
  is transcribed as it stands. It usually means nobody stood, which is a real
  and reportable outcome, not a parse failure.
