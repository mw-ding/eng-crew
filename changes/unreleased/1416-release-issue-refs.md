---
type: changed
issue: 1416
pr: TBD
date: 2026-11-11
box-skill: none
---

**Breaking:** a release cut PR now links its release issue in a release-only non-closing form, `Refs #N` plus one whole line `Release issue: #N` in the same repository, instead of `Closes #N`, so landing the cut no longer closes the issue before publication; this changes how the Linked issue merge gate is satisfied for a cut. `release-trigger.py linkage` checks the form on the cut PR, and `authorize` reads the issue from the body at publish; a missing, ambiguous or foreign target, or a closing keyword for it, refuses with a correction step. The publish job posts the release URL and only then closes the issue; any earlier failure leaves it open. Ordinary PRs keep `Closes #N`. Migration: write a cut PR body with `Refs #<release issue>` and the `Release issue: #<release issue>` line, not `Closes`.
