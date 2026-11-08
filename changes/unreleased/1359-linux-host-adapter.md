---
type: added
issue: 1359
pr: 1426
date: 2026-11-08
box-skill: none
---

The `linux` host OS adapter: the runner as a systemd user unit with `Restart=always`, enabled with `systemctl --user` and lingering asked for (install, start, stop, status, uninstall), procfs start times with a `ps` fallback, and a read-only SSH listener row from `ss`. `mdstack host check` on a systemd host adds a `linger` row that warns while lingering is off. A lab container is supervised only when its image says so: the lab `Dockerfile` writes `/etc/mdstack/supervised`, and then the adapter writes no unit and refuses start and stop; a Linux host with neither systemd nor that file reports `no user manager` instead of falling back. Proof uses fakes only; a real user unit with lingering needs a systemd-capable Linux guest.
