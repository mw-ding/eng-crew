# Session runtime binding (design)

Proposed `runtime.name = "session"` for one interactive coordinator session,
with short-lived workers as native subagents or external harness CLI runs
(roadmap 17.13, [#340](https://github.com/mw-ding/eng-crew/issues/340), after
[#179](https://github.com/mw-ding/eng-crew/issues/179)). This describes the
single-session mode used to build eng-crew on 2026-10-29: a Claude Code
coordinator, subagent builders and an independent Codex reviewer.

This is a design, not an implemented selector. The validator and renderer
still accept only `grok-bot` and `tmux`; bootstrap's
[harness pointers](../bootstrap.md#q4-install-targets) do not implement this
runtime. It adds no rule, gate, cap, marker field or label: the
[protocol](../protocol.md) and [runtime contract](README.md#contract) apply.

## Decisions

| Concern | Session decision |
|---|---|
| Lifetime | One coordinator for the owner's interactive session; one builder run per item, fresh review and validation runs per pass. GitHub and disk retain state when the session closes. |
| Engines | Claude Code coordinator with native subagents or external CLI workers; Codex coordinator with external CLI workers is a manual alternative. Each run follows tier routing and records its actual engine, model and effort. |
| Independence | The coordinator schedules and combines outputs; separate workers review and validate. Validation never receives the review. Reviewer identity and engine diversity remain subject to the existing rules and recorded waivers. |
| Dispatch | Re-read ownership and live item/head, check markers and claims, then pass a brief pointer and refs. A native subagent must enter its assigned unique worktree before changing files. |
| Concurrency | Profile caps remain ceilings; dispatch only as many independent workers as the harness can track. No worker shares the coordinator checkout. |
| Landing | The synthesizer remains the landing role, including land-rule selection and merge trains. The coordinator dispatches it; one repo lock covers the final gate through the merge post. |
| Persistence | Claims, run identities, inbox refs, status, summaries and unlanded worktrees live on disk; evidence and markers live on GitHub. Transcript memory is not recovery state. |

## Harness adapters and session backends

| Interface | Proposed use | Limits |
|---|---|---|
| [Claude Code adapter](harness-adapters.md#claude-code-claude-code) | Interactive coordinator; native subagents via bootstrap's project-local pointers; external `claude` workers via the adapter's CLI recipe | Native subagents use harness task handles, not tmux foreground/idle probes. The existing Stop hook invokes a tmux watcher guard; it is not a session wake implementation. |
| [Codex adapter](harness-adapters.md#codex-codex) | External `codex exec` worker with model, effort, worktree and brief pointer; interactive coordinator only with manual wakes | No typed doorbell without a session backend; the tmux notify recipe does not wake a hand-started session. Worker execution uses the non-interactive recipe in [roles](../roles.md#how-to-run-each-engine). |
| Session backend | None: native harness task operations and OS process supervision only | No tmux or herdr support is implied. A supervised CLI needs its PID and OS start time recorded; native tasks need a unique handle and start time from the harness. If these cannot be probed, C5 remains partial. |

The six [backend operations](session-backends.md#operations) still bound
the design: create a worker in its worktree; expose the coordinator's live
view; deliver refs with an ack; probe identity before reading task/process
state; and stop all worker processes before cleanup. Native tasks without
attach or doorbell use the coordinator's view and a new pass after confirmed
completion. An unprovable stop preserves the worktree and is escalated.
Other adapters and backends are undeclared and unsupported here.

## Runtime contract

The mechanisms below are manual operating procedures using the existing
protocol, harness and OS facilities. An automated session runner remains
follow-up work; these rows do not claim it exists. Every partial capability
uses the [gap declaration](README.md#gap-declaration) format.

| Capability | Mechanism | Gap |
|---|---|---|
| C1 Wake on event | Coordinator sweeps GitHub and claims on each owner turn and worker completion; supported harness task completion can return control to it. No model-turn polling is prescribed. | C1 wake on event: partial, compensated by the §6 sweep on the next owner turn or delivered worker completion; residual risk: CI, steering, deadlines and other changes wait while the coordinator is idle or closed. Claude Code background completion is harness-dependent; Codex needs an owner turn without a backend. |
| C2 One consumer per event | Coordinator routes each live event to the protocol's one consumer, checking the pass/head marker and claim before dispatch; duplicate receipts do not create another pass. | None under this manual procedure; no shared event listener is claimed. |
| C3 Messages by reference, proof of delivery | Brief pointers, item/PR/full SHA and finding links go through native task dispatch or the CLI prompt. The receiver re-reads live state and writes an ack in durable status. | C3 messages by reference: partial, compensated by checking the ack and applying the protocol's bounded retry/escalation on the next coordinator wake; residual risk: no independent timer detects a lost handoff while the session is idle. A dispatch handle alone is not delivery proof. |
| C4 Status protocol | Each worker writes `ack`, then `done`, `blocked`, `paused` or `failed` with refs to its status file; coordinator reads these without the worker transcript. A missing final status goes to C5. | None under this manual procedure; native completion alone is not a pass result. |
| C5 Liveness | Inspect native task state or the recorded CLI PID/start time externally; confirmed exit or absent identity means dead/missing. An unqueryable task, hung subagent or failed probe is ambiguous. | C5 liveness: partial, compensated by claim heartbeats, the §6 sweep and bounded re-check then escalation of ambiguous runs; residual risk: a native task lacking a probeable handle/start time cannot be proven alive or missing. Never restart it solely for stale progress. |
| C6 Isolation | Coordinator creates each unique worktree from a fresh remote base and assigns it explicitly; teardown follows both C6 landed/discard checks, recording and preserving unlanded work. | C6 isolation: partial, compensated by explicit worktree assignment and manual C6 checks before removal; residual risk: native subagents may inherit the coordinator's cwd and bypass the assignment. If the harness cannot keep writes in the assigned worktree, that worker configuration is unsupported. |
| C7 Serial land | Synthesizer takes the repo's exclusive OS file lock before the §7 re-check and holds it through head-bound land and merge post; inability to hold the lock blocks land. | None under this manual procedure; being in one chat is not a lock. |
| C8 Owner channel and SLA | Coordinator's interactive chat plus matching GitHub asks, with the protocol's awake-hours SLA, recommended default and auto-apply time. | C8 owner channel and SLA: partial, compensated by GitHub notifications and checking due asks at the next coordinator wake; residual risk: no session deadline watcher enforces timely defaults while the session is idle or closed. |
| C9 Ownership handoff | Run `crew ownership --runtime session` from the paste-ready [coordinator-session brief](../../templates/runtimes/session/coordinator.md) each wake and before dispatch, push, post or land, and follow its outgoing and incoming handoff steps; a non-owner or moving/unreadable record means read-only. On transfer, stop dispatch, retain work and reconcile live GitHub state on return. | C9 ownership handoff: partial, compensated by the owner's manual pause/stop of the outgoing session and the existing ownership-record procedure; residual risk: no session runner stops wake sources or acknowledges a drain automatically. A takeover waits for confirmed stop and any land past its final gate. |

## Run parameters for hosted dispatch

A hosted or hand-dispatched session gets no runtime-filled run block, so the
coordinator builds it with the same helper `crew spawn` uses for tmux
([#647](https://github.com/mw-ding/eng-crew/issues/647)) and never
hand-writes run parameters:

```sh
{ cat "<rendered-brief>"
  scripts/crew brief --item "PR #42" --pass review --base "<full-head-sha>" \
    --round 2 --host "<session-host>" --engine "codex gpt-6.1-sol medium" \
    --flavor standard --comments "<review-comment-ids>"
} > "<dispatch-brief>"
```

`Item`, `Pass` and `Base` (the full head SHA the pass runs against) are
required; `crew brief` exits 2 and prints no block when one is missing or
empty. The optional fields are `Window`, `Round`, `Slot`, `Host`,
`Worktree`, `Engine`, `Claim`, `Flavor` and `Comments`; an omitted one is
left out. Re-read the live head just before building the block. A worker
whose brief lacks the block, or one of its required fields, does not start
the pass ([worker brief rules](../roles.md#worker-brief-template)).

## Recovery and support boundary

On reopening, read ownership first, then GitHub heads, verdicts, CI, claims
and durable status. Reconcile each item from its current stage without
resetting rounds. Resume a builder on the existing PR branch; do not create
a second PR. Restart only externally confirmed dead/missing workers, in a
fresh worktree. Slow or unqueryable workers remain ambiguous and are
escalated; preserve their checkout until their processes are proven stopped.

The design is suitable only for an attended crew that accepts the declared
wake and SLA delays. A requirement for unattended progress cannot be met
by this binding. Any configuration that cannot preserve independent review,
isolation, exclusive landing or trusted ownership is **unsupported**, per
the contract's invariant floor; a gap never waives a merge gate.

## Implementation follow-ups

Before accepting `session` in profiles, implement its renderer and lifecycle
runner, durable receipts/status, external task/process identity probes,
worktree enforcement and safe teardown, lock handling and ownership guards.
Add a token-free wake/backstop and deadline path per supported coordinator
adapter, or retain the declared attended-only gaps. Verify real harness
completion and stop behaviour, lost acknowledgements, ambiguous runs,
session closure/recovery, unlanded cleanup and ownership transfer before
claiming any gap closed. Bootstrap targets alone supply none of these.
