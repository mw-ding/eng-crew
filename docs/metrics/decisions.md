# Metrics to decisions

Turns the velocity and quality numbers in [README.md](README.md) into explicit
decisions. When a sensor trips, the coordinator opens one issue in the harness
control-plane repo (`<owner>/<control-repo>`, eng-crew in the pilot) with the
numbers and a per-repo table, and further `M*` feature work waits until a
harness fix ships or the owner waives the gate. Without this, a slow streak or
a wave of reviewer rework changes nothing.

The thresholds below are initial drafts. They are tunable by design: the rule
is to start with this setup, watch for false trips, then adjust (see
[Tuning](#tuning)).

## Two layers

| Layer | What it is | What it decides |
|---|---|---|
| Per repo | Metrics collected for each working project (eng-crew, agentconnect, other watched repos), so unlike workloads are not smeared | A project follow-up issue. Never freezes the swarm |
| Rollup | All watched repos pooled, evaluated from the control-plane repo | The gate: only a rollup trip pauses new `M*` feature work |

Both layers are computed on day one by the same script, from the same data.
Issues are always filed in the control-plane repo, whichever repo tripped; the
issue body links the offending product PRs as `<owner>/<repo>#<n>`.

## Sensors

| # | Sensor | Trips when | Status |
|---|---|---|---|
| 1 | Latency | Median `open_to_merge_min` of merged crew PRs in the current window is more than **30%** above the baseline window's median | Gate sensor |
| 2 | Rework | More than **20%** of merged crew PRs in the current window are rework PRs (proxy below) | Gate sensor |
| 3 | CI rounds | Mean `ci_fix_rounds` per PR, reported only | Informational; no threshold yet |

A lessons-applied rate (a sensor for M11) is not collected yet. The report
prints sensor 3 so a threshold can be chosen from real numbers.

Windows (all tunable): current window = the last **14** days up to the as-of
date; baseline = the **14** days before that. A PR belongs to the window of its
`merged_at` date (UTC). A window needs at least **3** merged PRs in scope
(rollup or repo) before a sensor can trip; otherwise that sensor reports
`INSUFFICIENT` and cannot trip. An empty or thin baseline therefore never trips
the latency sensor by itself.

### Rework proxy and its limits

The CSV has no event order, so the exact "REQUEST_CHANGES after APPROVE" rate
cannot be computed from it. The script counts a PR as **rework** when
`reopened` is `reopened`, or `changes_verdicts` is at least **3** (the round
cap in [protocol section 5](../protocol.md#5-rounds-and-escalation)). Limits:

- A single changes verdict is the normal loop and is not counted. On the
  pilot data about 60% of PRs had one, so counting them would trip permanently.
- It misses a changes request after an approval that the builder fixed in one
  round (one changes verdict, so below the cap).
- `reopened` covers only a reopen event on the PR itself, and blank means none
  seen. Closed-unmerged PRs have no merge time and are left out of both windows.
- A baseline that is a mix of different workloads moves the pooled median.
  Read the per-repo table before acting on a latency trip.

If the proxy turns out to miss real regressions, extend `metrics-refresh.py`
with an ordered column (for example `changes_after_approve`) and switch the
script to it; the sensor and thresholds stay the same.

## Run the check

The CSV needs both windows, so refresh it with a lookback of at least
window plus baseline (28 days). Refresh to a scratch directory to avoid churn
in the committed snapshot:

```sh
python3 scripts/metrics-refresh.py --days 28 --out-dir <state-dir>/metrics
python3 scripts/metrics-decide.py --csv <state-dir>/metrics/prs.csv
```

`metrics-decide.py` is pure computation on the CSV (no network). Options:
`--as-of YYYY-MM-DD` (default today UTC), `--window-days`, `--baseline-days`,
`--latency-pct`, `--rework-pct`, `--rework-changes`, `--min-prs` and `--repo`
(repeatable; default every repo in the CSV plus eng-crew and agentconnect).
It prints a markdown report (rollup table, per-repo table, the PRs to link) and
a last line `VERDICT: <word>`. Exit codes:

| Exit | Verdict | Meaning |
|---|---|---|
| 0 | `OK` or `INSUFFICIENT` | No sensor tripped, or not enough data to trip |
| 1 | `TRIP` | A gate sensor tripped on the rollup: open the gate issue |
| 3 | `FOLLOW-UP` | One repo tripped but the rollup did not: project follow-up only |
| 2 | (none) | Bad usage or unreadable input |

Offline self-test: `python3 scripts/test-metrics-decide.py`.

## Trigger path

**Who files.** In v1 the coordinator runs the check and files the issue by
hand: at the end of each milestone, in its triage window
([protocol section 6](../protocol.md#6-duties-on-wake-all-roles)), and when the
user asks. A scheduled routine may run the same steps later; the stub below is
what it would do. Nothing here creates or changes a live routine.

```text
Run python3 scripts/metrics-refresh.py --days 28 --out-dir <state-dir>/metrics,
then python3 scripts/metrics-decide.py --csv <state-dir>/metrics/prs.csv.
Exit 1: if no open issue labelled metrics-gate exists in
<owner>/<control-repo>, open one from templates/metrics-regression-issue.md
with the report pasted in; if one is open, comment the new numbers on it.
Exit 3: open (or update) a project follow-up issue in <owner>/<control-repo>
for the tripped repo, without the metrics-gate label. Exit 0: stay silent.
Report to <CoordinatorBot>; never hold, label or merge anything yourself.
```

**Where.** Always `<owner>/<control-repo>`. Title for the gate issue:
`harness: latency/quality regression (<as-of date>)`, label `metrics-gate`
(a plain repo label, not a `crew:*` state label; create it once). Title for a
project follow-up: `project: <owner>/<repo> latency/quality follow-up`, no
`metrics-gate` label. Body: [the issue template](../../templates/metrics-regression-issue.md).

**Dedup.** At most one open `metrics-gate` issue. A later trip comments on it
instead of opening another. After a lift, do not file again within one window
unless the new numbers are worse than those in the lifted issue.

## The gate

While a `metrics-gate` issue is open, **new `M*` feature work is blocked**.
Operationally:

1. The coordinator does not add `crew:ready` to new `M*` feature issues, and
   does not assign them in its after-merge routine.
2. For `M*` feature issues already `crew:ready` but not started (no builder
   claim, no PR), the coordinator adds `crew:hold` and a comment
   `hold-until-#<gate issue>`. Work roles no-op on `crew:hold`
   ([protocol section 6](../protocol.md#6-duties-on-wake-all-roles)).
3. Not blocked: PRs already open (they finish and merge normally), the harness
   fix for the gate (its issue and PR say `Closes #<gate issue>` or
   `Refs #<gate issue>`), bug and CI fixes, and doc-only corrections. The
   [protocol freeze](../protocol.md#protocol-freeze) is unchanged: the fix
   lands under the open milestone's rules, and the owner decides if it needs a
   one-off exception.
4. **Builder.** If B1 wakes on an `M*` feature issue that has no `crew:hold`
   while a `metrics-gate` issue is open and the issue does not reference it,
   the builder does not start. It tells `<CoordinatorBot>` ("gate-blocked") and
   stops. This is a backstop; the coordinator's hold is the primary control.
5. **Reviewer-validator and synthesizer.** The gate is not a merge gate. They
   review and merge every PR, including the fix, as usual. The reviewer-validator
   keeps verdict markers accurate (they feed the rework sensor); the
   synthesizer merges the fix like any PR.

**Waiver.** Only the owner waives the gate, through the coordinator (a comment
on the gate issue, or chat that the coordinator records there):
`waive metrics-gate: <reason>`. The coordinator then removes the holds it added,
removes the `metrics-gate` label, and closes the issue as not planned. A waiver
covers the current window; the next trip is evaluated on later data.

**Lift.** The gate lifts when the harness fix merges (the PR closes the gate
issue), or on a waiver. In its `pr-merged` routine the coordinator then removes
the `crew:hold` and `hold-until-#<gate issue>` notes it added and resumes
assigning. The next check confirms the numbers moved. The coordinator never
removes a hold it did not add for this gate.

## Tuning

Expect false trips at first: small windows, one slow spec PR, a quiet repo.
Record each false trip in the issue before closing it as not planned, then
adjust one of: `--latency-pct`, `--rework-pct`, `--rework-changes`,
`--min-prs`, or the window lengths, and note the new values in the
[CHANGELOG](../../CHANGELOG.md). Per-repo thresholds are not supported yet; add
them when one repo's baseline is too far from the rest.

This closes the metrics-to-decisions row of the gap table (issue #86) and
feeds the self-improve sensor. Lessons-applied tracking and the M11 intake are
out of scope here.
