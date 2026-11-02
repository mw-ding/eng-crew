---
type: added
issue: 205
pr: 435
date: 2026-11-01
box-skill: none
---

Add `crew host check` and `crew hosts` for per-project readiness and live host capabilities, prepared projects, reachability and load. Remote checks use a fixed SSH entrypoint contract for the runner in #208; `--fix` requests safe repairs and reports human steps, while missing logins or an unavailable runner keep hosts unready.
