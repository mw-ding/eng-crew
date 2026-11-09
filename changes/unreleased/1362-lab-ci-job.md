---
type: added
issue: 1362
pr: TBD
date: 2026-11-09
box-skill: none
---

CI has an opt-in `lab` job for the M20.1 Linux Docker/SSH lab. It runs only on a PR labelled `lab`, on an ARM64 runner, from the base image named by the `LAB_BASE` repo variable (pinned by digest). It runs the lab setup, every runner scenario and teardown, and keeps the evidence as an artifact. Without `LAB_BASE`, Docker or ARM64 it records an explicit skip and passes. It is not a required check, and every other CI job still runs.
