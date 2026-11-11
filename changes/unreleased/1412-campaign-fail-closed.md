---
type: fixed
issue: 1412
pr: 1677
date: 2026-11-11
box-skill: none
---

Campaign steps fail closed on the assertion forms the new lint proves, and required failing cases stay recorded: a new `scripts/campaign-lint.py` parses each scenario step and refuses an unhandled assertion (a `test`, `[`, `grep -q` or `!` whose exit neither becomes the step's result nor is captured, handled or guarded by `|| exit`), so a failed assertion chain followed by a passing command can no longer read as PASS; the lint is an allowlist of forms whose failure propagation it proves, and any other construct (a brace group other than an unconditional `|| { ...; exit N; }` handler, a subshell that can fail, a backgrounded compound command, `eval`, `trap`, a non-brace function body) is refused by name. `campaign-run.py` refuses such a step before it runs, as well as one that does not parse. A step may record a required failing case as `expected-fail` or `accepted` with a reason, reported as EXPECTED FAIL or ACCEPTED and never as PASS. `check-repo.py` (rule `campaign`) checks against the merge base of `origin/main` that no required case was deleted without a reason in `retired-cases.json`. The lint found and fixed masked assertion chains in the A01 and A18 fixtures; A12, A13, A22, A24, A28 and A32 steps were restructured into the allowed forms with unchanged oracles. Explicit refusal oracles (`rc=$?` captures and declared exits) are unchanged. Remaining failure-propagation forms (an exiting helper called in a pipeline, a backgrounded `exit` in a handler group) are tracked in #1684.
