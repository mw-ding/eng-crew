---
type: changed
issue: 1224
pr: 1264
date: 2026-11-07
box-skill: none
---

Tests and fixtures are organized per module: every `scripts/test-*.py` moves to `dev/tests/<module>/` by the module holding the code under test (`core`, `environments`, `harnesses`, `connectors`, or `scripts` for code not moved yet), with its fixtures beside it, and `crew_testlib.py` and the shared render fixtures in `dev/tests/`. `run-tests.py`, `crew train`'s local checks, `crew runner` and the forge-less host find tests there, and accept a bare test name. `check-repo.py` gains two checks: `test-layout` fails a test outside `dev/tests/<module>/` or a test name used twice, and `deps` enforces the team spec's dependency rules D1–D9 and the runtime-word lint over `roles/` and `protocols/`; in Python a reference is a whole repo path literal, an import of a module package or a module joined into a path. Today's known couplings are listed with a reason in `scripts/deps-baseline.txt`, which only shrinks. The builder brief's local-checks paragraph names `dev/tests/*/test-*.py`.
