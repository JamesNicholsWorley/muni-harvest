# muni-harvest

Harvesting and QA for Civic Atlas MA: annual municipal election results for
Massachusetts towns and cities.

## What the project is

Three questions. If a term does not help answer one of them, it is noise.

1. **Do we have the (right) document?**
2. **Do we have a correct reading of it?**
3. **Is it in scope** — one annual municipal election, one town, one year?

The goal is one correct parse per election. Everything else is scaffolding.

## The pipeline

Collect documents in whatever form a town published them — PDFs, scans, images,
spreadsheets. Record where each came from: a URL and a description. Convert to
readable text with OCR or extraction. Then send **the PDF itself** to the Claude
API and get structured JSON back.
On a scan, where the image and the OCR disagree, the image wins.

PDFs are served from `jamesnicholsworley.github.io/civicatlasma/pdfs/` because
some municipal domains block the API from fetching directly.

## The unit

A **town-year**: one municipality in one year, written as a **stem** —
`Athol2023`, the municipality with spaces removed then the four-digit year. The
stem names every file belonging to that town-year.

Documents are named `<Stem>_d<N>` — `Quincy2021_d0`. A new number is minted only
for new bytes: hash first, and if that sha256 already exists for the stem, reuse
its number. So `_d3` means the third genuinely different document tried for that
town-year.

## Rules for reading a document

**The model transcribes. Code derives. Nothing is asked for twice.**

Every number a model is asked to produce rather than copy is a number it can
invent. `ballots_cast` is derivable from any municipality-wide single-seat
contest, so asking for it creates a hallucination site for a value we already
hold. Derive it. Where the document also prints a count, compare the two — that
is a free check, and it only exists because we derived rather than asked.

The parsing step emits `_original` fields and nothing else. No canonical names,
no office codes, no ballot counts, no confidence scores. If a field is not in
the tool schema it cannot be invented, which is a better guarantee than
instructing a model not to normalise.

`name_original` and `office_original` are the transcription and are **never
edited**. Grounding checks match against them, so editing them destroys the
ability to check anything. Canonical forms are derived by a second pass that
reads only `_original` fields and never sees the document.

## Rules for QA

QA lives in `qa/layers.py` and is organised as four layers, in order, because
no later check can recover from a wrong document.

- **Layer 0 — is this the right document?** Does it name the town, carry the
  year, and support the record at all? Zero support is a wrong document.
- **Layer 1 — is the reading grounded?** Every name and figure findable in the
  document text. Pure string matching, no model judgement.
- **Layer 2 — does the arithmetic hold?** See below.
- **Layer 3 — is it in scope and complete?** One annual election per town-year,
  office count consistent with the town's other years, no state or county races.

Every check returns the same shape: `stem, layer, check, verdict, evidence`.
Evidence is a verbatim quote or a computed comparison, never a bare assertion.

### The arithmetic

In nearly every election, a voter may mark a contest once per seat. The **direction** of a discrepancy
matters more than its size, and the asymmetry is a fact about ballots rather
than a tuned threshold:

    marks >  ballots x seats    impossible at any magnitude. An error.
    marks == ballots x seats    confirmed. An independent witness to the reading.
    marks <  ballots x seats    usually legitimate: blanks or write-ins not tallied.
                                Describe it; do not flag it.

Exact closure is what vouches for figures OCR cannot confirm. A number cannot
satisfy that constraint by accident, so a contest that closes is confirmed even
when its digits are unreadable in the text layer. Record how a figure was
confirmed — `text`, `arithmetic`, `both`, or `neither` — and work the `neither`
pile, which is small.

Deriving the ballot count needs a quorum: two contests that disagree are a
disagreement, not a derivation. Say "cannot derive" rather than picking one.

Sometimes, a heuristic may be useful. A Town Clerk printing the results off-by-one digit
or not including blank votes in the results is still useful information. A results document
could be entirely valid and still fail an arithmetic check, but be within some range 1%, 5%, etc.
A flag on a document should only ever be cleared after careful review and documentation.

### The edge cases

**Scope is a field, not a guess.** The word "district" does double duty and that
is the whole trap.

