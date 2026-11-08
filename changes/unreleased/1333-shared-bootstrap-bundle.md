---
type: changed
issue: 1333
pr: 1399
date: 2026-11-08
box-skill: none
---

`dev/tests/environments/test-crew-bootstrap.py` runs fewer, cheaper tests. It now runs 58 tests instead of 97: `HarnessTargets`, like `ReleaseSources`, no longer re-runs every inherited `Bootstrap` test. Tests also no longer copy the whole bundle (about 300 files) into every test's temp directory and delete it again: they share one read-only v2.1.0 bundle per process. Only tests that edit the bundle or fetch a release beside it take a private copy with `own_bundle()`, and a cleanup check fails any test that changes the shared bundle without one. The copy and delete cost about 5 seconds per test on a loaded host, where endpoint agents scan every file touched. The `Upgrade` and `UserInstall` subclasses, which edit or rename their bundle, keep a private copy per test.
