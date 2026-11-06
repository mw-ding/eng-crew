---
type: fixed
issue: 1072
pr: 1081
date: 2026-11-05
box-skill: deferred to #140 (tmux coordinator template only; Grok Bot renders unchanged)
---

Priority class 1 (a fix for a red default branch) is now reachable: the scheduler's tracker read takes each open issue's title and records the open `main-red` issues as `red_fixes`, and `rank` (so `crew schedule decide`, the target growth check and the summary) defaults to that set, ranking a build of such an issue, and a fix or ci-red round on a PR whose run record names it, ahead of every recheck, merge-up, validation and review. Before, `decide` never passed `red_fixes`, so a red-main fix ranked as an ordinary class 6, 7 or 8 item and could wait behind the review queue whenever the target was tight. The coordinator brief, the protocol land rules and the tmux runtime now title the blocking fix issue `main-red: <summary>`, and the scheduling inputs table lists the new input.
