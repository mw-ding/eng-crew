# Issue template: metrics regression (gate)

Owner: `<CoordinatorBot>`. Filed in the harness control-plane repo
(`<owner>/<control-repo>`) when `scripts/metrics-decide.py` exits 1 (`TRIP`).
Protocol and thresholds: [decisions.md](../docs/metrics/decisions.md). This is
a body template only; nothing here creates an issue or a routine.

Title: `harness: latency/quality regression (<as-of date>)`. Label:
`metrics-gate`. For a per-repo `FOLLOW-UP` (exit 3), use the title
`project: <owner>/<repo> latency/quality follow-up`, drop the gate section and
the label.

## Body

```markdown
## Trip

Verdict: TRIP as of <as-of date> (UTC). Current window <days> days, baseline
the <days> days before. Sensors tripped: <latency | rework | both>.

## Rollup

<paste the "Rollup" table from the metrics-decide.py report>

## Per repo

<paste the "Per repo" table from the report>

## Pull requests to link

- <owner>/<repo>#<n> (<minutes> min, changes=<k>)
- <owner>/<repo>#<n> (<minutes> min, changes=<k>)

## What to fix

<one line from the coordinator: the likely harness cause, or "unknown, needs
diagnosis">. The fix is a harness change in this repo; its PR says
`Closes #<this issue>`.

## Gate

While this issue is open, new `M*` feature issues wait. The coordinator holds
unstarted `crew:ready` `M*` issues with `hold-until-#<this issue>` and does not
release new ones. Open PRs finish normally. The fix, bug and CI fixes and
doc-only corrections are not blocked.

Waiver: only the owner, through `<CoordinatorBot>`, by commenting
`waive metrics-gate: <reason>`. The coordinator then removes the holds and
closes this issue as not planned.

Lift: the gate lifts when the fix PR merges and closes this issue.

Data: `scripts/metrics-refresh.py --days <28>` then
`scripts/metrics-decide.py` (see docs/metrics/decisions.md).
```
