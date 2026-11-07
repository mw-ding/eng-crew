# Actions CLI contract

Status: draft v0.1 (2026-11-07). The terminal binding is
[`crew action`](../docs/runtimes/tmux.md#crew-action) (#1232), which
implements five actions so far; the rest is milestone M32. The vocabulary,
inputs and outcomes are in
[README.md](README.md); this file fixes how a role calls them from a shell.

The CLI is one binding of the contract. An API or MCP binding may expose the
same actions; it keeps the same names, inputs, outcomes and JSON result.

## Invocation

```text
crew action <name> [<op>] [<common flags>] [<action flags>] [--json]
crew action --capabilities [--json]
```

- `crew action` dispatches to the active environment and connector of the
  project. The command names stay the same in every environment.
- `<name>` is the action name; `<op>` is required for actions with
  operations and absent otherwise.
- `--capabilities` prints the active environment's declaration
  (`supported`, `emulated` or `unsupported`) for every action and exits 0.
- Flags use `--kebab-case`. A flag that takes a list repeats
  (`--ref 12 --ref 34`). A flag value that names a file is a path, never the
  content itself.

## Commands

| Command | Op | Action |
|---|---|---|
| `crew action read` | | A1 |
| `crew action resolve-policy` | | A2 |
| `crew action check-ownership` | | A3 |
| `crew action claim` | `acquire`, `release` | A4 |
| `crew action heartbeat` | | A5 |
| `crew action notify` | | A6 |
| `crew action ack` | | A6 |
| `crew action wait` | | A7 |
| `crew action report` | | A8 |
| `crew action spawn-worker` | | A9 |
| `crew action supervise` | `probe`, `stop`, `restart` | A10 |
| `crew action workspace` | `create`, `remove` | A11 |
| `crew action artifact` | `write`, `append`, `update`, `remove` | A12 |
| `crew action post-marker` | | A13 |
| `crew action tracker` | `create`, `edit`, `assign`, `place`, `label`, `close` | A14 |
| `crew action run-check` | | A15 |
| `crew action publish-change` | `open`, `upload`, `publish`, `prune` | A16 |
| `crew action update-base` | | A17 |
| `crew action compare-content` | | A18 |
| `crew action land` | `acquire`, `request`, `status`, `finish`, `release` | A19 |
| `crew action owner-channel` | `ask`, `update`, `close` | A20 |

## Common flags

These carry the [common envelope](README.md#common-envelope).

| Flag | Envelope input | Default |
|---|---|---|
| `--project <path>` | `project` | `$CREW_PROJECT` |
| `--actor <name>` | `actor` | the run's identity from its brief |
| `--role <role>` | `role` | `$CREW_ROLE` |
| `--item <ref>` | `item` | none |
| `--head <sha>` | `head` | none; a 7-character or other short SHA is refused |
| `--key <key>` | `key` | derived from action, op, item, head and role |
| `--json` | | off: one human line on stdout |

## Action flags

| Command | Flags |
|---|---|
| `read` | `--ref <ref>`, `--kind item\|change\|ci\|markers\|control\|artifact`, `--at <rev>` |
| `resolve-policy` | `--paths-file <path>` (one path per line, both rename paths) |
| `check-ownership` | `--for start\|write\|land` |
| `claim acquire` | `--pass <pass>`, `--round <n>` |
| `claim release` | `--claim <handle>` |
| `heartbeat` | `--claim <handle>` |
| `notify` | `--to <role-or-run>`, `--kind <kind>`, `--ref <ref>`... |
| `ack` | `--message <id>` |
| `wait` | `--event <type>[=<ref>]`..., `--deadline <utc>`, `--backstop <seconds>` |
| `report` | `--status ack\|done\|blocked\|paused\|failed`, `--ref <ref>`..., `--reason <text>` |
| `spawn-worker` | `--pass <pass>`, `--base <sha>`, `--engine <engine>`, `--model <model>`, `--effort <effort>`, `--brief <path>`, `--claim <handle>` |
| `supervise <op>` | `--run <handle>`, `--started <utc>` |
| `workspace <op>` | `--run <handle>`, `--base <sha>`, `--discard-reason <text>` |
| `artifact <op>` | `--type <type>`, `--ref <ref>`, `--file <path>` |
| `post-marker` | `--target <ref>`, `--type <record-type>`, `--body-file <path>`, `--round <n>` |
| `tracker <op>` | `--ref <ref>`, `--field <name>=<value>`... |
| `run-check` | `--check <name>`, `--scope <scope>`, `--proof-kind <kind>` |
| `publish-change <op>` | `--branch <branch>`, `--body-file <path>` |
| `update-base` | `--strategy merge\|rebase` |
| `compare-content` | `--base <sha>`, `--base2 <sha>`, `--head2 <sha>` (`--head` is H) |
| `land <op>` | `--rule direct\|train` |
| `owner-channel <op>` | `--ref <ref>`..., `--deadline <utc>`, `--default <text>`, `--decision-file <path>` |

## Exit codes

The exit code is the outcome. A caller branches on it without parsing text.

| Exit | Outcome | Notes |
|---|---|---|
| 0 | `completed` | |
| 2 | `refused` | Usage error: unknown action, op or flag, or a missing required flag. Checked before any effect |
| 3 | `pending` | Matches the no-ack exit of `crew send --wait-ack` and `crew acked` today |
| 4 | `unknown` | Matches `crew send`'s not-submitted (ambiguous) exit today |
| 5 | `stale` | |
| 6 | `refused` | Precondition failed, including `unsupported` |
| 7 | `failed` | |

Exit 1 is not used, so an interpreter crash or an unhandled error in the
binding never reads as a defined outcome; a caller treats it, and any other
code, as `unknown`.

Existing `crew` subcommands keep their own exit codes; this table applies to
`crew action` only.

## JSON output

With `--json`, stdout carries exactly one JSON object and nothing else;
diagnostics go to stderr. Without `--json`, stdout is one line:
`<outcome>: <action>[ <op>] <reason or primary ref>`.

```json
{
  "contract": "eng-crew.actions/0.1",
  "action": "claim",
  "op": "acquire",
  "outcome": "refused",
  "reason": {"code": "claimed", "text": "live claim held by ben-1218"},
  "refs": {"item": "1218", "claim": "builder-issue1218"},
  "result": {},
  "capability": "supported",
  "key": "claim:acquire:1218:build:builder",
  "observed_at": "2026-11-07T08:00:00Z"
}
```

| Field | Type | Meaning |
|---|---|---|
| `contract` | string | Contract name and version |
| `action`, `op` | string, string or null | What ran |
| `outcome` | string | One of the six outcomes; agrees with the exit code |
| `reason` | object or null | `code` (machine-readable, below) and `text`; null on `completed` |
| `refs` | object | Durable references: the envelope's refs plus any the call created (post, message, claim, run, intent) |
| `result` | object | Action-specific outputs from [README.md](README.md#actions) |
| `capability` | string | `supported` or `emulated` for the binding that ran |
| `key` | string | The idempotency key used |
| `observed_at` | string | UTC time the outcome was determined |

Reason codes are lowercase kebab-case. These are fixed; a binding may add
others and documents them in its capability declaration:

| Code | Outcome | Meaning |
|---|---|---|
| `usage` | `refused` | Bad command line (exit 2) |
| `unsupported` | `refused` | The binding declares the action `unsupported` |
| `not-owner` | `refused` | `check-ownership` refused the effect |
| `no-authority` | `refused` | The calling role may not take this action |
| `held` | `refused` | A hold or stop blocks the effect |
| `claimed` | `refused` | A live claim exists |
| `invalid-ref` | `refused` | A reference is malformed, a short SHA or a payload |
| `head-moved` | `stale` | Live head differs from `--head` |
| `already-recorded` | `stale` | This pass already has its record at this head |
| `no-receipt` | `pending` | Sent, no ack yet |
| `queued` | `pending` | Waiting for capacity or an async backend |
| `uncertain-write` | `unknown` | A write may or may not have happened |
| `unreadable` | `failed` | Required state could not be read |
