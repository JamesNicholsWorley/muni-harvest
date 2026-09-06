# The record

One file per town-year, `data/json/<Stem>.json`. A **stem** is the municipality
with spaces removed followed by the four-digit year: `Athol2023`.

```jsonc
{
  "document": {                    // what this document IS, with its own evidence
    "heading_verbatim": "ANNUAL TOWN ELECTION",
    "date_verbatim": "April 24, 2021",
    "election_type": "Regular",
    "election_type_evidence": "The document heading states 'ANNUAL TOWN ELECTION'",
    "offices_on_ballot": 11,
    "is_sample_ballot": false,
    "uncontested_remainder": false
  },

  "ballots_cast": 1204,
  "ballots_cast_source": "derived_from_contests",

  "elections": [                   // one entry per CONTEST on the ballot
    {
      "municipality": "Paxton",
      "date": "2024-05-13",
      "office_original": "SELECT BOARD - 3 YEARS",
      "district_original": "",
      "scope": "at_large",
      "num_winners": 1,
      "blanks_printed": true,
      "stage": "General",
      "type": "Regular",
      "extraction_confidence": 0.95,
      "candidates": [
        { "name_original": "Jane A. Smith", "votes": 612 },
        { "name_original": "Blanks", "votes": 141, "tally_row": true }
      ]
    }
  ]
}
```

## The fields that carry weight

### `*_original` — the transcription

`name_original`, `office_original`, `district_original` are copied from the
document exactly as printed, including clerk typos and inconsistent office
names. **They are never edited.** Grounding checks match against them, so an
edit destroys the ability to check anything — and if a clerk misspelled a name,
the document holds the misspelling and the check must agree with the document.

Canonical forms are derived by a separate pass that reads only `_original`
fields and never sees the document. That pass can be re-run over the whole
corpus whenever the office taxonomy changes, without re-parsing anything.

Corrections live on top, as rows in the adjudication ledger, never by
overwriting the transcription.

### `scope` — at_large | sub_town | regional_district

The word "district" does double duty and that is the whole trap.

- `at_large` — town-wide.
- `sub_town` — a precinct or ward. Divides one town; its numbers sum to the
  town total.
- `regional_district` — a regional school district. Spans several towns, so its
  numbers routinely exceed the host town's ballots, legitimately. **Exempt from
  the ballot arithmetic.**

`NORTH MIDDLESEX REGIONAL SCHOOL DISTRICT COMMITTEE` was once counted as one of
Ashby's precincts, and `Greater Lawrence Technical School` did the same in
Lawrence 2021. Both towns carried a serious-looking flag; neither had anything
wrong. This field exists so nothing has to guess from the office name again.

### `blanks_printed` — which arithmetic applies

Every voter may mark a contest once per seat.

    blanks printed      votes + blanks == ballots x seats, exactly
    blanks not printed  votes <= ballots x seats

An equality test on the second case produces false alarms, and a checker should
not have to infer which case it is from whether it happens to find a Blanks row.

Closure is evidence about figures only. It is structurally blind to a fused race
-- merging two contests preserves `ballots x seats` exactly -- and blind to a
name dropped while its votes were captured. Treat a closing contest as "the
digits are probably right", never as "the record is right".

### `ballots_cast` and `ballots_cast_source`

Derived, never asked for. Every municipality-wide single-seat contest that
prints its blanks sits on the same ballot and implies the same figure, so the
count is computable from the record and asking a model for it would only create
a hallucination site for a value already held.

    derived_from_contests   two or more qualifying contests agree
    stated_in_record        printed in the document and read from it
    quorum_count            counted to establish a Town Meeting quorum
    recorded_vote           from a recorded vote on the floor
    cannot_derive           fewer than two qualifying contests, or no two agree
    results_no_turnout      a complete result, and the document states no turnout

`results_no_turnout` is the state the project already wanted turnout for,
finally given a name: the election is confirmed uncontested, the winners are
known, and the turnout is not. It is not `cannot_derive`. That says a derivation
was attempted and failed, which is true here and is not the point -- Hawley 2025
prints nine offices, eight winners and no count anywhere, and reads as a
successful parse of a document that simply does not state turnout. Recording it
as an absence makes it indistinguishable from a parse that went wrong; naming it
makes it findable when somebody goes looking for the towns whose turnout is
still outstanding.

Beware the number that is nearby and is not turnout. Hawley's page prints "21
voters were in attendance" -- that is the annual town meeting a week after the
election, and taking it would have invented the one figure the record does not
have.

`cannot_derive` is a real answer. Two contests that disagree are a
disagreement, not a derivation, and picking one is how stale data becomes
confident data.

Where a document states a count *and* one can be derived, both are kept
(`ballots_cast_derived`) and the disagreement is a finding.

Gosnold and Leverett elect officers on the floor of Town Meeting. Turnout still
applies there — it is printed in the meeting minutes as a quorum count or a
recorded vote, so only the source differs.

### `votes` and `status`

`votes` is a count, or `null` when no count was printed.

    status: "uncontested"       the office was uncontested; no count printed
    status: "write_in_winner"   won on write-ins; no count printed

These replaced the sentinels `-1` and `-3` in September 2026. A sentinel is a
magic number in a field that otherwise holds real counts: nothing stops a sum
from including it, and a contest that quietly totals negative passes every check
that does not think to look. `null` cannot be summed by accident.

### `outcome_verbatim`

On a contest that elected nobody, quoting what the document says happened.
Hawley 2025 prints "Town Clerk - 3 years / Invalid - Non-Resident": the
write-ins were for a clerk who lives in Charlemont, so none of them counted and
the seat went unfilled. The contest carries no candidates and this field carries
the town's own words for the outcome.

It exists so that "no winner" is never written as a person. A name field holding
`Invalid - Non-Resident` would ground nowhere, sort as a candidate, and read to
every later check as a transcription error.

### `tally_row`

`true` on Blanks, Others and Write-ins. They are lines that count marks, not
people. Inferring this by matching names is why an office name occasionally
ended up treated as a candidate.

### `document{}`

The parser's self-report on **what this document is**, each judgment carrying a
verbatim quote. This is the "is this the right document?" step, answered at
parse time rather than inferred later.

`is_sample_ballot` catches the failure that once produced a ballot count read
off a blank sample ballot. `offices_on_ballot` is the document's own count of
offices, which can be compared against the number of contests actually parsed —
a completeness check that needs no model.

Present on 474 of 1,900 records as of September 2026. Backfill it whenever a
document is touched.

### `extraction_confidence`

The batch parser's assessment of its own reading of a contest. It is metadata
about the reading, not a reading — nothing else can derive it, which is why it
is asked for when `ballots_cast` is not.

## Out of scope

Annual municipal elections only. Specials (`S<Town><YYYYMMDD>`) and
preliminaries (`P<Town><YYYYMMDD>`) are collected and kept in their own store,
documented but not published; a special must never occupy an annual town-year
slot. State, county and federal races are out of scope even when printed on the
same ballot.
