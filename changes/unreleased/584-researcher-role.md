---
type: added
issue: 584
pr: 717
date: 2026-11-03
box-skill: none
---

Define the researcher role, Riley (part 1 of 3 for the researcher role). `docs/roles.md` and the concepts glossary describe a read-only role that takes deep dives off the coordinator: it never pushes to a PR branch, builds, reviews or lands, holds no gate, answers with a signed issue comment or a requested design-doc PR, runs on the research engine row, and gets one fresh session per request. The profile validator accepts an optional `[identities] researcher` table (with a required `gh_user`) and a tmux `researchers` cap (integer, at least 1, default 1); `profiles/tmux.toml` names the identity Riley. The brief, spawn path and coordinator rule follow in the next PRs.
