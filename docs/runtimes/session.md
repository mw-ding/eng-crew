# Session runtime binding

> - **Status:** partly built
> - **Applies to:** hand-dispatched or hosted sessions; profiles with `runtime.name = "session"`
> - **Current rules:** [protocol](../protocol.md), [runtime contract](README.md#contract)
> - **Built:** [Run parameters for hosted dispatch](#run-parameters-for-hosted-dispatch) via `mdstack brief` (#647); the [selector, options and briefs](#selector-options-and-briefs) (#914)
> - **Design only:** everything in [Implementation follow-ups](#implementation-follow-ups)
> - **Last checked:** 2026-11-09 at `1db3f1d`

`runtime.name = "session"` runs one interactive coordinator session,
with short-lived workers as native subagents or external harness CLI runs
(roadmap 17.13, [#340](https://github.com/mw-ding/eng-crew/issues/340), after
[#179](https://github.com/mw-ding/eng-crew/issues/179)). This describes the
single-session mode used to build mdstack on 2026-10-29: a Claude Code
coordinator, subagent builders and an independent Codex reviewer.

The validator and renderer accept the selector; the lifecycle mechanisms
below remain manual procedures, and bootstrap's
[harness pointers](../bootstrap.md#q4-install-targets) do not implement this
runtime. It adds no rule, gate, cap, marker field or label: the
[protocol](../protocol.md) and [runtime contract](README.md#contract) apply.

## Selector, options and briefs

A profile selects the binding with `runtime.name = "session"`
([options](../configuration/runtime-options.md#session-options)):
`max_active_milestones`, `session_backend` (`native` subagents or `cli`
runs), the `builders` and `reviewers` pool limits, and the synthesizer's
land-policy options. `crew-render` writes four briefs from
`templates/runtimes/session/`: the coordinator, and the builder, reviewer and
synthesizer worker briefs. Each worker brief carries the tmux role's
contract for one pass per run and ends where the coordinator appends the
`mdstack brief` run block (below); workers set their own `CREW_*` paths, since
no runtime sets them. The binding has no researcher brief:
`researchers = 0` validates as a no-op, so a profile migrated from tmux keeps
it, and any other value is refused.

Session lands are sync and alone (#1041). `land.mode = "async"` is
tmux-only: the validator refuses it on a session profile, and
`mdstack land request|resume|done` resolve only tmux profiles. Merge trains
are tmux-only too, since every `mdstack train` action refuses a session
profile: the synthesizer brief lands each ready PR alone, one per run, and
`train_min`, `train_window` and `train_local_checks` have no effect.

A session profile may carry a `[hosts]` inventory, without `[placement]`.
`mdstack host check` and `mdstack host prepare` then run as for tmux: the
primary gets `mdstack doctor`'s session rows, the engine login rows and the
project mirror row, with load 0 since session workers hold no tmux windows;
any other host gets the same remote rows as under tmux (#1122). Other host
and runtime commands (`hosts`, `layout`, `upgrade`) stay tmux-only.

With `repo.control_item` set, a GitHub issue or a tracker-native item, the
coordinator brief carries the ownership guard and the handoff steps. Without
one, `mdstack ownership` always permits, so the render drops that inert text:
one paragraph says there is no ownership record or handoff, and the worker
briefs omit their ownership line.

## Decisions

| Concern | Session decision |
|---|---|
| Lifetime | One coordinator for the owner's interactive session; one builder run per item, fresh review and validation runs per pass. GitHub and disk retain state when the session closes. |
| Engines | Claude Code coordinator with native subagents or external CLI workers; Codex coordinator with external CLI workers is a manual alternative. Each run follows tier routing and records its actual engine, model and effort. |
| Independence | The coordinator schedules and combines outputs; separate workers review and validate. Validation never receives the review. Reviewer identity and engine diversity remain subject to the existing rules and recorded waivers. |
| Dispatch | Re-read ownership and live item/head, check markers and claims, then pass a brief pointer and refs. A native subagent must enter its assigned unique worktree before changing files. |
| Concurrency | Profile caps remain ceilings; dispatch only as many independent workers as the harness can track. No worker shares the coordinator checkout. |
| Landing | The synthesizer remains the landing role and selects the land rule; it lands each ready PR alone, with no merge train or async land (above). The coordinator dispatches it; one repo lock covers the final gate through the merge post. |
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
| C7 Serial land | Synthesizer takes the repo's exclusive lock (an atomic `mkdir` of `$CREW_STATE/locks/merge.lock.d`, per the [synthesizer brief](../../templates/runtimes/session/synthesizer.md)) before the §7 re-check and holds it through head-bound land and merge post; inability to hold the lock blocks land. | None under this manual procedure; being in one chat is not a lock. |
| C8 Owner channel and SLA | Coordinator's interactive chat plus matching GitHub asks, with the protocol's awake-hours SLA, recommended default and auto-apply time. | C8 owner channel and SLA: partial, compensated by GitHub notifications and checking due asks at the next coordinator wake; residual risk: no session deadline watcher enforces timely defaults while the session is idle or closed. |
| C9 Ownership handoff | Run `mdstack ownership --runtime session` from the rendered [coordinator brief](../../templates/runtimes/session/coordinator.md) each wake and before dispatch, push, post or land; a non-owner or moving/unreadable record means read-only. Outgoing, the brief's steps drain, post the manifest with `offered` and, on `acked`, [stop](../handoff.md#prompt-stop): dispatch nothing more, end every worker keeping unlanded worktrees, post `stopped`, and the session ends. Incoming, it walks the [resume](../handoff.md#resume-and-reconcile) steps by hand: reconcile against live state, ack once per handoff id, hold diverged sets before dispatch, and lift `holds_added` only after `stopped`, the owner's confirmation or a guarded release. | C9 ownership handoff: partial, compensated by the brief's manual steps and the owner closing the outgoing session; residual risk: the tmux `mdstack handoff reconcile`, `ack`, `lift` and `stopped` tooling does not run here, so the plan, the single ack and the stop rest on the coordinator following the brief, and no runner stops wake sources while the session is idle. A takeover waits for confirmed stop and any land past its final gate. |

## Run parameters for hosted dispatch

A hosted or hand-dispatched session gets no runtime-filled run block, so the
coordinator builds it with the same helper `mdstack spawn` uses for tmux
([#647](https://github.com/mw-ding/eng-crew/issues/647)) and never
hand-writes run parameters:

```sh
{ cat "<rendered-brief>"
  cli/mdstack brief --item "PR #42" --pass review --base "<full-head-sha>" \
    --round 2 --host "<session-host>" --engine "codex gpt-6.1-sol medium" \
    --flavor standard --comments "<review-comment-ids>"
} > "<dispatch-brief>"
```

`Item`, `Pass` and `Base` (the full head SHA the pass runs against) are
required; `mdstack brief` exits 2 and prints no block when one is missing or
empty. The optional fields are `Window`, `Round`, `Slot`, `Host`,
`Worktree`, `Engine`, `Claim`, `Flavor` and `Comments`; an omitted one is
left out. Re-read the live head just before building the block. A worker
whose brief lacks the block, or one of its required fields, does not start
the pass ([worker brief rules](../roles.md#worker-brief-template)).

The Grok Bot B1, B2 and V2 prompts follow this recipe for every build, fix,
review and validate worker turn, with the claim, engine and worktree filled
([#778](https://github.com/mw-ding/eng-crew/issues/778)).

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

Profiles accept `session` and the renderer writes its briefs (#914). Still to
build: the lifecycle runner, durable receipts/status, external task/process identity probes,
worktree enforcement and safe teardown, lock handling and ownership guards.
Add a token-free wake/backstop and deadline path per supported coordinator
adapter, or retain the declared attended-only gaps. Verify real harness
completion and stop behaviour, lost acknowledgements, ambiguous runs,
session closure/recovery, unlanded cleanup and ownership transfer before
claiming any gap closed. Bootstrap targets alone supply none of these.
