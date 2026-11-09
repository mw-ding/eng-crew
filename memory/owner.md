# Owner profile

How the owner works with the team: standing preferences only. Personal data
never goes here; it lives in the knowledge connector. Change this file only
through a reviewed memory PR (`docs/memory.md`).

## Communication

- Lead with the conclusion, the ask and a short TL;DR; details follow.
- Be concise; skip preamble and recaps the owner did not ask for.

## Decisions

- Owner decisions, grants and away status are recorded on the decision log
  (#985); act on the recorded decision, not on a recollection of it.
- The owner pre-approves every change, round-cap extension and release;
  apply it, record it on #985 and report, rather than asking. Only
  `crew:sensitive` still needs the owner's per-change reason (#985
  c6729351370).

## Work

- An issue is a unit of work, not a PR-sized slice: one PR per issue, split
  into commits (#978).
- Project artifacts (designs, plans, findings) live in the tracker and change
  records, never in external documents.
- Ship an approved release; a newly found non-test fix goes into the next
  one. Re-run a flaky CI job; never waive CI.
- "Full speed" means the profile's FULL SPEED SETUP block: caps 10/10,
  `max_load` 288, `load_high`/`load_low` 18/12 per CPU, `schedule_interval`
  60 s, `schedule_ramp` 5; apply it as is when the owner asks (#985
  c6726893407).
- Batch work that needs a temporary owner resource (such as the Docker
  daemon) first, then pause, so the owner can release it (#985 c6734826673).
