---
type: added
issue: 1324
pr: 1354
date: 2026-11-08
box-skill: none
---

A second independent crew can share a machine with the first, one root each. `~/.mdstack` is now only the default root: with `CREW_ROOT` set, the default config is `<root>/config.toml` and bootstrap's proposal writes that root. An explicitly named config always wins: commands take `--project`, else `CREW_PROJECT` (every role window's own file), else `MDSTACK_CONFIG`, else the root's `config.toml`, and every command that can write prints the file it acts under on stderr as `mdstack: config <path>`. `mdstack install` writes the launcher under the root its bundle sits in, and `--name NAME` links it onto `PATH` under its own name, so it never takes the first root's `mdstack`; `upgrade` and rollback flip only that root's `releases/current`, and `mdstack doctor` checks the profile root's launcher (docs/runtimes/tmux.md, A second root on one machine).
