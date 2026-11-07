# Role registry (design)

> - **Status:** built
> - **Applies to:** the engineering role definitions `roles/eng/<role>.toml`
> - **Current rules:** [protocol](protocol.md) for gates and markers; [roles](roles.md)
> - **Built:** [Schema](#schema) and [Validation contract](#validation-contract) (#317, #318); the validator, renderer and tmux runtime read the registry
> - **Design only:** none; [Hard-coded locations to replace](#hard-coded-locations-to-replace) is the migration inventory, kept as history
> - **Last checked:** 2026-11-04 at `217cec5`

`roles/<domain>/<role>.toml` describes one role of a domain as data (roadmap
15.7, [#317](https://github.com/mw-ding/eng-crew/issues/317), part of #110).
Each file is that role's one authored definition, and its file stem is the
role ID. The registry is the union of a domain's files, in `rank` order with
unranked roles after, by ID (#1185).
This schema records today's four orchestration roles and the read-only
researcher (#584). `eng-backend`,
`eng-web` and `eng-infra` are worker areas, not extra runtime roles.
The profile validator, renderer and tmux runtime read the engineering registry.
The [protocol](protocol.md) still owns gates and markers.

## Schema

TOML 1.0, Python 3.11+ `tomllib`: one file per role, each a closed top-level
table starting `schema_version = 1`. Domain and role IDs match
`[a-z][a-z0-9-]*`; role IDs are data, not an enum compiled into the machinery.
A selected domain has one registry, with no layering or cross-domain relations
in this version. Every key below is required unless marked optional.

| Key | Type / meaning |
|---|---|
| `schema_version` | Integer `1`. |
| `rank` | Optional positive integer; registry order. Unranked roles follow the ranked ones, by ID. |
| `display_name` | Nonempty string; fallback name, overridden by the identity's profile `name`. |
| `identity_key` | String naming an `identities.<role-id>` profile table; login stays in the profile. |
| `marker_role` | Nonempty string used in existing markers; reviewer uses `reviewer-validator`. |
| `passes` | Ordered, nonempty list of distinct pass IDs; first is the default. |
| `inputs` | Table with exactly the pass IDs as keys; each value is a list containing `issue`, `change`, both, or neither. |
| `change_pass` | Optional pass ID; default when a change is supplied (builder `fix`). |
| `engine_source` | `coordinator` (profile `engines.coordinator`) or `tier` (profile tier order and effort). |
| `identity_independent_of` | Optional role ID; preserve the reviewer/builder identity invariant and its existing emulated-capability exception. |
| `engine_independent_of` | Optional role ID; exclude that role's actual engines under the existing [engine rules](roles.md#actual-builder-engine). |
| `templates` | Table keyed by supported runtime, each a nonempty list of template paths relative to the repo root. |
| `events` | Table keyed by supported runtime, each a list of consumed event IDs; empty is allowed. |
| `window_band` | Two integers, inclusive tmux index range; singleton for session roles. |
| `window_name` | Pattern using only `{name}`, `{issue}`, `{change}`, `{round}`, `{pass}`; `name` is the resolved display name in lowercase. |
| `lifetime` | `session`, `issue` or `pass`, matching the [tmux layout](runtimes/tmux.md#layout-and-naming). |
| `cap_key` | Optional profile integer key; omitted means the band alone limits concurrency. |

`window_band`, `window_name`, `lifetime` and `cap_key` describe tmux;
other runtimes use their binding's session mechanisms. `templates` and
`events` use binding IDs (`tmux` and `grok-bot` today). Template paths must name
existing files, remain inside the repo and contain no traversal components.
No credentials, commands, plugin callbacks or gate expressions are allowed.

## Validation contract

The future loader rejects unknown keys, wrong types (including booleans as
integers), unsupported schema versions, missing required fields and secret
patterns, using the [profile validator conventions](profile.md#format).
Errors identify `roles/<domain>/<id>.toml:<key>: reason`; invalid input
writes nothing.
It also rejects unresolved identity/cap keys, nonpositive caps, invalid or
overlapping bands, unknown relation targets or self-relations, a `change_pass`
not in `passes`, input/pass key mismatches and unavailable pattern inputs.
Pass IDs and event IDs must match the selected binding's declared vocabulary;
adding a role reuses that vocabulary without adding a machinery role switch.

One event has one consumer per runtime and scope, preserving
[protocol §8](protocol.md#8-safety). Grok Bot's existing per-change terminal
watch exception is retained by its binding: builder B2 and reviewer V2 both
receive terminal events; the repo-wide coordinator event is a different scope.
The tmux lists below reproduce `CONSUMER`. Grok Bot event scopes and its
watch routing remain in the binding; steering, timers and ownership wakes
also keep their binding-specific routing; no new subscriptions
or merge permissions follow from registry membership.

## Worked registry: engineering domain

[roles/eng/](../roles/eng/) holds one file per current role, filled for tmux:
`coordinator`, `builder`, `reviewer`, `synthesizer` and `researcher`.
Grok Bot retains its existing templates and scoped events
in [wake wiring](runtimes/grok-bot.md#wake-wiring-event-to-consuming-role);
these tmux entries must never supply subscriptions for that runtime.
The coordinator's `coordinate` pass names its existing session duty, not a new
`crew spawn` command. tmux `new-head` includes first PR discovery; Grok Bot
uses `pr-opened`. `fix-at-head` is tmux's existing evidence-only fix wake.
The researcher's file, as an example:

```toml
# roles/eng/researcher.toml
schema_version = 1
rank = 5
display_name = "Riley"
identity_key = "identities.researcher"
marker_role = "researcher"
passes = ["research"]
inputs = { research = ["issue"] }
engine_source = "tier"
templates = { tmux = ["templates/runtimes/tmux/researcher.md"] }
events = { tmux = [] }
window_band = [40, 44]
window_name = "{name}-{issue}"
lifetime = "pass"
cap_key = "runtime.options.researchers"
```

Validate them with `python3 scripts/crew-roles.py roles/eng` (optionally
`--project crew.toml` for resolved identity and cap keys). The equivalence test
compares them with runtime metadata and the remaining renderer constants.

## Hard-coded locations to replace

| Location | Registry data that replaces the role-specific knowledge |
|---|---|
| [crew.d/_shared.py](../scripts/crew.d/_shared.py) | `BANDS`, `PASSES`, `NAMES`, `CAPS`, `brief_src` template selection and `window_env` identity lookup. |
| [crew.d/poll.py](../scripts/crew.d/poll.py) | `CONSUMER` becomes the inverse of the selected runtime's event lists. |
| [crew.d/spawn.py](../scripts/crew.d/spawn.py) | Role/pass CLI choices, default fix pass, input checks, window/item/run/claim/worktree names, reviewer round/verdict handling and `pick_engine` independence branch. |
| [crew.d/up.py](../scripts/crew.d/up.py) | Coordinator name, index 0, identity, brief and engine source. |
| [crew-config.py](../scripts/crew-config.py) | Identity role list, `PLACED_PASSES` host/placement choices, coordinator engine source and reviewer/builder identity relation in capability validation. |
| [crew-render.py](../scripts/crew-render.py) | `ROLES`, role template jobs and role-specific `MAPPED` identity/display-name placeholders. |

This is the migration inventory, not authorization to change those files now.
Profile tier routing, harness support, lifecycle safety and stage 7 remain
owned by their existing contracts; registry data must preserve their behavior.
