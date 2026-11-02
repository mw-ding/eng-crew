# Role registry (design)

`roles/<domain>.toml` describes a domain's roles as data (roadmap 15.7,
[#317](https://github.com/mw-ding/eng-crew/issues/317), part of #110).
This schema records today's four orchestration roles. `eng-backend`,
`eng-web` and `eng-infra` are worker areas, not extra runtime roles.
The profile validator, renderer and tmux runtime read the engineering registry.
The [protocol](protocol.md) still owns gates and markers.

## Schema

TOML 1.0, Python 3.11+ `tomllib`, with `schema_version = 1` and
`[roles.<role-id>]` tables. Domain and role IDs match `[a-z][a-z0-9-]*`;
role IDs are data, not an enum compiled into the machinery. A selected domain
has one registry, with no layering or cross-domain relations in this version.
Every key below is required unless marked optional; tables are closed.

| Key | Type / meaning |
|---|---|
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
Errors identify `file:roles.<id>.<key>: reason`; invalid input writes nothing.
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

The registry [roles/eng.toml](../roles/eng.toml) records each current role,
filled for tmux. Grok Bot retains its existing templates and scoped events
in [wake wiring](runtimes/grok-bot.md#wake-wiring-event-to-consuming-role);
these tmux entries must never supply subscriptions for that runtime.
The coordinator's `coordinate` pass names its existing session duty, not a new
`crew spawn` command. tmux `new-head` includes first PR discovery; Grok Bot
uses `pr-opened`. `fix-at-head` is tmux's existing evidence-only fix wake.

```toml
schema_version = 1

[roles.coordinator]
display_name = "Ash"
identity_key = "identities.coordinator"
marker_role = "coordinator"
passes = ["coordinate"]
inputs = { coordinate = [] }
engine_source = "coordinator"
templates = { tmux = ["templates/runtimes/tmux/coordinator.md"] }
events = { tmux = ["pr-merged", "pr-closed", "ci-infra"] }
window_band = [0, 0]
window_name = "{name}"
lifetime = "session"

[roles.builder]
display_name = "Ben"
identity_key = "identities.builder"
marker_role = "builder"
passes = ["build", "fix"]
inputs = { build = ["issue"], fix = ["issue", "change"] }
change_pass = "fix"
engine_source = "tier"
templates = { tmux = ["templates/runtimes/tmux/builder.md"] }
events = { tmux = ["issue-assigned", "ci-failed", "review-changes-requested"] }
window_band = [10, 19]
window_name = "{name}-{issue}"
lifetime = "issue"
cap_key = "runtime.options.builders"

[roles.reviewer]
display_name = "Vera"
identity_key = "identities.reviewer"
marker_role = "reviewer-validator"
passes = ["review", "validate", "recheck"]
inputs = { review = ["change"], validate = ["change"], recheck = ["change"] }
engine_source = "tier"
engine_independent_of = "builder"
identity_independent_of = "builder"
templates = { tmux = ["templates/runtimes/tmux/reviewer.md"] }
events = { tmux = ["new-head", "fix-at-head", "merge-up"] }
window_band = [20, 29]
window_name = "{name}-{change}-r{round}-{pass}"
lifetime = "pass"
cap_key = "runtime.options.reviewers"

[roles.synthesizer]
display_name = "Sam"
identity_key = "identities.synthesizer"
marker_role = "synthesizer"
passes = ["land"]
inputs = { land = ["change"] }
engine_source = "tier"
templates = { tmux = ["templates/runtimes/tmux/synthesizer.md"] }
events = { tmux = ["ci-passed", "review-approved"] }
window_band = [1, 1]
window_name = "{name}"
lifetime = "session"
```

Validate it with `python3 scripts/crew-roles.py roles/eng.toml` (optionally
`--project crew.toml` for resolved identity and cap keys). The equivalence test
compares it with runtime metadata and the remaining renderer constants.

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
