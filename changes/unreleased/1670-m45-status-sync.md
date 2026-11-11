---
type: changed
issue: 1670
pr: 1683
date: 2026-11-11
box-skill: none
---

The portable spec gains the M45 section (recover runs and preserve queue state) as its status-sync slice: one row per landed item with Status `done` (#1536, #1633, #1639 diagnosis only, #1020, #1005, #631 with #1074, #738, #1480, #1082, follow-ups #1654 and #1665), #1003 `dropped` as covered by #1163, the settled questions (B1's required-check baseline, #1639 as caller error) and its lessons (flaky default-branch tests, environment-dependent bootstrap smoke #1668).
