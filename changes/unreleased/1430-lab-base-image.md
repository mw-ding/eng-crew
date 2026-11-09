---
type: added
issue: 1430
pr: 1431
date: 2026-11-08
box-skill: none
---

The M20.1 local lab has a base image recipe: `environments/terminal/remote/lab/base.Dockerfile` builds `LAB_BASE` from the official `debian:bookworm-slim` pinned by its `linux/arm64` manifest digest, adding only Python 3.11, git, tmux, the OpenSSH server and procps and deleting the package's SSH host keys. The ref built on the owner's Docker Desktop is recorded in `environments/terminal/remote/lab/base.ref`, and `docs/runtimes/multi-device.md` gives the rebuild and re-pin commands. The lab image builds with the classic builder (`DOCKER_BUILDKIT=0`), because BuildKit resolves a digest-pinned `FROM` against the registry and the base is never pushed.
