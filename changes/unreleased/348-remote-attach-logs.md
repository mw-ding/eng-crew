---
type: added
issue: 348
pr: TBD
date: 2026-11-08
box-skill: none
---

`mdstack attach` and `mdstack logs` now reach a run placed on a role host (multi-device observability). Attaching to a remote window, or to a role whose only run is remote, runs `ssh -t` to the host's new `attach` verb, which attaches to the run's pane in the runner session, read-only unless `--rw`. The crew key line becomes `restrict,pty`; the request travels base64url-encoded in the SSH command, and the entrypoint refuses `attach` without a TTY and every other verb with one. `mdstack attach builders` adds one pane per remote builder showing its host's `capture` reply every 15 s. `mdstack logs` prints the tail of the run's newest step summary from the host's `logs` verb, never raw logs; `-f` stays local only. The lab host's `authorize` writes the new key line, and a new lab `attach` scenario proves it over real SSH. Fixed: on a host where tmux had never run, the runner never got its tmux session, because tmux does not create the directory of a socket named by path and still exits 0. The runner now creates it.
