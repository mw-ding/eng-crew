---
type: added
issue: 143
pr: 302
date: 2026-10-31
box-skill: none
---

Inline-only evidence design (#143, part 1 of 2, owner decision pending): a
design section in `docs/verification.md` that answers the five open
questions and lists the alternatives considered for each. It recommends:
media only as GitHub user-attachments URLs, attached with
`gh pr create --attach` (`gh` 2.99.0 or later), and for posts after the
change opens a text recipe plus the validator's own reproduction; text
evidence as a copyable repro pair (an `sh` block, then a `text` block with
the exit code, stdout and stderr); size budgets under GitHub's
65,536-character limit; deleting `evidence/` from each tree going forward,
with no history rewrite; and a new Required evidence gate registry row. No
live rule, gate, template or marker changes: protocol §3 and §7, the
registry and the templates change in the build PR.
