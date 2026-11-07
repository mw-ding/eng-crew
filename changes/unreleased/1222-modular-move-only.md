---
type: changed
issue: 1222
pr: 1261
date: 2026-11-07
box-skill: none
---

The crew CLI and its modules move out of `scripts/` into the team spec's module layout, with no behaviour change: `scripts/crew` to `cli/crew`; `crew-config.py`, `crew-render.py` and `crew-roles.py` to `core/`; the command modules, session discovery, process helpers, session adapters and remote call to `environments/terminal/` (`crew.d/`, `sessions/<backend>/adapter.py`, `remote/`); harness discovery and one adapter per harness to `harnesses/` (`harnesses/<engine>/adapter.py`); and the GitHub repository checks to `connectors/github/`. Every old path is a compatibility shim for one release that runs the moved file, and an adapter left in the old `scripts/harness.d/` or `scripts/session.d/` is still discovered for that release, so `scripts/crew`, the Stop hook, `$CREW_BIN`, the remote forced command and every documented `scripts/...` command keep working, and briefs render byte-identical except the builder's shared-plumbing list, which now names the new paths. Protocol docs, templates, role definitions, packs and the repo QA and release scripts stay where they are for now.
