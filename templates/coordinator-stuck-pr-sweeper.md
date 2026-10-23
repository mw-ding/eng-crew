# Coordinator routine: stuck-PR sweeper

Owner: `<CoordinatorBot>`. One scheduled routine per repo. It exists because
event-driven wakes can be missed or can end without progress; the sweep is the
backstop. It is read-only apart from nudges.

## Trigger

```json
{
  "type": "schedule",
  "cron": "17 * * * *",
  "timezone": "<timezone>"
}
```

Hourly at minute 17, around the clock. The minute is arbitrary; pick one that
does not collide with other schedules. Hourly cadence stretches the thresholds
below (see Notes).

## Prompt

```text
Read-only sweep of open crew PRs and crew:ready issues in <owner>/<repo>.
Skip anything labelled crew:hold. Re-read live state every run.

An item is stuck when:
| Condition                                                                              | Threshold | Wake        |
| changes requested (at head, or carried over a merge-up ack), no builder claim or push  | > 30 min  | builder     |
| CI green at head, no reviewer ack or verdict                                           | > 30 min  | reviewer    |
| approved and green at head, not merged                                                 | > 15 min  | synthesizer (if held only for a missing builder pass=watch marker: builder) |
| conflicting with the base, no merge-up                                                 | > 30 min  | builder (merge-up-only brief) |
| CI failed at head, no ci-fix                                                           | > 20 min  | builder     |
| claimed or acked, no output                                                            | > 3 h     | that bot: check worker liveness, restart in a fresh unique worktree |
| crew:ready issue, no PR and no claim                                                   | > 60 min  | builder     |
| open crew PR (builder marker present), no B2 watch marker file and no builder pass=watch marker | > 10 min after PR open | builder (parent turn creates B2; condition name no-builder-watch) |

Nudge by messaging the bot that owns the stage. Do not post to the PR. For
no-builder-watch, ask the builder's parent turn to create B2 for the PR and
verify it; the sweeper cannot create routines. The watch marker file is
<state-dir>/<owner>__<repo>/watches/pr-<n>.b2.

Dedup: keep <state-dir>/<owner>__<repo>/sweeper-state.json keyed by
(item, condition, head SHA). Send at most one nudge per key per 2 hours.
Nudge cap: after the third nudge for the same key with no progress, escalate to
the user (a message, and crew:escalated only if the PR is a crew PR in a loop).
Progress means a new marker, a new head SHA, or a changed label.

Silent when nothing is stuck.
Result goes to: the user, only on escalation.
```

## Notes

- A PR whose last verdict was `REQUEST_CHANGES` stays in the first row after a
  merge-up ack lands at its head: the ack is not a new verdict.
- A `pass=ack` review never counts as approved. After a clean merge-up of an
  approved PR the reviewer posts a formal re-approve at the new head, so a PR
  still behind on that is caught by the "CI green at head, no reviewer ack or
  verdict" row (reviewer wake).
- Detection window. With the hourly cron, the real detection time for the
  30-min `crew:changes` / no-builder-activity row is 30-90 min (a PR can cross
  the threshold just after a sweep and wait almost a full hour for the next one).
  The same applies to the 10-min `no-builder-watch` row. For repos where that is
  too slow, run the sweeper every 30 min, or add a one-off check about 35 min
  after any `REQUEST_CHANGES`.
- `no-builder-watch` uses the same dedup key shape `(item, condition, head SHA)`
  and the same nudge cap as the other rows.
- Thresholds are the pilot defaults (added Oct 19, 2026, after the bottleneck
  analysis). Tune them per repo; keep the order of conditions.
- The state file holds only item numbers, condition names, SHAs and timestamps.
