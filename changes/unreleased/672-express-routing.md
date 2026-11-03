---
type: added
issue: 672
pr: TBD
date: 2026-11-03
box-skill: deferred (tmux mirror deferral; Grok Bot runs express items in the crew lane)
---

Route express changes (X5, the switch in `docs/express-lane.md`). `crew poll` resolves the express lane the way `crew train` does (`crew:express`, the item record and class rules; an unreadable resolution runs the crew lane). For an express change it emits no `new-head` or `fix-at-head`, emits `ci-passed` only with a builder selfgate pass at head, and emits the new `selfgate-passed` event to the synthesizer when a selfgate pass lands with CI green. When the change falls back to the crew lane, poll emits `new-head` at its head so normal review starts. `crew route` never starts a reviewer pass for an express change, so the reviewer lead skips any queued review, and the tmux coordinator brief routes express `ci-passed` and `selfgate-passed` to land, sends `ci-red` without holding, and hands review back on fallback.
