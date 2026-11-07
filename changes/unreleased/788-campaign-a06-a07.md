---
type: added
issue: 788
pr: 1071
date: 2026-11-05
box-skill: none (internal campaign fixtures and doc; no template or box-skill changes)
---

The M25 campaign gains the A06 (leads, refs and withdrawn handoffs) and A07 (reap and retention) scenario specs in `scripts/fixtures/campaign/` (25.06). They run on real sandbox tmux at level a. A06 covers refs-only send and ack, pending and lost-ack replay reusing one id, completed and withdrawn ids never reported as the new ack, a single dispatch per resend, and a lead restarted once after it exits holding a pending id. A07 covers review, validate, changes and external-merge (#811) terminals in router-first and lead-first order and through `crew kill`, retained verdict sections, a freed reviewer slot admitting the queued pass, the terminal summary, and idle-builder reclaim that leaves a busy builder alone. The run filed #1070.
