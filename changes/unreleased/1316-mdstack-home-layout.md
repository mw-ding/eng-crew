---
type: changed
issue: 1316
pr: TBD
date: 2026-11-07
box-skill: none
---

**Breaking:** every installed piece now lives in one place, `~/.mdstack/`, with only the repo checkout outside it, and the profile is `config.toml`. The user-level `~/.mdstack/config.toml` is the default: every `mdstack` and `core/crew-config.py` command uses it when given no `--project` and no `MDSTACK_CONFIG`, so `--project` is no longer required. A project-level `config.toml` passed with `--project FILE` stays the secondary option for a separate project-group stack; the two never merge (docs/runtimes/tmux.md, User-level and project-level config). The default layout is `~/.mdstack/` (profile directory: `config.toml`, the `start` and `start-owner` wrappers, `releases/`), `~/.mdstack/state/`, `~/.mdstack/runs/<repo>/` and `~/.mdstack/live/`; `profiles/tmux.toml` carries the `[paths]` block and a tmux bootstrap proposal writes it, taking the repo from the profile directory's git origin, else the current directory's. `mdstack layout --write` now writes `start-owner` beside `start` in the profile directory instead of under the checkout's `.crew/`. Host and runner job roots default to `~/.mdstack`. Bootstrap records the profile copy as `<state>/config.toml`. Doctor, and so bootstrap, now refuse a `state_dir` or `worktree_root` inside a git checkout, while a profile directory that also holds `state/`, `runs/` and `live/` passes. There is no fallback to `crew.toml` or the old `~/crew-home/` and `~/.crew/` defaults (7.x installs are fresh); `crew:` labels, markers and `CREW_*` variables keep their names.
