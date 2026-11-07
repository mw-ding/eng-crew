---
type: added
issue: 1234
pr: 1304
date: 2026-11-07
box-skill: none
---

`mdstack migrate --rename-to <owner>/<new>` plans and applies a repository rename for a stopped crew: the state directory `<owner>__<name>` moves, and the profile (its `[repo]` name, quoted slugs and state paths), the operational state files, bootstrap's `install.json` and the home's turn-end guard are rewritten in place. The preview also lists the tmux session and host job roots derived from the repo, and the product names that stay until a release renames them. The GitHub rename and the redirect check stay owner steps, done before `--apply`. The owner-run runbook is `docs/runbooks/repo-rename.md`. The train's mirror check now recognises eng-crew's own checkout by its `cli/mdstack` entry point, not by the repo name, so it keeps firing after a rename.
