---
type: added
issue: 1026
pr: TBD
date: 2026-11-05
box-skill: deferred to #140
---

The project docs pass now runs (M26.1 P3, `docs/project-docs.md`): with `[docs] enabled`, each `crew watch` scan runs a docs-pass timer that, once `interval_days` passed since the last slot in `docs/pass.json` (at once when a crew wakes with a pass overdue), fetches the default branch, runs `scripts/docs-scan.py` on the project's own checkout and starts `crew spawn researcher --docs-pass`, recording `skipped: scan unchanged` without a session when the scans (head, date and banner ages left out) match the last started or queued pass. `crew spawn researcher --docs-pass` starts a `riley-docs` window whose Item names each repo's scan.json, shares the `researchers` cap and queue, and is refused unless `docs.enabled` is true. The tmux researcher brief gains a Docs pass section that runs stages 2–4 of `docs/project-docs.md` on each scan (duplicated rules, contradictions and removed behaviour; structural drafts, one per unit of work, contradictions as separate correction drafts): read-only, with no edits, PRs, issue filing or labels beyond opening the repo's one `docs:log` issue, `path:line` citations at the head SHA, no re-proposal of a rejected draft until its cited text changes, and quiet passes posting nothing; it stays under the researcher brief's size budget. Protocol §4 defines the `pass=docs-pass` record on each `[Riley/docs-pass]` comment, a note and never a gate input.
