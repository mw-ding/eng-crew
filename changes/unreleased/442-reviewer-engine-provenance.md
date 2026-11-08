---
type: fixed
issue: 442
pr: 1370
date: 2026-11-08
box-skill: none
---

`mdstack spawn reviewer` no longer starts a Claude Code reviewer on a Claude-built PR whose builder engine it could not parse. It reads every `Engine:` line in the PR's commit messages, including one written outside the trailer block (before `Co-Authored-By:`). With none, it uses the PR-body builder marker and the builder run records for the PR or its closing issues. When the engine is still unknown, spawn refuses instead of assuming non-Claude.
