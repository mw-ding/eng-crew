---
type: changed
issue: 380
pr: 392
date: 2026-11-01
box-skill: deferred to #140
---

Start tmux review on each opened or pushed head alongside CI, combine held CI failures with review findings in one builder handoff, and treat CI as information during review and validation. CI green at head remains a merge gate. Update the reviewed protocol and declare the Grok Bot review-start gap; live Grok Bot impact is none until mirrored (deferred to #140).
