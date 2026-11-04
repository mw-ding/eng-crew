---
type: added
issue: 779
pr: TBD
date: 2026-11-03
box-skill: deferred to #140
---

The Grok Bot binding gains a cross-runtime limits section. It lists the supported defaults: `lighter_lane = "docs"`, CI-first review, and manual trains that batch two or more ready PRs at once, with members merging one at a time after a red train. It also lists the tmux-only features with the Grok Bot behaviour used instead: the direct lone-PR land waiver, the forge-less runner, the scheduler and role leads, window reaping and the triage timer. A provenance table for #140 AC3 records that #418 and #425 have no mirror deferral record (a gap the #140 render closes, with no owner approval added after the fact) and marks #402, #428, #433 and #436 N/A, since none changes a Grok template, the protocol or roles. Step 7 of the new-repo runbook points at the section. No template changed; deploying the box skills is deferred to #140.
