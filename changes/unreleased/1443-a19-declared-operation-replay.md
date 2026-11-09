---
type: added
issue: 1443
pr: TBD
date: 2026-11-08
box-skill: none
---

Campaign scenario A19 replays every declared harness and session backend operation (#797). `dev/tests/scripts/fixtures/campaign/a19/replay.py` discovers the shipped adapters and reads the declared rows from `docs/runtimes/harness-adapters.md` and `docs/runtimes/session-backends.md`. `a19/ledger.json` must give each adapter and row a spec-linked oracle that the named fake-binary tests replay, a default, or a quoted gap or unsupported entry. It also records the refusal and ambiguous cases and the Grok Bot runtime gaps, including C1, C2, C3 and C5, which the owner accepted under #150. The run fails on a gap claimed as conformant, a missing row or adapter, a stale quote or an unknown test. `docs/campaign-harness.md` lists A19 and documents the scenario.
