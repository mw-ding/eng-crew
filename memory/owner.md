# Owner profile

Standing owner preferences only; personal data lives in the knowledge
connector. Change only by a reviewed memory PR (`docs/memory.md`).

## Communication

- Lead with the conclusion, the ask and a TL;DR; details follow.
- Be concise; skip preamble and recaps not asked for.

## Decisions

- Owner decisions, grants and away status: act on the decision log
  (#985), not a recollection.
- The owner pre-approves every change, round-cap extension and release:
  apply, record on #985, report. Only `crew:sensitive` needs a per-change
  reason (#985 c6729351370).
- On a design or scope decision, the coordinator applies its posted
  recommendation, records it on #985, reports; the owner reviews later.
  Not for sensitive reasons, owner-shell runs or the coordinator's own
  authority (#985 c6831237295).
- Ask before cutting a release with `**Breaking:**` entries; the owner
  picks the version, may keep a minor (#985 c6789223346, c6814282786).
- Batch owner-only asks (sensitive or gate-contract merge-oks, owner-shell
  runs) in one list, each with a one-line reason; record a per-PR
  merge-ok at each listed head from the bulk reply. A merge-ok never
  supplies missing AC evidence (#985 c6729351370, c6746709060).
- For named milestones only, "all my approvals" or "merge OK for all the
  PRs" means a per-PR merge-ok at each head, template, protocol,
  gate-contract and spec text included; never `crew:sensitive` (#985
  c6783489747, c6789266394, c6789083159, c6832180374).

## Work

- An issue is a unit of work, not a PR-sized slice: one PR per issue,
  split into commits (#978).
- Project artifacts (designs, plans, findings) live in the tracker and
  change records, never external docs.
- Ship an approved release; new non-test fixes go in the next.
  Re-run a flaky CI job; never waive CI.
- Plan few, larger milestones: ~10 small items make one; a second
  only for owner-dependent work (host or owner-shell proofs) (#1879
  c6882853315).
- "Close M<n>" means finish every issue in it, then close it; never defer
  unfinished items to the backlog (#985 c6814376023).
- "Light mode" means caps 3 builders / 3 reviewers with `max_suites = 2`.
  "Full speed" means the profile's FULL SPEED SETUP block: caps 10/10,
  `max_suites = 99`, `max_load` 288, `load_high`/`load_low` 18/12 per CPU,
  `schedule_interval` 60 s, `schedule_ramp` 5; apply as is on ask; stays
  on until the owner says otherwise (#985
  c6726893407, c6696039050, c6755491250, c6757500956).
- "Normal mode" means caps 5 builders / 5 reviewers with `max_suites = 4`;
  scheduler settings unchanged (#985 c6833626503).
- Batch work needing a temporary owner resource (e.g. Docker) first, then
  pause for the owner to release it (#985 c6734826673).
- Express flavor only when the owner names it (item or milestone);
  else the project flavor (standard) (#985 c6777665345).
- Grok Bot work is deprioritized: none admitted or dispatched until
  the owner asks; `mirror = "none"` (#985 c6787615719).
