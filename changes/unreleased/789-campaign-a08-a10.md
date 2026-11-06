---
type: added
issue: 789
pr: TBD
date: 2026-11-05
box-skill: none (internal campaign fixtures, fake-forge stub and doc; no template or box-skill changes)
---

The M25 campaign gains the A08 (rank and reservations), A09 (held demand and release) and A10 (rate limit, pressure and floors) scheduler scenario specs in `scripts/fixtures/campaign/` (25.07). They run on real sandbox tmux at level a. `docs/campaign-harness.md` maps scheduler build issues S1–S7 and S9–S11 to scenario steps and excludes S8, which was closed unbuilt. The fake forge answers a `gh ... --label L` query from its own file, so held items differ from the open issue list. A08's last step, a red default-branch fix ranked as class 1, fails until #1072 is fixed; the run filed #1072.
