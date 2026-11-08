# profiles

Install-time profiles: the per-axis selection a deployment runs with. Part
of the [module layout](../docs/specs/team.md#4-target-module-layout).

## Contents

| File | Holds |
|---|---|
| `default.toml` | The complete default: GitHub for every concern, Grok Bot environment (portable spec P7) |
| `tmux.toml` | Terminal environment example, layered on the default |
| `session.toml` | Single-session environment example, layered on the default |

## How it plugs in

A target repo's `crew.toml` starts from one of these; `crew-config.py
resolve` layers the default, an org pack, the team file and the project
profile, and `validate` checks the result. Every key and default:
[profile](../docs/profile.md).
