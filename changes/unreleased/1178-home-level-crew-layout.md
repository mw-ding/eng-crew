---
type: added
issue: 1178
pr: TBD
date: 2026-11-06
box-skill: none
---

A crew can now live in a home-level layout under one movable root. `paths.checkout` names the git checkout that spawn, train, host prepare, the docs timer and bootstrap's `.crew/` exclude use, so the runtime home (`~/crew-home`) need not be a git checkout; it defaults to the profile's directory. `paths.root`, which a set `CREW_ROOT` overrides, resolves each relative `state_dir`, `worktree_root`, `live_dir`, `eng_crew` and `checkout` under it, so a later move such as `~/.mdstack/` changes one value. `crew layout` prints the resolved layout and `--write` writes the one-command `<home>/start` and `<checkout>/.crew/start-owner` wrappers, never user-level config. `crew down --preserve` stops the watcher and panes but keeps every run's work, and `crew migrate --project OLD --to NEW` previews and, with `--apply`, performs the relocation: state, live and registered worktree moves, operational path rewrites that keep message ids and reconcile watcher offsets, the settings copy, a journal with rollback commands and a path map, with Claude Code memory and trust left as owner steps.
