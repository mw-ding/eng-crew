---
type: changed
issue: 1182
pr: TBD
date: 2026-11-06
box-skill: none
---

Each harness is now one adapter module, `scripts/harness.d/<engine>.py`, holding its role and coordinator launch and resume, permission modes, trust and preflight checks, process, dialog, busy, transient-error and composer rules, login check and install pointer. `scripts/crew-harness.py` discovers the modules and derives the profile's engine and coordinator choices, the executable aliases, the `crew bootstrap --harness` choices and the built-in install targets. `crew spawn`, `crew up`, `crew upgrade` reload, `crew doctor`, `crew status`, `crew watch`, `crew send` and remote readiness read the adapters and no longer name a harness, so adding a harness means adding its module and tests. Contributor-tier and engine-independence policy stay in the core, and existing harnesses behave as before. OpenCode becomes a schema-only adapter with no interactive launch, as it was before.
