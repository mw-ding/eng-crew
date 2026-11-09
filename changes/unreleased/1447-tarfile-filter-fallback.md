---
type: fixed
issue: 1447
pr: 1452
date: 2026-11-08
box-skill: none
---

`scripts/crew-install.py` runs on every Python 3.11 again, as the README promises. Both extract sites (the release bundle and the git source's `scripts/` archive) now go through one `extract` helper that passes `filter="data"` only where `tarfile` has it (3.11.4+); on 3.11.0 to 3.11.3, such as Debian bookworm's 3.11.2, the member checks alone gate the extract. Those checks refuse any member that is not a regular file or directory under the expected root, or that has a `..` part, so symlinks, hard links, devices, FIFOs and absolute paths never reach `extractall`. The git source archive had no member checks before and now gets the same ones. This unblocks `crew-lab-host.py activate` in the bookworm lab containers.
