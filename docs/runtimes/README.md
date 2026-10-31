# Runtime contract

What every runtime must provide so the core protocol keeps its guarantees,
whichever runtime runs the crew (portable eng-crew, roadmap 13.8,
[#120](https://github.com/mw-ding/eng-crew/issues/120); contract set decided on
[#130](https://github.com/mw-ding/eng-crew/issues/130)). Terms are in
[concepts.md](../concepts.md). This page adds no rule, gate, cap, marker field
or label; the [protocol](../protocol.md) still owns them. Each binding
([grok-bot.md](grok-bot.md); [tmux.md](tmux.md), shipped in M14 and M14.1) fills in
a contract table against it.

## Contract

| # | Capability | Guarantee it protects |
|---|---|---|
| C1 | Wake on event | Every stage starts without a human nudge; nothing idles blind while work is in flight |
| C2 | One consumer per event (spec R8) | No double work; each event is handled once |
| C3 | Messages by reference, with proof of delivery | No payload in messages; no hand-off is silently lost |
| C4 | Status protocol `done` / `blocked` / `paused` / `failed` / `ack` | The coordinator always knows a run's outcome without reading its session |
| C5 | Liveness classes `alive` / `dead` / `missing` / `ambiguous` | Stuck work is detected; a restart never starts a duplicate run |
| C6 | Isolation | Runs never share or damage a checkout; no orphans |
| C7 | Serial land | One land at a time |
| C8 | Owner channel and SLA | Asks reach the owner and are answered or defaulted within the protocol SLA |

### C1. Wake on event

A state change (new tracker item, new change head, CI signal, verdict, land,
steering command, run status) wakes the role that consumes it, by push or by
poll. A role with work in flight never ends a turn without a pending wake
source: either a subscribed event or a scheduled re-check. A missed wake is
picked up by the next wake's sweep ([protocol §6](../protocol.md#6-duties-on-wake-all-roles)
step 3) or by a scheduled backstop.

### C2. One consumer per event

Each event is delivered to exactly one consuming role. Any exception is named
in the binding with its reason and must be cleanup-only (it may not start a
pass). Re-delivery of the same event is a no-op through the idempotency rule
in [protocol §6](../protocol.md#6-duties-on-wake-all-roles) step 2: an existing
marker or lock for this pass at this head ends the wake.

### C3. Messages by reference, with proof of delivery

A message between roles names state; it never carries it. It holds only
references: tracker item, change, full head SHA, a link to the post holding
findings or evidence, or a file path. The receiver re-reads live state before
acting. The sender gets proof that the message arrived (a receipt or an `ack`
naming the message) and retries or escalates when no proof arrives in a
bounded time. Lifecycle actions (interrupt, stop, restart) never travel as
message text.

### C4. Status protocol

Every run reports exactly one of these, recorded where the coordinator reads
it without opening the run's session:

| Status | Meaning |
|---|---|
| `ack` | Run accepted the work or message and started |
| `done` | Pass finished; its output (change, marker, post) exists |
| `blocked` | Cannot continue without another role or the owner; names what it needs |
| `paused` | Stopped on purpose (hold, steering); resumes on an explicit command |
| `failed` | Stopped on an error it cannot fix; names the error |

A run that ends without reporting a status is treated as `missing` under C5.

### C5. Liveness

The runtime classifies every in-flight run without relying on the run itself
to report:

| Class | Meaning | Allowed action |
|---|---|---|
| `alive` | The run exists and is working or waiting on a known wake | None |
| `dead` | The run existed and has exited without a final status | Restart in a fresh worktree |
| `missing` | A run is recorded as in flight but none exists | Restart in a fresh worktree |
| `ambiguous` | The runtime cannot tell (no progress signal, probe failed) | Re-check, then escalate to the coordinator after a bounded time; never restart |

Only `dead` or `missing` authorizes a restart, so a slow run is never
duplicated. The nudge cap and escalation of
[protocol §5](../protocol.md#5-rounds-and-escalation) still apply.

### C6. Isolation

Each run works in its own unique worktree
([roles: worker isolation](../roles.md#worker-isolation-worktrees)), never the
main checkout and never a branch-named shared path. The worktree starts from a
fresh base: the current remote default branch, or the parent change's branch
for stacked work. Spawn refuses a path that breaks these rules. Teardown
deletes that run's worktree and build output only.

### C7. Serial land

At most one land runs per repo at a time, under an exclusive lock taken before
the final [§7 gate](../protocol.md#7-merge-gate-synthesizer) re-check and
released after the merge post. The land is bound to the head the gate checked.

### C8. Owner channel and SLA

Owner asks go through one channel owned by the coordinator, recorded on the
tool of record (invariant I5), with the 2h awake-hours SLA, recommended
default and auto-apply time of
[protocol §6](../protocol.md#6-duties-on-wake-all-roles). No role asks the
owner only inside its own session.

## Gap declaration

A binding that cannot meet a capability fully declares it in its contract
table, in this form:

```text
<C#> <capability>: <unsupported | partial>, compensated by <mechanism>; residual risk: <what can still go wrong>
```

Rules:

- Every gap names a compensating mechanism. A gap with none makes the profile
  **unsupported**.
- A gap that would weaken an invariant from
  [portable spec §3](../specs/portable.md#3-invariants) makes the profile
  unsupported. It is never silently weakened.
- A gap declaration changes no protocol rule; the compensation must already
  exist in the binding or the protocol.
