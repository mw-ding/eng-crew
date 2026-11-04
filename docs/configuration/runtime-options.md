# Runtime options

Configuration module for the profile's runtime keys and the coordinator
option shared by both runtimes, split out of the
[profile reference](../profile.md) under the M26 modular organization
principle ([#676](https://github.com/mw-ding/eng-crew/issues/676)). It holds
the `[runtime]` key table and the shared `max_active_milestones` option with
its priority and default behavior. `control_item`, which `instance` is
required with, stays in the profile's [`[repo]`](../profile.md#repo) table.

## `[runtime]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `name` | string: `grok-bot` or `tmux` ([runtimes](../runtimes/README.md)) | *required* | none (was implicit: Grok Bot) |
| `options` | table, keys per runtime below | `{}` | none |
| `timezone` | string (IANA name) | none | `<timezone>` |
| `instance` | string: `[a-z0-9-]`, 1–63 characters | none; required with `control_item` | owner-chosen instance label, never a host name or path |

Both runtimes accept this coordinator option:

| Option | Type | Default | Replaces |
|---|---|---|---|
| `max_active_milestones` | integer, at least 1 | `1` | `<max-active-milestones>`: dispatch new builds from at most N open milestones, in milestone order |

The earliest active milestone keeps priority. A later milestone only fills
builder capacity the earlier one cannot use because its remaining items are
blocked by dependencies or already in flight. In-flight PRs in any milestone
still finish. The default preserves dispatch from one milestone at a time.

The `tmux`-specific options, standing notes and launch topology stay in the
profile's [`[runtime]`](../profile.md#runtime) section.
