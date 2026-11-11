---
type: security
issue: 397
pr: 1629
date: 2026-11-10
box-skill: none
---

Coordinator briefs (tmux, session and the Grok Bot routines) now include a
secret-retrieval rule: never suggest a command that prints a secret value,
since output the owner runs through a harness shell passthrough such as `!`
enters the transcript. Coordinators give a clipboard pipe or the revealing UI
instead and verify by fingerprint, length or last 4 characters. The bootstrap
design's secrets table records the rule.
