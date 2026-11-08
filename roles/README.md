# roles

**Axis:** roles (who). Part of the [module layout](../docs/specs/team.md#4-target-module-layout).

## Purpose

Portable role definitions: who each employee is, what it owns, its
procedures, refusals and handoffs. A role package names generic
[actions](../actions/README.md) only, so the same package works in every
environment and harness.

## Contents

| Path | Holds |
|---|---|
| `eng/<role>.toml` | The engineering team's role definitions (coordinator, builder, reviewer, synthesizer, researcher): identity defaults, class, owning seat, escalation, passes, lifecycle ([role registry](../docs/roles-registry.md)) |
| `eng/<role>/routines/` | A role's recurring jobs, one `<routine>.toml` each ([routines](../docs/routines.md)) |
| `seats/<seat>/` | Owner-facing seat placeholders (CEO, CTO, CPO, COO, CDO, CFO) in the role-package shape |
| [seats/TEMPLATE.md](seats/TEMPLATE.md) | What a seat package holds and how to fill it in |

## How it plugs in

The renderer reads the registry and each role's routines and renders one
brief per role for the selected environment. A role references only the
protocol and the actions contract (dependency rule D1). Add a role whose
lifecycle already exists with one definition plus its tests
([Adding a role](../docs/roles-registry.md#adding-a-role)).