- `at_large` — town-wide.
- `sub_town` — a precinct or ward. Divides one town; its numbers sum to the
  town total.
- `regional_district` — a regional school district. Spans several towns, so its
  numbers routinely exceed the host town's ballots, legitimately. **Exempt from
  the ballot arithmetic.**

A regional contest printed in one town's return is always separated into its own
record, whether the figures are that town's portion or the whole district's.

**Special elections** keep their own folder and their own
`S<Town><YYYYMMDD>` name, and stay out of the published set. Documented, not
published. A special must never occupy an annual town-year slot.

**Turnout** is wanted only where three things hold: the election is confirmed
uncontested, the winners' names are known, and the turnout is not. Gosnold and
Leverett elect officers on the floor of Town Meeting — turnout still applies
there, but it is printed in the meeting minutes as a quorum count or a recorded
vote, so the source differs. Record which: a quorum count and a ballot count are
both turnout, arrived at differently.

## Rules for changing things

These exist because the project accreted badly once and the cost was real. In
three days one file grew from 1,479 lines to 4,043 with 109 lines ever deleted.

**A data correction is a row, never code.** Corrections go to
`adjudications.csv`, bound to a `source_sha256`. Do not add a `fix_<town><year>()`
function or a module-level fix table. Git already gives you attribution and
history; a per-town function re-deriving a correction on every run is a worse
version of what version control does natively.

**A new check retires one, or states why not.** Never add a check that an
existing check already catches. If you find yourself writing "this is caught
independently, committing anyway" — stop. That sentence is how the last pile
started.

**Checks assert about numbers in the record, never about pipeline plumbing.** If
a check would still pass on a corpus holding arithmetically impossible contests,
it is not earning its runtime. The repository's own diagnosis, as a commit
title: *"The invariants tested the plumbing, so they passed while the numbers
were wrong."*

**Prefer editing to appending.** A commit that only adds lines needs a reason
why the existing code could not be changed instead.

**When the owner names a broken town-year, answer with the class of parse error,
not a patch.** "Springfield 2025 is wrong" is a question about the parser.

## Rules for asking an agent to check something

A previous run gave nine read-only agents QA buckets. The result was unusable for
anything numeric and included two fabricated quotes — a turnout figure invented
from a document reading "Turnout not reported", and a ballot count taken from a
blank sample ballot. Roughly 30% of answers were wrong even on "find a printed
sentence".

So:

- **Never state the expected value in the prompt.** The model will back-solve to it.
- **Require a verbatim quote, or the answer `NOT-FOUND`.** No verdict without one.
- **Do the arithmetic outside the model.**
- **Verify every agent claim against the source before applying it.**

## Rules for absence

**Build an explicit audit trail for gaps; never silently exclude.** Log dead
ends — 404s, paywalls, no-data — so an absence is documented rather than
asserted. Do not trust blank returns: results have been recovered from archived
clerk pages, Tableau workbooks, Google Drive, social media posts, badly-named
files and sequential document-ID trawls.

Watch for the shape of a stuck reading: a corpus-changing operation that leaves
the headline numbers **exactly** unchanged is not stable, it is stuck.

An unattended run must end by writing a dated record of what it checked and
concluded. Absence of that record is then visible, rather than looking identical
to a clean run.

## What must not become public

- **Full text of news articles.** The corpus stores headlines, URLs, dates and
  short snippets — a citation index, not a reproduction. Some sources are paid
  subscriptions. Full article text lives in `civicatlas-private` only.
- **Newspaper issue PDFs.** Complete issues of commercial local papers. Never
  published, not even as a release asset.
- **Anything carrying residents' personal details.** One town's survey appendix
  carries names, street addresses, phone numbers and emails.

## Working notes

- Long jobs run in the background. Do not idle-poll waiting on a shell when
  there is other work.
- Do not run Wayback or CDX queries from a personal machine; this project got an
  IP-level block that survived two days of silence. Use Actions runners.
- One declared writer per shared store. A transient check failure caused by
  another writer is not a defect — verify before repairing.
- Secrets live in Actions secrets, never in the repo.
