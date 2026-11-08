# harnesses

**Axis:** harnesses (how an agent launches and loads). Part of the
[module layout](../docs/specs/team.md#4-target-module-layout).

## Purpose

Everything harness-specific (launch line, trust and first-run dialogs, hooks,
skill loading, resume, idle detection) lives in one adapter per harness, so
shared plumbing never branches on a harness name.

## Contents

| Path | Holds |
|---|---|
| `<harness>/adapter.py` | One adapter each: `claude-code`, `codex`, `cursor`, `muse`, `opencode`, `pi` |
| `crew-harness.py` | Adapter discovery; derives the engine tables the profile schema and the CLI consume |

## How it plugs in

A profile names engines by adapter id in its tier orders. Adding a harness
means adding its adapter and tests, with no edit to a consumer
([harness adapter contract](../docs/runtimes/harness-adapters.md)). Only this
module names harness launch flags, hooks or trust settings (dependency rule
D7). A pack adds one as `harnesses/<name>/adapter.py`.
