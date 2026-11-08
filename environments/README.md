# environments

**Axis:** environments (where and how the team runs). Part of the
[module layout](../docs/specs/team.md#4-target-module-layout).

## Purpose

An environment runs the team machinery (wake, spawn, teardown, delivery,
liveness) and implements the generic [actions](../actions/README.md) with
its own tools. Roles never depend on which environment runs them. Older docs
call an environment a *runtime*; the [runtime contract](../docs/runtimes/README.md)
(C1–C9) is what each one answers.

## Contents

| Path | Holds |
|---|---|
| [terminal/](terminal/README.md) | The terminal environment: this project's owned fast lane and the reference implementation of the actions |

The hosted-bot and single-session environments are documented as bindings
([Grok Bot](../docs/runtimes/grok-bot.md), [session](../docs/runtimes/session.md));
their brief templates are still under `templates/runtimes/`.

## How it plugs in

The profile's `[runtime] name` selects the environment. An environment may
use the core libraries and reaches tools of record only through connectors
and harnesses through their adapters (dependency rule D3). A pack adds
environment defaults as `environments/<name>/defaults.toml`
([pack plug-ins](../docs/packs.md#pack-plug-ins)).
