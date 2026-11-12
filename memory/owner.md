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
- Ask before cutting a release whose unreleased entries carry
  `**Breaking:**`; the owner picks the version and may keep a minor
  (7.10.0 over 8.0.0) (#985 c6789223346, c6814282786).
- Batch the asks only the owner can answer (sensitive or gate-contract
  merge-oks, owner-shell runs) into one list, each with a proposed one-line
  reason; the owner answers in bulk, and a per-PR merge-ok is recorded at
  each listed head from that reply. A merge-ok never supplies missing AC
  evidence (#985 c6729351370, c6746709060).
- The owner's "all my approvals" for named milestones covers template,
  protocol, gate-contract and spec text; record the merge-ok per PR at
  head. `crew:sensitive` still needs a per-change reason (#985
  c6783489747, c6789266394, c6789083159).

## Work

- An issue is a unit of work, not a PR-sized slice: one PR per issue, split
  into commits (#978).
- Project artifacts (designs, plans, findings) live in the tracker and change
  records, never in external documents.
- Ship an approved release; a newly found non-test fix goes into the next
  one. Re-run a flaky CI job; never waive CI.
- "Light mode" means caps 3 builders / 3 reviewers with `max_suites = 2`.
  "Full speed" means the profile's FULL SPEED SETUP block: caps 10/10,
  `max_suites = 99`, `max_load` 288, `load_high`/`load_low` 18/12 per CPU,
  `schedule_interval` 60 s, `schedule_ramp` 5; apply it as is when the owner
  asks. Full speed stays on until the owner says otherwise (#985
  c6726893407, c6696039050, c6755491250, c6757500956).
- Batch work that needs a temporary owner resource (such as the Docker
  daemon) first, then pause, so the owner can release it (#985 c6734826673).
- Express is an available item flavor, used only when the owner names it
  for an item or milestone; items default to the project flavor
  (standard) (#985 c6777665345).
- Grok Bot work is deprioritized: nothing Grok Bot-specific is admitted or
  dispatched until the owner asks; this install sets `mirror = "none"` (#985
  c6787615719).
