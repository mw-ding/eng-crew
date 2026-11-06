---
type: fixed
issue: 1064
pr: 1069
date: 2026-11-05
box-skill: none
---

`scripts/check-skill-drift.py --project` (render-vs-live mode) now compares each section exactly: any difference in the raw section text, including an edited multi-word command span, a changed HTML comment or appended live-only text, is DRIFT (exit 1), printed with its first differing words as `render:` and `live:`, where it used to pass as WORDING because only single-word code spans and quantities counted as key facts. Doc-vs-skill mode keeps its WORDING tolerance unchanged. Found by the M25 A02 run on #786.
