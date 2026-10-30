# tmux runtime binding (design)

Design for a local tmux crew (portable eng-crew, roadmap 14.1,
[#130](https://github.com/mw-ding/eng-crew/issues/130)). It answers the
runtime questions #110 left open (Q1, Q2, Q3, Q5, Q6, Q7) and maps the
[runtime contract](README.md#contract) to tmux mechanisms. The `crew` CLI
lands in 14.2–14.9 (#131–#138); [Usage](#usage) covers what has landed. It
adds no rule, gate, cap, marker field or label; the [protocol](../protocol.md) still owns them,
and GitHub stays the tool of record (invariant I5).

## Decisions

| #110 question | Decision | Section |
|---|---|---|
| Q1 wake model | Status files, inbox nudges and `crew poll` feed one zero-token watcher; its exit wakes the coordinator; a turn-end guard keeps it armed | [Q1](#q1-wake) |
| Q2 session lifetime | Coordinator and synthesizer for the session; builder window per issue; reviewer and validator windows per pass | [Q2](#q2-lifetime) |
| Q3 coordinator engine | Claude Code or Codex, chosen by profile; role engines by tier routing | [Q3](#q3-coordinator-engine) |
| Q5 identities | Per-role identity from the profile, token derived inside the window at launch; single-identity rule from #111 | [Q5](#q5-identities) |
| Q6 concurrency | Per-band caps, default 5 builders and 2 reviewer passes; serial land under `flock` | [Q6](#q6-concurrency) |
| Q7 failure | Process-identity liveness probe plus watcher stale timers; restart only on `dead` / `missing` | [Q7](#q7-failure) |

## Layout and naming

One tmux session per repo, `crew-<owner>-<repo>`. One window (tab) per
running agent, never several agents in one window. Index bands keep roles
grouped and stable:

| Index | Window name | Role | Lifetime |
|---|---|---|---|
| 0 | `ash` | Coordinator | Session |
| 1 | `sam` | Synthesizer | Session; idle between lands |
| 10–19 | `ben-<issue>` | Builder | One per issue; fix rounds reuse it; closed with its worktree on merge, close or escalation |
| 20–29 | `vera-<pr>-r<k>-review`, `vera-<pr>-r<k>-validate` | Reviewer-validator | One pass each, fresh session; closed after its status line |
| 30 | `crew-status` | Optional dashboard | Runs `crew status` on a loop: role, item, head SHA, last status, liveness |

Window names are the profile's role display names; the defaults are shown.
`crew spawn` takes the next free index in the role's band. The owner watches
or types by attaching (`crew attach <window>`, read-only by default);
`crew attach builders` opens a temporary tiled view without changing the
layout (#138).

Runtime state lives under `<state-dir>/<owner>__<repo>/`, never only in a pane:

| Path | Holds |
|---|---|
| `render/` | Rendered coordinator and role briefs (#131, #137) |
| `runs/<window>.json` | Run record: index, role, item, worktree, engine, expected harness, start time |
| `inbox/<window>.jsonl` | Messages to a window, one JSON line each, with a `msg-id` |
| `status/<window>.status` | Append-only status lines from a window (`$CREW_STATUS`) |
| `wake/queue.jsonl` | Durable wake queue the coordinator drains each turn |
| `wake/watcher.pid` | PID of the armed watcher; the turn-end guard reads it |
| `poll-state.json` | Last GitHub state seen by `crew poll` |
| `claims/` | Claim files per [protocol §6](../protocol.md#6-duties-on-wake-all-roles) step 2 |
| `spawn-queue.jsonl` | Spawn requests refused by a cap |
| `locks/merge.lock` | Land lock |

## Runtime contract

How tmux meets each capability, with gaps in the
[gap format](README.md#gap-declaration). Mechanisms only; no rule changes.

| Capability | How tmux meets it | Gap |
|---|---|---|
| C1 Wake on event | Watcher blocks on status files, stale timers and `crew poll`; its exit re-invokes the coordinator, which routes each wake by `crew send` or `crew spawn`; turn-end guard blocks an idle coordinator with no armed watcher ([Q1](#q1-wake)) | C1 wake on event: partial, compensated by `crew poll` diffing against `poll-state.json` and the §6 step 3 sweep on the first wake after the machine resumes; residual risk: no work moves while the machine sleeps or the tmux server is down |
| C2 One consumer per event | `crew poll`'s decision function maps each GitHub change to one consumer ([protocol §8](../protocol.md#8-safety)); each wake record names one window; terminal `pr-merged` / `pr-closed` go to the coordinator alone, which runs `crew kill`, so the Grok Bot two-watch exception is not needed | None |
| C3 Messages by reference, proof of delivery | `crew send` appends refs only (issue, PR, full SHA, link, path) to `inbox/<window>.jsonl`, then types a fixed nudge `inbox: <msg-id>`; delivery is proven only by `ack: <msg-id>` in the window's status file; no ack in the profile timeout → one re-nudge, then a liveness check; lifecycle goes through `crew kill` and spawn, never message text | None |
| C4 Status protocol | One line per event in `status/<window>.status`: `ack:`, `done:`, `blocked:`, `paused:`, `failed:`, each with refs; the matching GitHub marker stays the record; a window that exits with no `done:` / `failed:` is `missing` or `dead` under C5 | None |
| C5 Liveness | Probe from tmux, not the agent: window present, `#{pane_dead}`, `#{pane_current_command}` and the pane's foreground process names vs the run record's expected harness ([Q7](#q7-failure)) | None |
| C6 Isolation | `crew spawn` creates a unique worktree from a fresh base and refuses the main checkout, a branch-named path or an existing path; `crew kill` removes that run's worktree, build output and state files only ([Spawn and kill](#spawn-and-kill)) | None |
| C7 Serial land | `sam` takes `flock` on `locks/merge.lock` before the [§7](../protocol.md#7-merge-gate-synthesizer) re-check and holds it through the head-bound squash and the merge post; `crew down` refuses while it is held | None |
| C8 Owner channel and SLA | Coordinator's terminal (`ash`) plus the matching GitHub post; roles send asks as `blocked:` lines, never to the owner in their own window; the watcher carries the §6 auto-apply time as a timer | C8 owner channel: partial, compensated by the GitHub post (the owner's GitHub notifications) and the §6 recommended default with auto-apply time; residual risk: an owner away from the machine sees the ask only through GitHub |

## Q1. Wake

**Decision.** Event-driven hybrid with one wake path into the coordinator:

1. Role windows append status lines; `crew poll` turns GitHub state changes
   into wake records routed to one consumer (#134); stale timers fire for
   runs with no status progress and for owner-ask deadlines.
2. A zero-token watcher (a plain script, no model) runs as a background
   command of the coordinator. It blocks on those three sources, appends
   each actionable event to `wake/queue.jsonl`, and exits with one reason
   line (`status:`, `poll:`, `stale:`).
3. The watcher's exit re-invokes the coordinator ([Q3](#q3-coordinator-engine)).
   It drains the queue, acts (`crew send`, `crew spawn`, `crew kill`, a
   GitHub post), and re-arms the watcher before the turn ends.
4. **No turn ends blind.** A turn-end guard refuses to let the coordinator
   stop while work is in flight (a live run record, a non-empty queue or an
   open owner ask) and no watcher is armed. Claude Code: a Stop hook that
   `crew up` installs (#131). Codex: its turn-complete notify program runs
   the same check and, if it fails, types a fixed wake line into `ash`.

Roles never read GitHub events themselves and never message each other;
everything goes through the coordinator (hub and spoke). The queue is on
disk, so a coordinator restart loses no wake.

**Alternatives.**

- *GitHub as the only bus, each role polling.* Rejected: N pollers spend
  tokens on no-op wakes and two roles can race on one event (C2).
- *Coordinator nudges and polls on its own loop.* Rejected: costs a model
  turn per tick, and the coordinator went idle forever when no notification
  arrived (Claude Code session runtime, 2026-10-29).
- *Heartbeat-driven wake.* Rejected for wake and for liveness; see
  [Q7](#q7-failure).

## Q2. Lifetime

**Decision.** Lifetime follows what each role gains from context:

- `ash` and `sam` live for the tmux session. Both keep only references;
  state is re-read from GitHub on every wake (§6 step 1).
- `ben-<issue>` lives for the issue. Fix rounds arrive in the same window by
  inbox, so the builder keeps its understanding of the change (#137).
- `vera-...-review` and `vera-...-validate` are one fresh session per pass.
  Validation never sees the review's context, and no reviewer carries a
  previous round's opinion forward.

**Alternatives.**

- *Every role long-lived.* Rejected: context grows without bound (#109) and
  a long-lived reviewer anchors on its earlier verdicts.
- *Fresh session for every pass, builder included.* Rejected: each fix round
  re-reads the issue, diff and findings, the cost #109 targets, for no
  independence gain on the author side.

## Q3. Coordinator engine

**Decision.** The profile picks Claude Code or Codex for `ash`. Both run
interactively in window 0 so the owner can type to them. Each meets the wake
path in its own way:

| Need | Claude Code | Codex |
|---|---|---|
| Re-invoked on watcher exit | Background command completion starts a turn | Watcher types a fixed wake line into `ash` on exit |
| Turn-end guard | Stop hook | Turn-complete notify program |

Role windows take engine, model and effort from profile tier routing
([roles](../roles.md#engines-and-fallback-order)). A reviewer or validator
engine differs from the engine that actually wrote the round (invariant I2,
[reviewer engine selection](../roles.md#reviewer-engine-selection)).

**Alternatives.** *Claude Code only*: rejected, because quota steering
([roles](../roles.md#quota-routing)) needs a second coordinator engine.
*Any engine as coordinator*: deferred; an engine qualifies once it can run a
background command or accept a typed wake, and has a turn-end hook.

## Q5. Identities

**Decision.** The profile names a GitHub identity per role. `crew spawn`
passes only the login (`CREW_IDENTITY`); the window's launch line derives
the token inside its own shell, `GH_TOKEN=$(gh auth token --user
"$CREW_IDENTITY")`, then starts the harness. The token is never written to
disk, never in argv and never on the tmux command line. With one identity
for all roles, the single-identity rule of #111 applies: verdicts are
COMMENT reviews with `pass=verdict` markers and a recorded owner merge-ok
([portable spec §6](../specs/portable.md#6-decisions)).

**Alternatives.** *`gh auth switch`*: rejected, it changes a machine-wide
setting and races between windows. *`tmux new-window -e GH_TOKEN=...`*:
rejected, the token lands in argv. *Per-window `gh` config dirs*: rejected,
they duplicate credential stores on disk. *A GitHub App per role*: later; it
also unblocks branch protection ([merge enforcement](../merge-enforcement.md)).

## Q6. Concurrency

**Decision.** Caps per band from the profile: default 5 builder windows and
2 reviewer passes; one land at a time. Beyond a cap, `crew spawn` creates
no window and appends to `spawn-queue.jsonl`; the coordinator drains it when
a window closes (#136). Land is serial: `sam` holds `locks/merge.lock`
([C7](#runtime-contract)).

**Alternatives.** *No cap*: rejected, one machine and engine quotas are the
limit. *2 builders* (the first proposal): raised to 5 to match the
[parallelism](../roles.md#parallelism) ceiling and the kickoff choice.
*5 reviewer passes*: reviews run a second engine and the tests, so the
default starts at 2, still within the ceiling.

## Q7. Failure

**Decision.** Detect from outside the agent; restart only when it is safe:

| Class | Probe result | Action |
|---|---|---|
| `alive` | Window present, pane live, expected harness in the foreground | None; a wedge timer with no status progress turns it `ambiguous` |
| `dead` | Window present, pane dead or harness gone, no `done:` / `failed:` | Restart once |
| `missing` | Run record or claim present, no window | Restart once |
| `ambiguous` | Probe failed, unexpected foreground process, trust dialog, or wedge timer expired | Re-probe; after a bounded time escalate to the coordinator; never restart |

A restart is a fresh window and a fresh worktree from the change's branch;
a second failure on the same item escalates (`crew:escalated`, owner channel)
under [protocol §5](../protocol.md#5-rounds-and-escalation). If the tmux
server or `ash` dies, `crew up` reconciles from disk and GitHub: run records,
status files, the wake queue and a probe of every recorded window.

**Alternatives.** *Heartbeat file per run* (the first proposal): rejected,
it depends on the agent remembering to write it, and silent workers froze
for hours on 2026-10-19
([bottlenecks lesson](../lessons/2026-10-19-bottlenecks.md)). *GitHub-only
sweeper*: kept as a backstop shape, too slow as the detector.

## Spawn and kill

`crew spawn <role> --issue <n> | --pr <n> --pass <pass>` (#132):

1. Check the band cap; on refusal queue the request ([Q6](#q6-concurrency)).
2. Create the worktree `<worktree-root>/<n>-<sha7>-<role>-<pass>/` from the
   current remote default branch, or from the PR branch for fix, review and
   validate passes. Refuse the main checkout, a branch-named path or an
   existing path.
3. Preflight: pre-trust the worktree for the harness (or expect the trust
   dialog to probe `ambiguous`); for a nested sandboxed Codex, set the
   sandbox-inheritance variable the org pack names; confirm the coordinator
   can reach the tmux socket.
4. Create the window in the background, so focus stays on `ash`:
   `tmux new-window -d -t crew-<owner>-<repo>:<index> -n <name> -c <worktree>
   -e CREW_ROLE=... -e CREW_ID=... -e CREW_STATUS=... -e CREW_INBOX=...
   -e CREW_BRIEF=... -e CREW_IDENTITY=... '<launch>'`.
5. `<launch>` derives `GH_TOKEN` ([Q5](#q5-identities)) and starts the
   harness interactively with a short pointer only, for example
   `claude --permission-mode acceptEdits 'Read your brief at $CREW_BRIEF and
   follow it.'`. Briefs never travel through `send-keys` or argv.
6. Verify start: within the profile timeout, `#{pane_current_command}` must
   be the expected harness. Otherwise record `failed:` and no live run.
7. Write the run record and the claim.

`crew kill <window>`: `tmux kill-window`, then remove only that run's
worktree, build output, run record, inbox, status file and claim.

## Usage

`scripts/crew` (Python 3.11+ stdlib) is the CLI; every tmux call goes
through `scripts/crew-tmux.py`, so tests run it against a fake `tmux` on
`PATH` (`scripts/test-crew.py`). Run it from an eng-crew checkout:

```sh
scripts/crew up --project <project>/crew.toml [--org-profile <path>] --inputs <inputs-dir>
scripts/crew down --project <project>/crew.toml [--org-profile <path>]
```

`crew up` (#131):

1. Resolves the profile and refuses unless `runtime.name` is `tmux`.
2. If the session (`runtime.options.session`, default `crew-<owner>-<repo>`)
   is already running, prints the attach command and changes nothing.
3. Renders the briefs with `crew-render.py` into
   `<state-dir>/<owner>__<repo>/render/`. `--inputs` is the render inputs
   directory until the tmux render targets land (#137).
4. For a Claude Code coordinator, adds the turn-end guard to
   `<project>/.claude/settings.local.json` as a `Stop` hook running
   `crew guard --state <state-dir>/<owner>__<repo>`, once, keeping every other
   setting.
5. Creates the session detached, with window 0 named after
   `identities.coordinator.name` (`ash`) in the project directory. The
   window gets `CREW_ROLE`, `CREW_STATE`, `CREW_BRIEF` and `CREW_IDENTITY`;
   its launch line derives `GH_TOKEN` in the window's shell
   ([Q5](#q5-identities)) and execs `claude` or `codex` with the pointer
   `Read your brief at $CREW_BRIEF and follow it.`

`crew down` refuses while `locks/merge.lock` is held, kills the role windows
(highest index first; `crew kill`, #132, adds their cleanup), then the
session. With no session running it is a no-op.

`crew guard` is the turn-end guard ([Q1](#q1-wake)). It blocks the turn end
(`{"decision": "block", ...}` on stdout) when work is in flight, meaning a
run record in `runs/` or a non-empty `wake/queue.jsonl`, and no watcher is
armed, meaning `wake/watcher.pid` names no live process. It blocks at most
once per stop cycle: when the hook input has `stop_hook_active: true` (the
coordinator is already continuing because of this hook), it allows the stop
with a `systemMessage` warning instead, so it never loops. Empty or malformed
hook input counts as not active. Open owner asks join the check when they get
a state file.

Codex recipe (documented, not installed by `crew up`; not yet verified on
the real Codex CLI): Codex runs its `notify` program after each turn. Point
it at the same check and type the fixed wake line into `ash` when it blocks:

```toml
notify = ["sh", "-c", "python3 <eng-crew>/scripts/crew guard --state <state-dir>/<owner>__<repo> </dev/null | grep -q block && tmux send-keys -t crew-<owner>-<repo>:0 'wake: turn-end guard' Enter", "crew-guard"]
```

## Design credit

The watcher, turn-end guard, delivery-ack and liveness-probe patterns are
adapted from [firstmate](https://github.com/kunchenguid/firstmate)
(MIT license). eng-crew takes the contracts only: no code or text
is copied. Delivery proof differs on purpose: an `ack:` status line instead
of checking the composer, so no screen parsing is needed. Not adopted: its
persona and communication style, relay, remote homes, the away-mode daemon,
non-tmux backends and its dispatch and task-lifecycle modes.
