---
type: added
issue: 636
pr: TBD
date: 2026-11-02
box-skill: none (design doc only)
---

Express lane design doc: an opt-in `express` flavor where one builder builds, self-reviews and tests end to end, and the change lands on green CI with no independent review or validation. It scopes the floor exceptions to `crew:express` changes (F4's verdict post and I1, plus I2 only when the `selfgate_engine` flip is `same`), excludes sensitive and spec items unless the owner overrides per item, and defines the self-gate loop that loads the reviewer rubric in a fresh sub-session, the signed `pass=selfgate` record, the §7 express gate row, tmux routing, trade-offs, per-lane metric columns and build issues. Design only: it adds no rule until its build issues land.
