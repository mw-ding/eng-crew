# Findings buffer

The live buffer. How to append, when to batch and who owns it are in
[README.md](README.md). Entries use the template there.

## Entries

### Builder per-PR watch (B2) missing or not verified

- **Date:** 2026-10-23
- **PR / repo:** this repo (eng-crew), PRs #35, #38 and #41. See
  [builder-watch-attach](../lessons/2026-10-23-builder-watch-attach.md),
  [watch-handoff-first-run](../lessons/2026-10-23-watch-handoff-first-run.md)
  and [merge-gate-watch-race](../lessons/2026-10-23-merge-gate-watch-race.md)
- **Smell:** The builder's B2 watch was missing, unverified or unreadable. On
  #35 B2 never attached and the PR stalled about 62 min. On #38 the
  `pass=watch` marker carried a 7-char SHA, so the reviewer cross-check could
  not match it. On #41 the PR merged before the B2 hand-off reached the
  builder's parent turn, so no watch or marker existed.
- **Count:** 3
- **Proposed fix layer:** architecture: create and verify B2 in the same turn
  that opens the PR, so no hand-off can lag behind a fast merge. The fixes
  documented so far are prose plus a merge gate: the verified hand-off (#36, fix
  PR #37), one watch identifier and full-SHA markers (#39, fix PR #41), and the
  merge gate requiring the `pass=watch` marker (#43, fix PR #45).
- **Status:** fixed by #37, #41 and #45 (all `documented` in the lessons).
  Seeded as a worked example: three sightings of one smell became three lesson
  files and three fix PRs; under this buffer they would have been one batch
  issue.

### Synthesizer race past open coordinator hold / rereview

- **Date:** 2026-10-29
- **PR / repo:** this repo (eng-crew), PRs #74 and #78. See
  [synthesizer-hold-race](../lessons/2026-10-29-synthesizer-hold-race.md)
- **Smell:** The synthesizer squash-merged while a coordinator hold was open:
  on #78 on a standing doc-only merge-ok before a hold-until took effect, on
  #74 on a prior APPROVE before the requested engine-diversity re-verdict.
- **Count:** 2
- **Proposed fix layer:** prose, because both checks depend on live GitHub
  state and timing; a static check-repo guard keeps the rules in the protocol
  and template. Architecture (the ruleset in
  [merge-enforcement](../merge-enforcement.md)) is the real fix.
- **Status:** fixing -> #81

### No typed runtime evidence for "prove it" (gap-table row 8)

- **Date:** 2026-10-29
- **PR / repo:** this repo (eng-crew), issue #83. See
  [typed-verify-evidence](../lessons/2026-10-29-typed-verify-evidence.md)
- **Smell:** Reviews relied on diff and CI. No shape-specific artifact was
  required, so the validation pass had no fixed proof to check and the
  synthesizer had no evidence to gate on.
- **Count:** 1
- **Proposed fix layer:** CI check for the shape table, prose for judging
  whether an artifact matches a claim (it depends on live PR content).
- **Status:** fixing -> #83

### Long agent runs invisible mid-flight (row 9, runtime / observe)

- **Date:** 2026-10-29
- **PR / repo:** this repo (eng-crew), issue #85. See
  [step-summary-observe](../lessons/2026-10-29-step-summary-observe.md)
- **Smell:** Long builds and tests leave no readable trace until the PR opens,
  so retries are blind and pass claims are unverifiable. Pasting full pane
  scrollback into chat would swamp the other roles instead.
- **Count:** 1
- **Proposed fix layer:** prose plus a thin helper and a fixture test; the
  structural fix (a runtime that emits step events itself) is deferred
- **Status:** fixing -> #85
