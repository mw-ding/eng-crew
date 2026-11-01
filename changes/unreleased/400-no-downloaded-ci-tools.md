---
type: fixed
issue: 400
pr: 405
date: 2026-11-01
box-skill: none
---

The tmux builder, reviewer and synthesizer briefs and `AGENTS.md` now say: never download or install a binary from the internet, never bypass OS code-signing or quarantine, never use an alternate or mirror package registry; when a CI tool is missing or its registry fails, skip that one local check, say so in the PR evidence, and leave it to CI. The tmux briefs also say role scratch files go in the worktree's `.crew/`, and only `$CREW_ID.body.md` goes in `$CREW_STATE/runs/`, since a stray `runs/*.json` crashed `crew watch` (#369).
