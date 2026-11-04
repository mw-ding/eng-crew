---
type: added
issue: 374
pr: 775
date: 2026-11-04
box-skill: deferred to #140
---

Add the milestone-close triage sweep (M24 T6, `docs/triage.md`): with `[triage] enabled`, `crew poll` lists each project-repo milestone closed since its baseline under `milestones` in `triage/queue.json`; the watcher's sweep timer starts a sweep at once for a milestone no sweep took yet (unless a queued sweep will take it); `crew spawn researcher --sweep` names the untaken milestones in its Item and records them in `triage/milestones-taken.json` only once its window starts; the researcher brief drafts one intake card per failure class from the milestone's changes verdicts, steers, escalations and near-misses, deduped against existing intake issues, Trigger `milestone-close` (new in `templates/intake-candidate.md`).
