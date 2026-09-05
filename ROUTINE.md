# How the QA work runs

Two mechanisms, doing different jobs. Keeping them separate is the whole design:
one is free and deterministic, the other is scarce and needs judgment.

## The gate — GitHub Actions, free, no model

`.github/workflows/qa-gate.yml` runs `qa/layers.py` on every push touching
`qa/`, `src/` or `config/`, and once a week.

It needs no model — layers 0 through 3 are string matching and arithmetic — so
it costs nothing on a public repository and can run as often as is useful. It
does **not** run hourly: the checks only change when the data changes, and a
schedule that reprints yesterday's answer burns minutes to say nothing.

`qa/regression.py` decides pass or fail, and it asks a narrow question: **did any
failure count go up?** The corpus has 2,535 open findings and will for a while;
a gate that failed on any nonzero count would be permanently red, and a
permanently red gate is worse than none because it looks like coverage.

The weekly run has a second purpose. A scheduled workflow in a public repository
is **auto-disabled after 60 days of inactivity**, and a disabled workflow looks
exactly like a clean one. The weekly run keeps it alive and gives a heartbeat to
notice the absence of.

## The grind — a Claude Code routine, scarce, needs judgment

The Max plan allows **15 routine runs a day, minimum one hour apart**. That is
the scarce resource, so it is spent only on work a model is needed for: reading
a document and deciding what a record should say.

`qa/worklist.py` turns the report into an ordered queue — `qa/worklist.csv`,
1,355 town-years, severity first and size second. Size is registered voters from
`config/denominators.csv`, so Boston 2021 (438,041) outranks a small town when
their findings are otherwise equal, but a layer-0 failure anywhere still beats a
note in a city. The size factor is logarithmic on purpose: linear, every city
would sort ahead of every real defect.

Records whose only findings are NOTEs are excluded. A NOTE is "unusual and true"
— it describes the document. It is not work.

### What one run does

1. `git pull`, then read `qa/worklist.csv`.
2. Take the top N rows with `status: open`. Write `in_progress` with the run id
   and **push before starting**, so a second run sees the claim.
3. Work each row. Layer 0 first: no later check recovers from a wrong document,
   so fixing anything else about that record is wasted effort.
4. Record the outcome in `resolution`, set `status` to `done` or `escalated`.
5. Run `python -m qa.layers` and `python -m qa.regression --baseline
   qa/baseline.json`. If a count went up, the run broke something.
6. Append a dated line to `qa/heartbeat.csv` — what was checked, what changed,
   what is still open — and commit.

Step 6 is not bookkeeping. A routine shows green when the session *started and
exited*, not when the task succeeded, and there is no built-in alerting. The
heartbeat is what makes "ran and did nothing" distinguishable from "ran and
found nothing", which otherwise look identical. The corpus already learned this
the hard way: retiring 23 wrong documents once left the coverage numbers exactly
unchanged, and the stillness read as stability.

### Claiming is advisory

Cloud sessions get a fresh clone and there is no lock to take, so the claim is a
row in a file and two runs starting in the same minute could both take it. Runs
are hours apart by design, which is what makes it hold. Do not raise the
frequency without replacing the claim with something real.

### What must never happen in a run

The rules in `CLAUDE.md` apply, and three matter most here because this work is
unattended:

- **Never state the expected value in a prompt.** A previous run of nine agents
  over QA buckets produced two fabricated figures — a turnout invented from a
  document reading "Turnout not reported", and a ballot count taken from a blank
  sample ballot — because the prompt supplied the number and the model
  back-solved to it.
- **A verdict needs a verbatim quote, or the answer is `NOT-FOUND`.**
- **A flag is cleared only after review and documentation**, never because it
  looked like an off-by-one.

## Escalation

Some rows need the owner: a records request, a judgment call about scope, a
document only he can obtain. Those are set to `escalated` with the question in
`resolution`, and they accumulate in the worklist where they can be read.

A mail channel to deliver them is the intended next step — the existing
`EmailNotes` routine already reads Gmail through the REST API on a daily cron,
and roughly half of what a question-and-answer loop needs is already written
there. It needs a `gmail.send` scope, thread correlation, and sender
verification that parses the `From` header rather than matching a substring,
because forwarded mail routinely contains the owner's own address in the body.

Until then `escalated` rows are simply visible in the repository, which is
enough to be useful and cannot silently fail.
