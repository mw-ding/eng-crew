---
type: added
issue: 1330
pr: TBD
date: 2026-11-09
box-skill: none
---

`scripts/evidence-cli.py` takes `--sha <full head>` and `--root <dir>`, so a capture in a working copy that git does not serve carries the real head and a root-relative cwd in its header instead of `sha unknown (not a git checkout)`. When git reports a HEAD that differs from `--sha`, the helper refuses (exit 2) rather than record the capture. Without the flags the output is unchanged.
