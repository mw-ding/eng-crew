---
type: added
issue: 652
pr: 658
date: 2026-11-02
box-skill: pending coordinator mirror
---

`scripts/evidence-cli.py` captures CLI, service and API evidence mechanically: a header with proof label, capture SHA and working directory, a copyable `sh` block with optional setup, and the exit code, stdout and stderr in separate sections with scrub notes. Builder briefs now require CLI proof from the helper or the template script, never hand-written, with executable setup and deferred AC evidence in a signed fix review; reviewer briefs make a capture without the header, or one that does not reproduce, one finding with the re-run output. This keeps evidence quality independent of the builder and reviewer models.
