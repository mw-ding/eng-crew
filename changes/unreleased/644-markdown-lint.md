---
type: added
issue: 644
pr: 655
date: 2026-11-02
box-skill: pending coordinator mirror
---

Builders can now catch common markdownlint failures locally without the binary: the new dependency-free `scripts/check-markdown.py` covers MD001, MD003, MD009, MD012, MD018, MD022, MD031, MD032, MD040, MD047 and MD056 (the rules this repo configures and has failed in CI, such as MD018 and MD056). It checks the changed `*.md` files by default (`--all` for every tracked file) and prints `path:line rule message`. `check-repo.py` runs it on every tracked `*.md` file as a new `markdown` check, so the targeted local set and the tmux builder brief pick it up without an extra step. The whole repo passes, and CI's markdownlint stays the authority (`scripts/README.md#markdown-lint`).
