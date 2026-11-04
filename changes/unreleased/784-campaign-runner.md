---
type: added
issue: 784
pr: 815
date: 2026-11-04
box-skill: none (internal campaign script and doc; no template or box-skill changes)
---

`scripts/campaign-run.py` is the M25 reusable scenario runner (25.02). It runs the campaign guard check first, selects scenarios by `--scenario Axx`, runs public-CLI steps and explicit deadline-bound completion waits, and writes durable results that keep PASS, FAIL, BLOCKED, LIMITATION and NOT RUN distinct, with each command's own exit, stdout and stderr recorded apart from the capture. A seed fixes the scenario order and the children's `CAMPAIGN_SEED`; `--rerun RESULTS` replays the same selection and seed. `docs/campaign-harness.md` documents the runner.
