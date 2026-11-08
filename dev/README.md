# dev

Repo QA for eng-crew itself; nothing here ships to a target repo's roles.
Part of the [module layout](../docs/specs/team.md#4-target-module-layout).

## Contents

| Path | Holds |
|---|---|
| `tests/<module>/test-*.py` | Tests per module under test (`core`, `environments`, `harnesses`, `connectors`, or `scripts` for code not moved yet), with fixtures beside them |
| `tests/crew_testlib.py`, `tests/fixtures/` | The shared test helpers and render fixtures |

## How it plugs in

`scripts/run-tests.py` runs the suite, and `scripts/check-repo.py` enforces
the test layout. The guard scripts (`check-repo.py`, `check-markdown.py`,
changelog, release and metrics tools) still live in
[scripts/](../scripts/README.md). Which tests a change runs:
[verification](../docs/verification.md) and [CONTRIBUTING](../CONTRIBUTING.md).
