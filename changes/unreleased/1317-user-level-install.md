---
type: added
issue: 1317
pr: TBD
date: 2026-11-08
box-skill: none
---

A user-level install puts a stable `mdstack` on your `PATH`. `mdstack install`, run from a bundle extracted into `~/.mdstack/releases/`, points `releases/current` at it and writes the launcher `~/.mdstack/bin/mdstack`, which runs `releases/current/cli/mdstack`; it links the launcher into a user directory already on `PATH` (for example `~/.local/bin`) or prints the one line to add, and never edits a shell rc file. `mdstack upgrade --version vX.Y.Z`, or the new `--latest`, then upgrades like an end-user tool: it fetches and verifies the release into `releases/`, re-renders `--project` and every other project whose `install.json` (which now records the project path) runs from that `releases/` directory, and only then flips `releases/current`, so the launcher follows with no `PATH` change; the previous tag rolls back to the bundle already on disk. `mdstack --version` prints the running tag, and `mdstack doctor` warns on a missing or stale launcher and on a `PATH` that resolves `mdstack` to something else (docs/runtimes/tmux.md, mdstack install).
