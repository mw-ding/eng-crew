# tmux runtime binding

Binding for a local tmux crew (portable eng-crew), designed in roadmap 14.1
([#130](https://github.com/mw-ding/eng-crew/issues/130)) and shipped in M14
and M14.1. It answers the
runtime questions #110 left open (Q1, Q2, Q3, Q5, Q6, Q7) and maps the
[runtime contract](README.md#contract) to tmux mechanisms. The `crew` CLI
landed in M14 (14.2–14.9 and 14.11, #131–#138 and #172) and was hardened in
M14.1 (14.1a–14.1k); [Usage](#usage) covers it. It
adds no rule, gate, cap, marker field or label; the [protocol](../protocol.md) still owns them,
and GitHub stays the tool of record (invariant I5).

## Decisions

| #110 question | Decision | Section |
|---|---|---|
| Q1 wake model | Status files, inbox nudges and `crew poll` feed one zero-token watcher; it routes mechanical wakes before its exit wakes the coordinator; a turn-end guard keeps it armed | [Q1](#q1-wake) |
| Q2 session lifetime | Coordinator and synthesizer for the session; builder window per issue; reviewer and validator windows per pass | [Q2](#q2-lifetime) |
| Q3 coordinator engine | Claude Code or Codex, chosen by profile; role engines by tier routing | [Q3](#q3-coordinator-engine) |
| Q5 identities | Per-role identity from the profile, token derived inside the window at launch; single-identity rule from #111 | [Q5](#q5-identities) |
| Q6 concurrency | Per-band caps, default 5 busy builders and 2 reviewer passes; serial land under `flock` | [Q6](#q6-concurrency) |
| Q7 failure | Liveness probe from tmux that matches the run identity recorded at spawn (pane id, pane pid and that process's start time), plus watcher stale timers; restart only on `dead` / `missing`, plus one synthesizer respawn after a failed nudge | [Q7](#q7-failure) |

## Layout and naming

One tmux session per repo, `crew-<owner>-<repo>`. One window (tab) per
running agent, never several agents in one window. Index bands keep roles
grouped and stable:

| Index | Window name | Role | Lifetime |
|---|---|---|---|
| 0 | `ash` | Coordinator | Session |
| 1 | `sam` | Synthesizer | Session; idle between lands |
| 2 | `ben-lead` | Builder lead | Session; owns builder scheduling and lifecycle |
| 10–19 | `ben-<issue>` | Builder | One per issue; fix rounds reuse it; closed with its worktree on merge, close or escalation |
| 20–29 | `vera-<pr>-r<k>-review`, `vera-<pr>-r<k>-validate`, `vera-<pr>-r<k>-recheck` | Reviewer-validator | One pass each, fresh session; closed after its status line |
| 40–44 | `riley-<issue>` | Researcher | One research request each, fresh session; closed by `crew route` after its `done:` ([roles.md](../roles.md#researcher-riley)) |
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
| `runs/<window>.json` | Run record: index, role, item, worktree, engine, expected harness, start time, run identity (pane id, pane pid and that process's start time), spawn arguments, restart count |
| `runs/<window>.body.md` | Scratch body a role writes for a `gh` `--body-file` (`$CREW_STATE/runs/$CREW_ID.body.md`, never `/tmp`; the briefs say so, #270); `crew kill` deletes it with the record. The coordinator's is `runs/coordinator.body.md`, which it deletes itself, since `crew down` leaves window 0's files |
| `inbox/<window>.jsonl` | Messages to a window, one JSON line each, with a `msg-id` |
| `leads/builder.json`, `leads/builder.brief.md` | Builder lead identity/restart record and brief; separate from worker runs |
| `leads/builder-events/` | Durable event files referenced by the lead's inbox; retained while work is pending |
| `status/<window>.status` | Append-only status lines from a window (`$CREW_STATUS`) |
| `wake/queue.jsonl` | Durable wake queue the coordinator drains each turn (`crew drain`) |
| `wake/queue.lock` | Lock held around each queue append and `crew drain`'s rename |
| `wake/watcher.pid` | PID of the armed watcher; the turn-end guard reads it |
| `poll-state.json` | Last GitHub state seen by `crew poll` |
| `claims/` | Claim files per [protocol §6](../protocol.md#6-duties-on-wake-all-roles) step 2 |
| `spawn-queue.jsonl` | Spawn requests refused by a cap |
| `locks/merge.lock` | Land lock |
| `trains/train-<n>.json` | Merge train: base, train SHA, members (head, train commit), dropped PRs, train PR, CI result and run links, landed and stopped PRs ([crew train](#crew-train)) |

Profile paths ([`[paths]`](../profile.md#paths)): `<state-dir>` is
`paths.state_dir` and `<worktree-root>` is `paths.worktree_root`.
`<eng-crew>` is `paths.eng_crew` (#244), the absolute path of the eng-crew
checkout, so rendered briefs cite its docs and scripts (`<eng-crew>/docs/`)
from any repo.

## Harness adapters and session backends

Supported here means `crew` uses the adapter or backend today; it claims
no support for an undeclared one (roadmap 15.6, #179).

| Interface | Supported | Limits / gaps |
|---|---|---|
| [Claude Code adapter](harness-adapters.md#claude-code-claude-code) | `claude-code` for role sessions and the coordinator | Launch, dialogs, wake recipe, idle detection and foreground process are declared by the adapter; the default backup nudge can add an empty coordinator turn (C1 below). |
| [Codex adapter](harness-adapters.md#codex-codex) | `codex` for role sessions; partial for the coordinator | The watcher types the coordinator wake line and the notify recipe works on codex-cli 0.164.0 (#170), but `crew up` does not install it ([crew guard](#crew-guard)); C1 gap below. |
| [Cursor adapter](harness-adapters.md#cursor-cursor) | `cursor` for role sessions and the coordinator, subject to engine policy | Only bypass mode; no effort flag or installed turn-end hook. Trust/login screen detection and live wake timing are unverified; C1/C5 gaps below. |
| [tmux backend](session-backends.md#tmux-tmux) | `tmux` through `scripts/crew-tmux.py` | Declares all six operations: create, attach, doorbell, identity probe, state read and kill. C5 compares pane id, pid and start time; C6 checks unlanded work before teardown. |
| [herdr backend](session-backends.md#herdr-herdr) | Local default server through `scripts/crew-herdr.py`, selected by `runtime.options.session_backend` | Background workspace per run; no backend hook dependency. Screen-only composer checks, no activity timestamp, no private coordinator environment or tiled attach; see the contract gaps below. |

`crew spawn` skips other engines in the tier order. Engine tier routing alone does
not declare adapter support.

## Runtime contract

How tmux meets each capability, with gaps in the
[gap format](README.md#gap-declaration). Mechanisms only; no rule changes.

| Capability | How tmux meets it | Gap |
|---|---|---|
| C1 Wake on event | Watcher blocks on status files, stale timers and `crew poll`; it applies mechanical routes before its exit re-invokes the coordinator for judgement, which routes retained wakes by `crew send` or `crew spawn`; turn-end guard blocks an idle coordinator with no armed watcher ([Q1](#q1-wake)); waiting is token-free: the watcher and `crew poll` are plain scripts, and the backstop doubles per idle wake while no run is recorded, capped at 16 × `--backstop` ([crew watch](#crew-watch)) | C1 wake on event: partial, compensated by `crew poll` diffing against `poll-state.json` and the §6 step 3 sweep on the first wake after the machine resumes; residual risk: no work moves while the machine sleeps or the tmux server is down<br>C1 wake on event (waiting cost): partial, compensated by `--no-nudge` for a coordinator whose exit wake works ([crew watch](#crew-watch)); residual risk: with the default nudge, kept so that no single harness feature is the only wake path ([#160](https://github.com/mw-ding/eng-crew/issues/160) row 4), a Claude Code coordinator may take a second, empty turn per wake<br>C1 wake on event (Codex turn-end guard): partial, compensated by the watcher's typed wake and the documented [notify recipe](#crew-guard); residual risk: `crew up` does not install that recipe (verified on codex-cli 0.164.0, #170), so a Codex coordinator without it that ends a turn without re-arming the watcher can idle blind<br>C1 wake on event (Pi): partial, compensated by the watcher's typed wake ([Pi adapter](harness-adapters.md#pi-pi)); residual risk: live wake timing is unverified and no turn-end guard extension is installed, so ending without re-arming the watcher can idle blind<br>C1 wake on event (Cursor): partial, compensated by the watcher's typed wake ([Cursor adapter](harness-adapters.md#cursor-cursor)); residual risk: live timing is unverified and no turn-end hook is installed, so ending without re-arming the watcher can idle blind |
| C2 One consumer per event | `crew poll`'s decision function maps each GitHub change to one consumer ([protocol §8](../protocol.md#8-safety)); each wake record names one window; terminal `pr-merged` is handled by `crew route`; `pr-closed` goes to the coordinator, which runs `crew kill`, so the Grok Bot two-watch exception is not needed | None |
| C3 Messages by reference, proof of delivery | `crew send` appends refs only (issue, PR, full SHA, link, path) to `inbox/<window>.jsonl`, then types a fixed nudge `inbox: <msg-id>` and confirms it left the composer (exit 4 if not, or if a dialog is on screen, when nothing is typed); delivery is proven only by `ack: <msg-id>` in the window's status file; no ack in the profile timeout → one re-nudge, then a liveness check; lifecycle goes through `crew kill` and spawn, never message text | None |
| C4 Status protocol | One line per event in `status/<window>.status`: `ack:`, `done:`, `blocked:`, `paused:`, `failed:`, each with refs; the matching GitHub marker stays the record; a window that exits with no `done:` / `failed:` is `missing` or `dead` under C5 | None |
| C5 Liveness | Probe from tmux and `ps`, not the agent: window present, run identity (`#{pane_id}`, `#{pane_pid}` and that process's start time) vs the run record, `#{pane_dead}`, then `#{pane_current_command}` and the pane's foreground process names vs the run record's expected harness ([Q7](#q7-failure)); a different pane id, pid or start time is `missing`, never `alive`, and a failed probe or adapter dialog is `ambiguous` | C5 liveness (Pi extension dialogs): partial, compensated by `--approve` avoiding built-in project trust and disabling extensions that prompt before unattended dispatch; residual risk: custom extension dialogs are not recognized and may probe alive<br>C5 liveness (Cursor dialogs): partial, compensated by authenticating and accepting workspace trust once with the owner attached before unattended dispatch; residual risk: Cursor-specific login/trust dialogs are not recognized and may probe alive |
| C6 Isolation | `crew spawn` creates a unique worktree from a fresh base and refuses the main checkout, a branch-named path or an existing path; `crew kill` removes that run's worktree, build output and state files only ([Spawn and kill](#spawn-and-kill)), and only when its unlanded-work check (uncommitted or untracked paths; commits not on a fresh fetch of the default branch, the run's branch or `refs/pull/<n>/head`; a failed check counts as unlanded) finds nothing, or after `--discard --reason` posts the owner's reason and that list on the run's PR or issue; otherwise it keeps them and exits 1 ([crew kill](#crew-kill), #172). `crew down` and `crew restart` keep unlanded worktrees the same way | None |
| C7 Serial land | `sam` takes `flock` on `locks/merge.lock` before the [§7](../protocol.md#7-merge-gate-synthesizer) re-check and holds it through the head-bound squash and the merge post; `crew down` refuses while it is held | None |
| C8 Owner channel and SLA | Coordinator's terminal (`ash`) plus the matching GitHub post; roles send asks as `blocked:` lines, never to the owner in their own window; the coordinator writes each open ask's §6 auto-apply time to `asks/<n>.json` (`{"deadline": ...}`, ISO 8601 with its UTC offset) and deletes it when the ask closes; the watcher queues one `ask:` wake per deadline on the first scan at or after it, and cuts its sleep short so that scan lands on the deadline, even while the backstop is backed off; an unreadable deadline wakes at once | C8 owner channel: partial, compensated by the GitHub post (the owner's GitHub notifications) and the §6 recommended default with auto-apply time; residual risk: an owner away from the machine sees the ask only through GitHub, and an ask posted without its `asks/` record gets no deadline wake |
| C9 Ownership handoff | Ownership record and read-only guard implemented ([protocol](../protocol.md#ownership-record)); `crew handoff` posts the owner commands (#637), builds and reconciles the manifest (#211), and acks, lifts `holds_added` and posts `stopped`, with poll's `lost` wake and a watcher that will not re-arm as the prompt stop (#212) ([Ownership fallback](#ownership-fallback)); [crew down](#crew-down) stops every window and the watcher, refusing while the land lock is held and keeping unlanded worktrees, and `crew up` reconciles from disk and GitHub ([Q7](#q7-failure)) | C9 ownership handoff: unsupported, compensated by the owner's manual pause: `crew down` before another runtime starts, plus `crew:hold` on open crew items for a runtime that honours it; residual risk: without a configured control item, a second crew can still act; runs are killed or kept, not drained; the incoming runtime rebuilds its context from GitHub ([#210](https://github.com/mw-ding/eng-crew/issues/210)–[#212](https://github.com/mw-ding/eng-crew/issues/212)) |

With `session_backend = "herdr"`, the runtime keeps the contract above,
using the [herdr operations](session-backends.md#herdr-herdr), with these
additional gaps:

| Capability | Gap |
|---|---|
| C1 Wake on event | C1 wake on event (herdr activity): partial, compensated by status-file progress, OS child-process probes and the existing stale re-check/escalation; residual risk: no last-output timestamp means output alone cannot refresh a heartbeat |
| C3 Messages by reference | C3 delivery (herdr composer): partial, compensated by requiring an empty visible composer before typing, checking for a new empty composer afterward and requiring the inbox ack; residual risk: unrecognizable or busy composers fail with exit 4 and need a bounded re-check |
| C6 Isolation | C6 coordinator environment (herdr): partial, compensated by refusing private environment delivery before creating a workspace and selecting tmux for those profiles; residual risk: a coordinator needing private environment delivery cannot start on herdr |
| C8 Owner channel | C8 observation (herdr): partial, compensated by individual read-only snapshot streams and explicit interactive attach; residual risk: no scrollback navigation or tiled builders view |

In-place upgrade is refused before stopping any herdr run; stop and restart
the crew using the updated install. These gaps change no protocol gate.

With a `[hosts]` inventory ([multi-device](multi-device.md)), each kind of
host keeps the contract as follows. With no `[hosts]` table, the machine is
the primary.

| Host | Runs there | Contract |
|---|---|---|
| Primary | The coordinator, the synthesizer, `crew poll`, the watcher, claims, the land lock, and every role run while M20 lasts | The table above, unchanged |
| Forge-less runner host (`forge = false`) | `crew runner` jobs only: `check-repo`, named tests and offline evidence captures, run at a seeded head. Never a role session, model call or forge access | Unchanged. No wake, status line, inbox, claim or lock lives on the host. A role run on the primary starts the job and gets its result back by reference under `$CREW_STATE/runner/`. Unreachable or refused falls back to a local run ([Failure and fallback](multi-device.md#forge-less-hosts-remote-test-runner)). Added by the [runbook](multi-device.md#runbook-add-a-runner-host) |
| Role host | Builder and reviewer runs (follow-up from 20.8, [#345](https://github.com/mw-ding/eng-crew/issues/345)) | The [contract across hosts](multi-device.md#runtime-contract-across-hosts), with its C1 and C9 gaps. Not built |

## Q1. Wake

**Decision.** Event-driven hybrid with one wake path into the coordinator:

1. Role windows append status lines; `crew poll` turns GitHub state changes
   into wake records routed to one consumer (#134). Each opened or pushed
   head starts review alongside CI; held CI failures join the findings in
   one builder handoff ([crew poll](#crew-poll)). Stale timers fire for
   runs with no status progress, and an ask timer fires at each open owner
   ask's deadline (`asks/<n>.json`, [C8](#runtime-contract)).
2. A zero-token watcher (a plain script, no model) runs as a background
   command of the coordinator. It blocks on those sources, appends
   each actionable event to `wake/queue.jsonl`, runs `crew route` for mechanical
   work, and exits only for retained judgement records with one reason line
   (`status:`, `poll:`, `stale:`, `ask:`).
3. The watcher's exit re-invokes the coordinator ([Q3](#q3-coordinator-engine)).
   On a turn with an owner message it answers briefly before routing, then
   drains the retained queue, acts (`crew send`, `crew spawn`, `crew kill`, a
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
  A `done:` line leaves it idle and assigned to that issue/PR; route reaps it
  when it sees `pr-merged` or `pr-closed`. Idle windows do not count toward
  the busy-builder cap. If all ten builder indices are occupied and queued
  work can run under that cap, dequeue reclaims the longest-idle builder
  whose work is pushed. A later `fix` or `ci-red` message to its old window
  queues refs for route to spawn a replacement automatically (#493).
- `vera-...-review` and `vera-...-validate` are one fresh session per pass.
  Validation never sees the review's context, and no reviewer carries a
  previous round's opinion forward. Review starts on `new-head` without
  waiting for CI, and validation starts only after review passes. Both record
  CI as information only; CI green at head is checked at merge.
- `vera-...-recheck` is an explicit CI-fix or recovery session: inspect
  conflict-resolution hunks and rerun acceptance checks, then post both
  sections in one merge-up re-approve verdict. A clean update-branch skips
  straight to the checks when this recovery is requested; identical clean
  base updates normally use synthesizer portability with no reviewer session.
  Content or behaviour changes in the resolution
  return to normal review and validation ([§6](../protocol.md#6-duties-on-wake-all-roles)).

**Alternatives.**

- *Every role long-lived.* Rejected: context grows without bound (#109) and
  a long-lived reviewer anchors on its earlier verdicts.
- *Fresh session for every pass, builder included.* Rejected: each fix round
  re-reads the issue, diff and findings, the cost #109 targets, for no
  independence gain on the author side.

## Q3. Coordinator engine

**Decision.** The profile picks Claude Code, Codex, Pi or Cursor for `ash`. They run
interactively in window 0 so the owner can type to them. Each meets the wake
path in its own way:

| Need | Claude Code | Codex | Pi | Cursor |
|---|---|---|---|---|
| Re-invoked on watcher exit | Background command completion starts a turn | Watcher types a fixed wake line into `ash` on exit | Watcher types a fixed wake line into `ash` on exit; live timing unverified | Watcher types a fixed wake line into `ash` on exit; live timing unverified |
| Turn-end guard | Stop hook | Turn-complete notify program | Extension `agent_end` event; integration unimplemented | No integration installed |

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

**Decision.** Caps per band from the profile: default 5 busy builders and
2 reviewer passes; one land at a time. Beyond a cap, `crew spawn` creates
no window and appends to `spawn-queue.jsonl`; the builder lead drains its
own pool on completion or window cleanup (#136, #493). Reviewer dispatch and
reclaim belong to its reviewer lead. Within the caps, both leads admit through
the crew scheduler's `crew schedule decide` ([scheduling](../scheduling.md)).
Land is serial: `sam` holds `locks/merge.lock` ([C7](#runtime-contract)).

**Alternatives.** *No cap*: rejected, one machine and engine quotas are the
limit. *2 builders* (the first proposal): raised to 5 to match the
[parallelism](../roles.md#parallelism) ceiling and the kickoff choice.
*5 reviewer passes*: reviews run a second engine and the tests, so the
default starts at 2, still within the ceiling.

## Q7. Failure

**Decision.** Detect from outside the agent; restart only when it is safe:

| Class | Probe result | Action |
|---|---|---|
| `alive` | Window present with the recorded run identity, pane live, expected harness in the foreground | None; a wedge timer with no status progress turns it `ambiguous` |
| `dead` | Window present with the recorded pane id and pid, pane dead or harness gone, no `failed:` (nor `done:` for a reviewer or synthesizer run) | Restart once |
| `missing` | Run record or claim present, and no window, or a window whose pane id, pane pid or that pid's start time differs from the run record | Restart once |
| `ambiguous` | Probe failed, unexpected foreground process, a blocking prompt (trust, hooks review, Codex approval, Claude Code permission) or a fatal API error on screen, or wedge timer expired | Re-probe; after a bounded time escalate to the coordinator; never restart, except one kill-and-respawn of the synthesizer after a failed nudge (below) |

**Failed nudge** (#308, #312). A window that `crew send` could not nudge
(exit 4; a `dialog:` reason is a dialog, which this rule leaves alone) or
that still has no ack after one re-nudge counts as `ambiguous` for the
coordinator, even when the probe says `alive` (an idle harness with the
nudge unsubmitted or unread), so it is never restarted. One exception: the
synthesizer window `sam` holds no worktree work, so the coordinator may
`crew kill` it and `crew spawn synthesizer --pr <n>` once per PR; a second
miss on that PR escalates to the owner. It does so only while
`locks/merge.pid` does not exist, so a land is never cut off mid-flight, and
it re-sends every other pending `land`, because the kill drops `sam`'s
inbox. This is firstmate's default of recovering a stuck worker without
waiting for the backstop, narrowed to the synthesizer. `crew restart` is
unchanged: it still refuses a run that does not probe `dead` or `missing`.

**Run identity** ([C5](README.md#c5-liveness)). `crew spawn`, and an
in-place `crew restart`, records the pane's `#{pane_id}`, `#{pane_pid}` and
that process's start time (from `ps`) in the run record. The probe compares
them before it looks at the harness, so a same-named window running the same
harness (a racing respawn, a manual relaunch) probes `missing`, never
`alive`. Pane ids are unique only while a tmux server lives, so the start
time is required.

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
   harness interactively with the profile's permission flags
   ([crew spawn](#crew-spawn)) and a short pointer only, for example
   `claude --add-dir <state-dir>/<owner>__<repo> --permission-mode
   bypassPermissions ... 'Read your brief at $CREW_BRIEF and follow it.'`.
   Briefs never travel through `send-keys` or argv.
6. Verify start: within the profile timeout, the expected harness must be a
   foreground process of the pane's tty, as for liveness, or
   `#{pane_current_command}`; through a symlinked install that reads as the
   name of the file the link resolves to, which also counts. Otherwise
   record `failed:` and no live run.
7. Write the run record and the claim. The run brief is the rendered role
   brief plus the `## This run` block from `crew brief`'s helper, the same
   block every runtime uses ([hosted dispatch](session.md#run-parameters-for-hosted-dispatch)).

`crew kill <window>`: stop the pane's processes, `tmux kill-window`, then remove only that run's
worktree, build output, run record, inbox, status file and claim, and only
when its work has landed or was explicitly discarded (#172).

## Builder lead

The default tmux renderer installs `builder-lead.md`; `crew up` starts its
long-lived session in reserved window 2, outside the `builders` cap.
The coordinator routes work with `crew lead handoff builder KIND REF...`;
the lead owns builder spawn, dequeue, reclaim and restart. Custom bindings
without this brief keep their declared scheduling; a missing/dead lead in
an installed binding never falls back to coordinator worker spawns.

Owner-present admission uses `runtime.options.present_builders` and
`present_reviewers`, each defaulting to its full cap. Active recorded non-quiet
away mode uses full `builders` and `reviewers`: owner-friendly parallelism
while present, full speed within the caps while away. The optional away
`--cap` remains an additional bound across concurrent runs, defaulting to no
cap. Both leads read `away-control.json` and its authoritative signed issue
records on each admission check. Entering or leaving away mode changes
admission on the next lead wake without restarting sessions; never kill
running workers to meet a lower cap, let the pool drain naturally.

Admission asks `crew schedule decide --pool builder`
([scheduling](../scheduling.md#model)): it ranks both pools' demand
crew-wide under the presence caps, the machine target, the ramp limit and the
optional `max_suites` and `max_load` ceilings, and the lead starts exactly
the builder items it admits. Never stop an active worker to reduce load. Idle
builders do not count toward admission; retention preserves continuity only while capacity is spare,
even with open findings. Reclaim clean/pushed idle builders on demand or
after `idle_builder_ttl` seconds (default 1800; 0 disables expiry), retaining
output and step summaries. Later fixes resume from the adopted PR.
`crew lead suites builder` (or `reviewer`) counts live tool sessions across
both pools, excluding closed/merged items and untracked orphan processes.
An unavailable process or live-state probe fails the command. `crew lead
capacity` is retired: no brief calls it since both leads use the scheduler.

`crew lead report builder REASON REF... --detail "observed inputs"` records
`capacity`, `load`, `suites` and `probe-unavailable` deferrals in
`leads/builder-admission.md` and the lead's `deferred:` status. The router
consumes those status wakes without involving the coordinator; keep the
handoff pending for a backstop or slot release. Only `spawn-failure`,
`missing-dependency`, `owner-decision` and `lead-fault` reasons send a
`blocked` coordinator inbox message with a durable block note. Identical
reason, refs and detail reuse that message across lead restarts; changed
refs or details notify again.

Handoffs use the existing inbox, status and delivery-ack interface. Event
files have stable identities for replay. The lead reconciles pending ids,
worker claims and live GitHub state on start; completed ids are no-ops.
`crew kill` hands builder reclaim to its lead, and automatic dequeue cannot
dispatch another lead's pool. The watcher observes lead identity/status and
nudges deferred inbox work on its token-free backstop. It restarts a dead
or missing lead once through `crew lead ensure builder`, keeping its inbox
and live workers. Ambiguity or a second failure reaches the coordinator's
owner channel for explicit repair. Stopping a lead keeps its inbox; a
successful `crew down` clears lead identity while keeping pending handoffs
for the next start. Synthesizer scheduling remains separate.

## Reviewer lead

The default binding installs `reviewer-lead.md` and starts the reviewer lead
in reserved window 3, outside the reviewer cap. The router records durable
`work` events for new heads, builder completion, pass completion and worker
liveness. Coordinator recovery uses `crew lead handoff reviewer
review|validate|recheck '#PR' HEAD ROUND`; add a rereview steer id as a fourth
reference for a fresh request at the same head. The coordinator never
spawns or reclaims reviewer workers directly in this binding.

The lead calls `crew reviewer-pool`. Dispatch
is serialized under `leads/reviewer/dispatch.lock`; inbox ids stay pending across interruption
until dispatch, matching output or live obsolescence is observed. Before each
spawn, admission asks `crew schedule decide --pool reviewer`
([scheduling](../scheduling.md#model)) and starts the pass only when its PR is
admitted; the reviewer floor keeps one slot, so builder suites cannot starve
reviews. Terminal output survives reclaim; slot release
never automatically dequeues a pool with a lead. Existing active passes stay
running when load rises. The watcher backstop nudges deferred work.

Dispatch deduplicates PR/full head/pass/round across worker records, queued
requests, retained sections and posted markers. An open rereview ignores
output before its steer. Passing review replay starts missing validation
even after review cleanup. `recheck escalate` starts normal review and then
validation; a completed recheck needs no extra validation. Identical
merge-ups continue through synthesizer verdict portability, preserving the
current protocol. Findings travel to the builder lead with retained refs.

A failed Actions run whose observed jobs all have zero steps is `ci-infra`:
coordinator handles the incident, validation may proceed, and no builder
CI fix is dispatched. Missing or incomplete observations remain CI failures.
Infrastructure is never green CI and never waives a merge gate.

Worker recovery rechecks live head and holds before one dead/missing restart;
ambiguous or twice-failed workers require coordinator escalation. Supervisor
lead recovery uses the same identity and one-restart rules as builder lead
recovery, preserving workers, pending inbox ids and evidence.

## Usage

`scripts/crew` (Python 3.11+ stdlib) is the CLI: a thin entry point that
loads one module per command, `scripts/crew.d/<cmd>.py`, with the shared
helpers in `scripts/crew.d/_shared.py`; `scripts/crew --help` lists the
commands. Every tmux call goes through `scripts/crew-tmux.py`, so the tests
(`scripts/test-crew-<cmd>.py`, one file per command) run it against a fake
`tmux` on `PATH`. Run it from an eng-crew checkout. Each command's usage
line is in its own section below.

Every command that resolves the profile (all but `crew guard`) refuses, exit
1, while the **resolved** value of a `paths.*` key it uses is still a
`<placeholder>`, whichever layer set it, so an omitted key that falls back to
the shipped default is refused too (#265). Each command checks only the keys
it uses: every command checks `paths.state_dir`; `spawn`, `kill`, `down`,
`restart` and `train build` also check `paths.worktree_root`; only
`spawn builder` also checks
`paths.toolchain_bin`. An unrendered copy, such as the `crew.toml` inside a
worktree, would put the land lock and state under the worktree. In a window,
use `--project "$CREW_PROJECT"`.

### crew up

```sh
scripts/crew up --project <project>/crew.toml [--org-profile <path>] [--inputs <inputs-dir>] [--coordinator-only]
scripts/crew up --team <config-home>/teams/<team>.toml [--org-profile <path>] [--inputs <inputs-dir>]
```

`--team` starts one instance for every repo of a
[team file](../profile.md#team-files) (#634): one session and coordinator,
and a render per repo under the team state root. The steps below apply to
each repo.

`crew up` (#131):

1. Resolves the profile and refuses unless `runtime.name` is `tmux`.
2. If the session (`runtime.options.session`, default `crew-<owner>-<repo>`)
   is already running, prints the attach command and changes nothing.
3. If the profile can use Codex (coordinator, tier order or fallback), checks
   host `hooks.json` and inline `config.toml` hooks under `$CODEX_HOME`
   (default `~/.codex`). Refuses, exit 1, if any hook has no stored
   `trusted_hash`, before rendering or creating a session. Run plain `codex`
   on the host and review/trust those hooks once, then retry. This check
   never writes Codex config or recomputes its hashes: changed hooks with
   stale hashes, plugin hooks and project hooks still rely on the live
   dialog check.
   Renders the briefs with `crew-render.py` into
   `<state-dir>/<owner>__<repo>/render/`, printing the renderer's output
   only when it fails. `--inputs` defaults to
   `templates/`, whose [tmux briefs](../../templates/README.md) render to
   `render/runtime/<role>.md` (#137); `crew up` and `crew spawn` use
   `render/briefs/<role>.md` when the inputs have a `core/`, else that file.
4. For a Claude Code coordinator, adds the turn-end guard to
   `<project>/.claude/settings.local.json` as a `Stop` hook running
   `crew guard --state <state-dir>/<owner>__<repo>`, once, keeping every other
   setting. Role windows in worktrees of the project load it too; the guard
   is a no-op there (`CREW_ROLE` is not `coordinator`).
5. Creates the session detached, with window 0 named after
   `identities.coordinator.name` (`ash`) in the project directory. The
   window gets `CREW_ROLE=coordinator`, `CREW_STATE`, `CREW_BRIEF`,
   `CREW_IDENTITY`, `CREW_BIN`, `CREW_PROJECT` and the sandbox variable
   (see `crew spawn`);
   its launch line derives `GH_TOKEN` in the window's shell
   ([Q5](#q5-identities)) and execs `claude` or `codex` with the pointer
   `Read your brief at $CREW_BRIEF and follow it.` A Codex coordinator gets
   the per-process `projects` table of a role window
   ([crew spawn](#crew-spawn), Pre-trust) for the real project directory
   and, in a git repository, its repository root, so it skips the
   `Trust this folder?` dialog (#262). Claude Code has no
   documented per-project trust option, so a Claude Code coordinator starts
   at its trust dialog in a new project, whose default answer is `No, exit`:
   attach with `crew attach ash --rw` and accept it once. Until then
   `crew status` shows `ash` as `ambiguous`.
   It sets `renumber-windows off` and `base-index 0` on that session only
   (never `-g`), and `crew spawn` / `crew kill` set them again, so a user
   config cannot renumber the index bands.
6. Starts the enabled pool lead windows, unless the profile's launch
   topology says otherwise ([Launch topology](#launch-topology)).

#### Launch topology

`[runtime.options.launch]` ([profile](../profile.md#runtime), #606) picks
what `crew up` starts. With the table absent, every step above runs as
before.

- `coordinator = "none"`: steps 1 to 3 and the coordinator notes run as a
  preflight for that topology, then `crew up` prints
  `launch.coordinator = none, so no session started` and exits 0. It
  installs no turn-end guard and creates no session. With `--team`, every
  repo renders and records its ownership binding first.
- `roles = "hosted"` or `"none"`, or `--coordinator-only` for one run:
  window 0 starts exactly as in step 5, with the same name and tags, and
  step 6 starts no lead windows (`started no role windows`). With `hosted`,
  the coordinator dispatches builder, reviewer and synthesizer passes as
  hosted sessions on remote worker hosts through its own dispatch tool;
  `crew spawn` and the leads are not used for them.
- `resume`: `fresh` launches as in step 5. A session id launches
  `claude --resume <id>` or `codex … resume <id>` with the brief pointer, so
  the resumed conversation re-reads the freshly rendered brief. `ask` launches
  `claude --resume` or `codex … resume` with no pointer, because the picker
  would take it as a search term or an id; tell the coordinator to re-read
  `$CREW_BRIEF` after picking. Another coordinator engine refuses before any
  write.
- `reconcile = "backend"` (the only value) is the rule below.

**Reconcile binding.** After a rebuild `crew up` itself reads only disk: run
records, status files and the wake queue ([Q7](#q7-failure)). Every other
reconciliation read goes through a backend operation of
[interfaces](../interfaces.md), bound by the configured backend (GitHub:
[Interface mapping](../backends/github.md#interface-mapping); a pack: its
`docs/` binding, [packs](../packs.md#layout)):

| Read | Operation | Who reads it |
|---|---|---|
| Ownership record on the control item | `markers.read-item` | lead start (`roles = "tmux"` with `repo.control_item`), and the coordinator on every wake |
| Open items, milestones, board status | `tracker.milestone`, `tracker.board-status` | coordinator §6 sweep |
| Open changes, heads and their items | `change.read-head`, `change.read-diff-paths`, tracker link | coordinator §6 sweep |
| Verdicts and markers at head | `review.list-verdicts`, `markers.read` | coordinator §6 sweep |
| Hold and escalation tags | `state-tags.set-clear-read` | coordinator §6 sweep |
| CI at head | `ci.check-status`, `ci.failing-jobs` | coordinator §6 sweep |

Non-GitHub reference binding: a pack backend named `<pack>` binds each of
those reads to one command of its own tool, documented in the pack's
`docs/`, never in eng-crew ([direction rule](../packs.md#direction-rule)).
For example:

| Operation | `<pack>` binding (placeholder form) |
|---|---|
| `markers.read-item` | `<pack-cli> item comments <control-item> --order posted --with-author` |
| `tracker.board-status` | `<pack-cli> item list --open --fields status,milestone` |
| `change.read-head` | `<pack-cli> change show <change> --field head` |
| `review.list-verdicts` | `<pack-cli> change reviews <change> --with-author --with-head` |
| `ci.check-status` | `<pack-cli> ci status <change> --head <sha>` |

The ownership read (`crew ownership`, lead start, route, notify) follows
`backends.markers.name`. GitHub keeps its `gh api` call. For any other
backend with `repo.control_item`, `crew up` renders that backend's
`markers.read-item` command from `<inputs>/backends/<backend>.toml` and
records it in `render/bindings.json` (with `--team`, under each repo's state
directory). The ownership read runs it, after
replacing `<n>`, `<owner>` and `<repo>`, with no shell and never `gh`. The
command must print the control item's comments in post order as JSON:
`[{"user": {"login": "..."}, "body": "..."}]`, or pages of such lists. The
trusted-author and marker rules are unchanged. A missing or unsupported
mapping, a non-zero exit or unparsable output reads as `read-only`, so
nothing starts or writes. With `roles = "hosted"` or `"none"`, `crew up`
makes no backend call. The shipped coordinator brief writes the GitHub
binding's commands; a pack supplies its own through the render overlay
(#580).

### crew down

```sh
scripts/crew down --project <project>/crew.toml [--org-profile <path>]
```

`crew down` refuses while `locks/merge.lock` is held, runs `crew kill` on
each role window (highest index first), stops window 0's processes the same
way (unless `crew down` runs inside that process group), then kills the
session. If any
window holds unlanded work, it keeps that worktree, names the windows, keeps
the session and exits 1. With no session running it is a no-op.

### crew spawn

```sh
scripts/crew spawn <role> --issue <n> | --pr <n> | --sweep [--pass <pass>] [--round <k>] [--tier <tier>] --project <project>/crew.toml
```

`crew spawn` (#132) follows [Spawn and kill](#spawn-and-kill) steps 2 to 7;
step 1, the band cap queue, is under [crew dequeue](#crew-dequeue) (#136):

- Roles and passes: `builder --issue <n>` (`build`), `builder --issue <n>
  --pr <n> --pass fix` (a restart; fix rounds normally reuse the window),
  `reviewer --pr <n> [--pass review|validate|recheck] [--round <k>]` and
  `synthesizer --pr <n>` (`land`), and `researcher --sweep`, a
  [triage sweep](../triage.md#host) with no item (window `riley-sweep`,
  claim `researcher-sweep`, worktree `sweep-<sha7>-researcher-research/`). It refuses when the session is not
  reachable (the socket check), the window name is taken, the band is full,
  the claim exists or `crew up` has not rendered the role brief.
- Worktree: a detached checkout of a fresh `git fetch` of
  `origin/<default-branch>`, or of `refs/pull/<n>/head` for a `--pr` pass,
  at `<worktree-root>/<n>-<sha7>-<role>-<pass>/` (a reviewer's is
  `<n>-<sha7>-reviewer-r<k>-<pass>/`, so each round gets its own). A failed fetch refuses (no
  stale base); so do a path inside the primary checkout and an existing path.
- Engine: the first `claude-code` or `codex` entry of `engines.<tier>.order`
  (`--tier`, default `default`) with that tier's effort. A reviewer or
  validator skips every engine named in the PR's `Engine:` commit trailers;
  with no trailer the builder counts as non-Claude, so Claude Code goes first.
  The synthesizer takes the tier's first engine as is, like a builder.
  Muse Code and OpenCode have no interactive launch yet and are skipped.
- Window: `-e` passes `CREW_ROLE`, `CREW_ID`, `CREW_STATE`, `CREW_STATUS`,
  `CREW_INBOX`, `CREW_BRIEF`, the login `CREW_IDENTITY`, `CREW_BIN`, the
  absolute path of this checkout's `scripts/crew`, and `CREW_PROJECT`, the
  absolute path of the `crew.toml` given to `crew up`; never a token.
  `CREW_BRIEF` is `runs/<window>.brief.md`: the rendered role brief plus the
  run's item, pass, worktree, base SHA, engine and claim path.
- Standing notes: `runtime.options.notes` maps each role to an ordered list
  of file paths ([profile](../profile.md#runtime)). `crew spawn` appends the
  current contents verbatim after the run details, each under
  `## Runtime note: <path>` naming the configured file. Absolute paths are
  used as given; relative paths resolve from `<state-dir>/<owner>__<repo>`.
  A missing or unreadable file fails the spawn with its role and path before
  creating a claim, worktree or window. No configured notes leaves the brief
  unchanged. `crew up` applies coordinator notes before creating window 0.
  Configure standing policy once instead of sending files to every new window.
- `--pass recheck` starts one fresh reviewer session at the merge head, using
  the previous approval's `--round <k>`. It checks `git show --remerge-diff`
  for resolution hunks and reruns acceptance checks, then posts Review and
  Validation sections and one final `pass=verdict` marker. It never starts a
  separate validation session. Non-mechanical resolution posts no verdict
  and reports `done: #<n> <sha> recheck escalate`; `crew route` starts full
  review at that head and approval round, then validation on a review pass.
  Every merge gate still applies.
- Step summaries: `.crew/` is added to the worktree's `info/exclude`, so
  `.crew/runs/**` never counts as unlanded work.
- Permissions: `runtime.options.permission_mode` picks the window's flags
  (#293). The default, `bypass`, follows firstmate: agents run any command
  in their worktree without asking, with no approval prompt and, for Codex,
  no sandbox. The worktree and the role's identity are the boundary.

  | Mode | Claude Code | Codex |
  |---|---|---|
  | `bypass` (default) | `--permission-mode bypassPermissions --settings '{"skipDangerousModePermissionPrompt":true}'`: no bypass warning screen, set for this process only; the user's settings are never edited | `--dangerously-bypass-approvals-and-sandbox` |
  | `auto` | `--permission-mode auto` | `-s workspace-write -a on-request -c sandbox_workspace_write.network_access=true` |
  | `safe` | `--permission-mode acceptEdits` (the launch before #293) | `-s workspace-write -c sandbox_workspace_write.network_access=true` |

  Every mode adds `--add-dir <state-dir>/<owner>__<repo>`, so a pass reads
  its brief and writes `$CREW_STATUS` and `verdicts/` there (#234 F15).
  Claude Code gets it before the mode flags: its `--add-dir` takes several
  values and would swallow the pointer. Residual gap in `auto` and `safe`:
  Claude Code still asks for commands no allow rule covers, and Codex
  `workspace-write` keeps a linked worktree's git metadata
  (`<repo>/.git/worktrees/<name>`) read-only, so `git commit` and
  `git push` can still prompt or fail (#288). Crew roles never answer a
  prompt; those modes suit only a host that auto-approves.
  Codex also gets `--add-dir <real path of the worktree's git common dir>`
  in every mode. A linked worktree keeps its refs and objects there,
  outside the worktree, so a host that wraps Codex in an external sandbox
  writable only under the working directory and `--add-dir` paths would
  otherwise block `git branch`, `commit` and `push` (#384).
- Pre-trust: Codex gets one `-c 'projects={"<worktree>"={trust_level="trusted"},"<repo-root>"={trust_level="trusted"}}'`
  (real paths), a `projects` table for that process only;
  `~/.codex/config.toml` is never edited. For a linked worktree Codex
  applies trust to the repository root, the parent of
  `git rev-parse --git-common-dir` (#288), and the old
  `projects."<dir>".trust_level` form did not stop its `Trust this folder?`
  dialog on codex-cli 0.164 (#262). Claude Code has no per-process trust
  option. It keys a linked worktree's trust on the repository root, so
  accepting `ash`'s trust dialog once in the project covers the role
  worktrees; a trusted parent directory did not (Claude Code 2.1.310). An
  untrusted window waits at the dialog with `claude` in the foreground,
  which liveness probes `ambiguous`.
- Sandbox inheritance: `runtime.options.sandbox_env = "<NAME>=<value>"`
  sets the sandbox variable for every window, including window 0. The
  launching environment's `CREW_SANDBOX_ENV=<NAME>=<value>` overrides it.
  Every window gets both `-e <NAME>=<value>` and `CREW_SANDBOX_ENV`, so
  later spawn/restart commands retain the setting. eng-crew never names the
  org's variable.
- Verify start: within `--timeout` seconds (default 15), `claude` or
  `codex` must be a foreground process of the pane's tty (the evidence
  [crew status](#crew-status) takes for `alive`), or
  `#{pane_current_command}` must be that name or the name of the file it
  resolves to on `PATH`. tmux reports a symlinked binary by its target's
  name, so the native Claude Code installer's `claude` reads as its version,
  such as `2.1.314` (#286); a version-shaped name never counts on its own.
  A dead pane reads as `dead`, not
  as its launch's first word (`export`), and fails at once. Otherwise it prints `failed:`,
  cleans up as `crew kill` does and records no run.
- Records: the claim (`claims/builder-issue<n>` for a build,
  `claims/reviewer-pr<n>-<sha7>-r<k>-<pass>` for a reviewer, so review and
  validate at one head coexist, else `claims/<role>-pr<n>-<sha7>`, created
  atomically) and `runs/<window>.json`. A reviewer's record also names its
  verdict file, `verdicts/pr<n>-<sha7>-r<k>-<pass>.md`.

### crew kill

```sh
scripts/crew kill <window> [--discard --reason "<why>"] --project <project>/crew.toml
```

`crew kill <window>` refuses window 0. It sends `SIGTERM` to the pane's
process group (the group of `#{pane_pid}`), waits up to 2 s, sends `SIGKILL`
to anything left, waits again and checks the group is gone; Codex ignores
the `SIGHUP` that `kill-window` sends. Before signaling, it collects descendant
process groups too, so detached tool sessions are terminated during kill,
reap and reclaim. If a group survives, it keeps the
window, worktree and state files and exits 1. Otherwise it kills the window, removes the
worktree named in `runs/<window>.json` (with the build output inside it)
only when it sits directly under `<worktree-root>`, then deletes that run's
`runs/<window>.*` files (record, brief and any scratch file such as a PR
body), inbox, status file and claim, and a reviewer run's verdict
file, except the `review` file: it survives both reviewer windows for
re-validation at the same head. The coordinator removes retained review files
when that PR's head moves or it merges/closes. On a successful kill, the oldest
queued spawn in the freed band starts automatically through `crew dequeue`;
other bands stay queued. The watcher reports terminal status to the coordinator
and does not reap windows itself.

It never removes work that has not landed (#160 row 3). Before removing the
worktree it lists:

- every uncommitted or untracked path (`git status --porcelain
  --untracked-files=all`; ignored build output does not count);
- every commit on `HEAD` not contained in a fresh fetch of
  `origin/<default-branch>`, of the worktree's branch on `origin`, or of
  `refs/pull/<n>/head` for a run on PR `<n>`. A failed default-branch fetch
  counts as unlanded too.

If the list is not empty, the window is still stopped but the worktree, run
record, brief and claim stay; `crew kill` prints the paths and commit SHAs
and exits 1. Reviewer and validator worktrees normally hold nothing and pass.
`crew kill <window> --discard --reason "<why>"` removes anyway, after
posting the reason and the list as a coordinator note on the run's item: a
narrative post on its PR (`gh pr review <n> --comment`), else a comment on
its issue (`gh issue comment <n>`). If the post fails, nothing is removed.
`--discard` without `--reason` is refused before anything is stopped.

### crew guard

```sh
scripts/crew guard --state <state-dir>/<owner>__<repo>
```

`crew guard` is the turn-end guard ([Q1](#q1-wake)). Unless `CREW_ROLE` is
`coordinator` it exits 0 with no output. It blocks the turn end
(`{"decision": "block", ...}` on stdout) when work is in flight, meaning a
run record in `runs/`, a non-empty `wake/queue.jsonl` or an open owner ask
record in `asks/<n>.json` ([C8](#runtime-contract); an unreadable record
still counts), and no watcher is armed, meaning `wake/watcher.pid` names no
live process. It blocks at most once per stop cycle: when the hook input has
`stop_hook_active: true` (the coordinator is already continuing because of
this hook), it allows the stop with a `systemMessage` warning instead, so it
never loops. Empty or malformed hook input counts as not active.

Codex recipe (documented, not installed by `crew up`; verified on
codex-cli 0.164.0, #170): Codex runs its `notify` program after each turn,
with the `agent-turn-complete` JSON as the last argument. Feed that JSON to
the same check and type the fixed wake line into `ash` when it blocks:

```toml
notify = ["sh", "-c", "printf %s \"$1\" | python3 <eng-crew>/scripts/crew guard --state <state-dir>/<owner>__<repo> | grep -q block && { tmux send-keys -t crew-<owner>-<repo>:0 -l 'wake: turn-end guard'; sleep 0.3; tmux send-keys -t crew-<owner>-<repo>:0 Enter; }", "crew-guard"]
```

A payload whose `input-messages` ends with `wake: turn-end guard` (the
turn this recipe started) counts as `stop_hook_active`, so the guard blocks
at most once per stop cycle here too. Without that, a coordinator that
ends the wake turn without re-arming the watcher looped one turn every few
seconds on the real CLI. The line is typed with `-l` and `Enter` follows
0.3 s later: typed in one `send-keys` with `Enter`, it stayed in the composer
unsent (the paste burst of #308). On a thread's first turn Codex also
notifies for its title turn, so a second wake line can follow; it joins the
same wake turn or the next, which the guard then lets end.

### crew send

`crew send <window> <kind> <ref>... --project <project>/crew.toml
[--wait-ack <secs>]` (#133) messages a role window by reference
([C3](#runtime-contract)):

- Refs only: each ref is an issue or PR number (`#171`), a full 40-character
  SHA, an `https://` link or a path, at most 200 characters, with no
  whitespace. A ref that opens a diff hunk (`---`, `+++`, `@@`) or holds
  `Traceback` is refused, and so is a message line over 1024 bytes. `<kind>`
  is a short lower-case word such as `fix` or `ci-red`. A refusal writes
  nothing and exits 2.
- It refuses (exit 1) when the window is not in the session. Otherwise it
  appends one JSON line `{"id", "kind", "refs", "from", "ts"}` to
  `inbox/<window>.jsonl` (`from` is `$CREW_ID`, else `$CREW_ROLE`, else
  `coordinator`), nudges the window through the adapter and prints
  `crew: sent <msg-id> to <window>`. The inbox file is the message; the
  nudge carries no payload.
- The nudge is typed once and its submit confirmed (#308). `crew send`
  reads the composer at the cursor (`capture-pane` and
  `#{cursor_x} #{cursor_y}`): the rows from the prompt glyph (Codex `›`,
  Claude Code `❯`) down to the cursor row. When they hold nothing but earlier
  `inbox: <msg-id>` lines and the cursor ends them, it clears them with
  `C-u`, twice per line (in both TUIs `C-u` clears a line, then joins the
  empty line to the one above; `Escape` is not used: it interrupts a running
  turn, and Codex keeps the draft). Other text is never cleared. Then it
  types `inbox: <msg-id>` (`send-keys -l`), waits 0.3 s (an `Enter` right
  behind typed text lands in Codex's paste burst and adds a newline instead
  of submitting, which stacked the nudges in #308) and presses `Enter`.
  While the nudge is still in the composer it retries `Enter` up to 3
  times, never retyping. If the nudge stays, or the clear left earlier
  lines, it prints `crew: nudge not submitted: <msg-id> to <window>: ...;
  treat <window> as ambiguous` and exits 4 without waiting for an ack; the
  inbox line stays. A screen with no composer at the cursor counts as
  submitted.
- A window showing a dialog (the list under [crew status](#crew-status))
  gets no key at all (#315): a Claude Code permission or Codex approval
  prompt preselects yes, so the nudge's `Enter` could approve a command
  nobody reviewed. `crew send` checks before the clear and before each
  `Enter` retry; on a dialog it prints the exit-4 line above with the reason
  `dialog: ...` and exits 4, and the inbox line stays. The watcher's next
  scan reports the same run as a `dialog:` wake.
- Delivery is proven only by a line `ack: <msg-id>` in
  `status/<window>.status`; the composer check proves only the submit.
  `--wait-ack <secs>`
  waits for it, and `crew acked <window> <msg-id> [--wait <secs>]` checks
  later: exit 0 when acked, 3 with `crew: no ack: ...` when not. The
  re-nudge and liveness check after a missed ack are the coordinator's;
  what follows an exit 4 or a second miss is under [Q7](#q7-failure).
- Lifecycle (interrupt, exit, relaunch) never goes through a message; use
  `crew kill` and `crew spawn`.

### crew acked

```sh
scripts/crew acked <window> <msg-id> [--wait <secs>] --project <project>/crew.toml
```

`crew acked` (#133) checks delivery of a `crew send` message: its exit codes
and the `ack: <msg-id>` rule are under [crew send](#crew-send).

### crew poll

```sh
scripts/crew poll [--once] --project <project>/crew.toml
```

`crew poll [--once] --project <project>/crew.toml` (#134) is the GitHub wake
source of [Q1](#q1-wake) and the decision function of [C2](#runtime-contract).
It needs no model and makes read-only `gh` calls only, with the logged-in
identity:

- `gh pr list --state open --json number,state,headRefOid,labels,statusCheckRollup,reviews`;
  a PR counts as a crew PR when it has a `crew:*` label. A tracked PR missing
  from that list is read with `gh pr view <n>` for its merged or closed state.
- `gh issue list --state open --label crew:ready --json number,labels,assignees`.
- For a changed head with a live pass verdict at the previous head,
  `gh api repos/<owner>/<repo>/commits/<head>` and
  `gh api repos/<owner>/<repo>/compare/<second-parent>...<default-branch>`
  confirm exactly two parents, first parent equal to the previous head, and
  second parent on the default branch (`identical` or `ahead`). Other pushes
  remain `new-head`; the synthesizer checks patch identity; changed patches route to the builder
  and delta re-review.

Per crew PR it keeps the head SHA, the CI rollup (`passed`, `failed` or
`pending`) and the latest verdict at head, read only from hidden `crew:v1`
lines with `role=reviewer-validator pass=verdict sha=<head>`
([protocol §4](../protocol.md#4-marker-conventions)). It compares them with
`poll-state.json` in a pure function and emits one event per change, each to
exactly one consuming role ([protocol §8](../protocol.md#8-safety)):

| Change | Event | Consumer |
|---|---|---|
| Opened or pushed crew PR has a new head, regardless of CI state | `new-head` | reviewer |
| Only new commit is a default-branch merge atop a previously approved head | `merge-up` | synthesizer (patch identity and live gates) |
| CI rollup at head turns green | `ci-passed` | synthesizer (retry only with approval at head) |
| CI rollup at head turns red after a job started, or startup evidence is unknown | `ci-failed` | builder |
| Failed Actions jobs have zero steps, with no other code failure | `ci-infra` | coordinator (infrastructure recovery; never a builder fix) |
| New `verdict=changes` at head | `review-changes-requested` | builder |
| New `verdict=pass` at head | `review-approved` | synthesizer |
| New builder `pass=fix` marker at head after a `verdict=changes` there (an evidence-only fix: no new commit, so no `new-head`) | `fix-at-head` | reviewer |
| Tracked PR merged / closed | `pr-merged` / `pr-closed` | coordinator |
| `crew:ready` issue newly assigned | `issue-assigned` | builder |
| Express change: new builder `pass=selfgate verdict=pass` at head with CI green | `selfgate-passed` | synthesizer |

A change that resolves express ([express lane](../express-lane.md#routing),
`crew:express` plus the item record and class rules, read as `crew train`
does) emits no `new-head` or `fix-at-head`, and emits `ci-passed` only with a
selfgate pass at head. A merge-up atop a head with a selfgate pass emits
`merge-up` and carries that pass to the merged head for `ci-passed`; the
synthesizer checks its portability. An unreadable resolution runs the crew lane. When an
express change falls back to the crew lane, poll emits `new-head` at its
current head so normal review starts.

No change emits nothing. Each event is one wake record appended to
`wake/queue.jsonl` before `poll-state.json` is saved (at least once):

```json
{"id": "poll-<ts>-<hex>", "source": "poll", "reason": "poll", "event": "new-head", "consumer": "reviewer", "refs": ["#171", "<head-sha>"], "round": 1, "ts": "<ts>"}
```

`new-head` and `fix-at-head` records also carry `round`: the verdict round
`k` the review pass is for, 1 + the `verdict=changes` verdict markers since
the latest `cutover` or `resume` marker
([protocol §5](../protocol.md#5-rounds-and-escalation)). A `fix-at-head`
record is the code side of the coordinator's rule for a builder `done:` at
the round's verdict head: spawn the review pass at that head with
`--round <k>`.

A `merge-up` record replaces `new-head` and carries `previous_head` (the
approved first parent) and the approval's `round`. The coordinator sends
it to the synthesizer for protocol §7 verdict portability; a later CI-green
wake retries the same candidate. `crew route` leaves clean `merge-up` records
queued for this handoff. Identical content needs no reviewer session. If the
synthesizer reports `no-verified-base`, the coordinator re-reads head/holds
and dispatches normal review and independent validation at that head to
record the base, then retries portability.
Conflicts or differing patches route through the builder, then delta
re-review and independent validation at the updated head. An open rereview
steer at head always routes full review and validation. Explicit `recheck`
recovery and CI-fix passes remain available; they are not required for an
identical clean base update. A `recheck escalate` status routes full review at
the same head and round, followed by independent validation on a pass.

`reason` and the string `event` are the keys every queue record shares with
the watcher (#135); `refs` are `crew send` refs. The coordinator drains the queue and routes each
record to the consumer's window by `crew send`, or `crew spawn` when the
window does not exist; poll itself types into no window. The first run, with
no `poll-state.json`, records a baseline and emits nothing; the
[§6](../protocol.md#6-duties-on-wake-all-roles) step 3 sweep covers anything
older. Without `--once` it polls every `runtime.options.poll_interval` seconds
(default 60), in a dedicated window or under the watcher (#135); a failed `gh`
call is printed and retried on the next tick, and exits 1 with `--once`.
Labels such as `crew:hold` are not filtered: the consumer applies its own
guard.

**Intake ack (#303).** `crew poll` has no `pr-opened` event. The
[§6](../protocol.md#6-duties-on-wake-all-roles) `pr-opened` ack comes from
the reviewer instead: the round-1 `review` pass posts it as its first act
after the live re-read and engine check (reviewer brief, step 3), a COMMENT
review `[<ReviewerBot>/ack] intake @ <sha7>` with a `pass=ack` marker and
`round=n/a verdict=n/a`. It is once per head, never from the `validate` pass
or a later round, and a respawned pass finds the post and adds none. It
appears when review starts on the opened head, even with CI pending or red.
The same `new-head` event starts review after a push; it does not add another
round-1 intake ack where an ack already exists at that head.

**CI and review handoff (#380).** `ci-passed` never spawns review. It wakes the
synthesizer to retry a merge only when an approval exists at head; all §7 gates
still apply. The coordinator holds `ci-failed` while that head's review or
validation is running or queued, persisting refs in
`ci/<n>-<head-sha>.json`. When the active pass reports, it
re-reads head, CI and findings and sends one builder fix carrying both CI
failures and review/validation refs. Zero-step startup failures are
`ci-infra`: the coordinator handles infrastructure recovery without a builder
fix, and validation proceeds after a passed review. CI must still be green
before merge. If review passed but CI is still red from a started or unknown job,
it sends `ci-red` with the review refs instead of starting validation on a
head about to move. If CI recovered, it drops the held failure and continues
validation or land. A red signal with no pass in flight goes straight to the
builder, including after approval. A CI fix after approval starts the light
re-check at the new head: fresh review and validation sessions inspect the
fix hunks and rerun acceptance checks using the approval's round number
(protocol §6). Other builder pushes get normal review; no per-PR CI-only
fast path is introduced. Status and poll events are
de-duplicated by PR/head/pass/round; held refs for older heads are discarded.
Files referenced in a handoff remain until the builder reports `done:` or
posts its fix marker, so it can read both CI failures and findings.
An evidence-only fix still starts the next review once through `fix-at-head`
or the builder's `done:` line. Review and validation record observed CI state
as information only, and independently reproduced failures remain findings.

### crew attach

```sh
scripts/crew attach <window>|<role>|builders [--rw] --project <project>/crew.toml
```

`crew attach` (#138) is the owner's live view of a window:

- `<window>` is a window name (`ben-7`, `crew-status`). `<role>` (`builder`,
  `reviewer`, `synthesizer`, `coordinator`) picks the role's only window in
  its band; with several it lists them and refuses.
- It runs `tmux attach-session -r -t =<session>:<index>`: read-only, so
  keystrokes never reach the agent; detach with the tmux prefix and `d`.
  `--rw` attaches interactively, for typing to the agent.
- Attaching selects that window as the session's current window, which other
  clients attached to the session also see. The layout (indices, names) does
  not change.
- `crew attach builders` opens a temporary tiled view of the builder band
  (10–19): a separate session `crew-<owner>-<repo>-builders-<pid>` with one
  pane per builder window, each showing the last lines of that window's
  screen (`capture-pane`, refreshed every second). It never moves, joins or
  renumbers a crew window, and the view session is killed on detach.

### crew logs

```sh
scripts/crew logs <window> [-n <lines>] [-f] --project <project>/crew.toml
```

`crew logs` (#138) prints the last `-n` lines (default 20) of the run's step
summary: the newest `<worktree>/.crew/runs/**/summary.md` under the worktree
in `runs/<window>.json` ([observe.md](../observe.md#tmux-attach-and-logs)).
`-f` follows it with `tail -f`. It never prints raw logs (`steps/`).

### crew land-lock

```sh
scripts/crew land-lock acquire|release --project <project>/crew.toml
```

Serial land ([C7](#runtime-contract), #136). `sam` runs `acquire` before the
[§7](../protocol.md#7-merge-gate-synthesizer) re-check and `release` after the
merge post. `acquire` takes `flock` on `locks/merge.lock` without waiting
and leaves a detached holder process with the lock open (its PID and
process start time in `locks/merge.pid`), so the lock outlives the command.
While it is held, a second `acquire` fails fast (exit 1, `land lock ... is
held`) and `crew down` refuses. `release` signals the holder only while the
lock is held and the live process with the recorded PID has the recorded
start time and is a `crew land-lock acquire`; otherwise (a stale or reused
PID, or a lock held by another process) it signals nothing and exits 1.
It then waits for the unlock and removes `merge.pid`; with no lock held it
is a no-op. The lock is local to the machine.

### crew schedule

```sh
scripts/crew schedule snapshot --project <project>/crew.toml
scripts/crew schedule summary --project <project>/crew.toml
```

`crew schedule snapshot` (#620) prints one JSON object with every
[scheduler input](../scheduling.md#inputs): both pools' pending demand by
kind, run records with their worker state (`busy`, `idle` or `exited`),
reservations, outstanding land messages in the synthesizer inbox, open trains,
open milestones and open issues with their
`Depends on #n` refs, normalized load, memory pressure (macOS pressure level;
Linux `/proc/pressure/memory` `some avg10`), local suites, gateway errors in
the last 10 minutes and each pool's cap. A failed read is `unknown` for that
input only. It is read-only: it writes nothing and admits nothing; the
scheduler's decision step is a later build issue.

The [target](../scheduling.md#target) T (#623) is a function over a snapshot,
kept with its last change time and recent starts in `schedule/target.json`;
no command calls it until the decision step. Its watermarks and ramp are the
`load_high`, `load_low`, `error_high`, `schedule_interval` and
`schedule_ramp` [profile options](../profile.md). Linux memory pressure is high
at `some avg10` 10.0 and low below 1.0.

`crew schedule summary` (#628) prints the
[one-line summary](../scheduling.md#observability) of the latest decision:
busy workers and reservations against each pool's cap, T, the machine
signals, queued demand by kind, current deferrals by first reason, held
demand by ref (an issue or PR under `crew:hold`, never granted), and
orphans with their pane process ids: live tool sessions of runs whose item
is closed, and of crew windows (other than window 0) with no run or lead
record. `terminal` counts and names reviewer runs whose last status line is
`done:` and that still hold a slot. The scheduler never stops them. `crew watch` prints it after its exit line. Finishing work
(classes 1–6) deferred for `stuck_after` seconds (default 1800) is one
`schedule-stuck` wake per (pool, ref, first deferral), carrying the latest
snapshot; `schedule/deferred.json` keeps each current defer's first time.

### crew train

```sh
scripts/crew train check <pr>... --project <project>/crew.toml
scripts/crew train build <pr>... [--after <n>] [--no-wait] [--local] [--grace <s>] [--interval <s>] [--timeout <s>] --project <project>/crew.toml
scripts/crew train wait <n> --project <project>/crew.toml
scripts/crew train land <n> <pr> [--mirror-deferred] --project <project>/crew.toml
scripts/crew train close <n> --project <project>/crew.toml
scripts/crew train route <n> --project <project>/crew.toml
scripts/crew train bisect <n> --project <project>/crew.toml
```

A merge train (#321) tests approved PRs together once, then lands them with
no catch-up between them: the merge queue GitHub does not offer private
repos on GitHub Free. `sam` uses it when two or more PRs are ready at once
([land rules](../protocol.md#land-rules-and-merge-trains), the synthesizer
brief). [§7](../protocol.md#7-merge-gate-synthesizer) counts a green train
whose tested state is the current default branch as tested with it.

The profile option `runtime.options.lone_pr_land` defaults to `"train"`,
which retains the tested-with-default-branch gate and batching rules. With
`"direct"`, exactly one ready PR lands immediately, even behind the default
branch, without update-branch or a one-member train. Two or more ready PRs
still train, regardless of `train_min`. Under the land lock, re-survey the
ready set before squashing; only the tested-with-default-branch gate is
waived, and the merge record names `lone_pr_land=direct` and the lone-ready
condition. Every other §7 gate still applies at head.

After a direct land, the synthesizer waits for the default-branch push CI run
at the PR's exact merge commit SHA, checking all required jobs; the coordinator
keeps the synthesizer alive through the check after `pr-merged`. Missing or
pending CI is not green. On red it reports
`blocked: main red after #<n> <run-url>`; the coordinator files a blocking
`crew:ready` fix issue linking the landed PR and run, prioritizes it over new
feature work and keeps the blocker open until default-branch CI is green.

`train check` is read-only: it reports `gate pr=... sha=... name=...
status=pass|blocked|manual reason=...` for every requested PR, and exits 1
if any gate is blocked. It checks head verdict markers (including formal
approval and passing review/validate), state/permission, sensitive merge-ok,
CI and evidence artifact presence. Mirror deployment freshness, evidence
agreement or reasoned N/A, grant scope, engine attribution, linkage and
runtime/inbox gates explicitly require manual verification. Filter blockers
before building and resolve manual gates with the synthesizer's §7 check.
A snapshot supplies no merge authorization and never replaces the land check.

`build --no-wait` pushes and records `ci=pending`, then returns exit 0
without waiting; `train wait <n>` collects CI and records its result. Build
N+1 with `--after N --no-wait` while N runs CI or lands: its base is N's
tested tip, and members already in N are excluded. A predecessor with
`ci=fail` is refused, even if its close has not completed. Preparation overlaps;
landing remains serial under C7. N+1 cannot land until N completes and its
final squash tree exactly matches N+1's tested base. After a predecessor's
real stop (including red CI or an early close), `wait` or `land` closes the old
successor and rebuilds its members on the newly fetched default branch,
using a new train number and fresh CI. Read the new record before landing.
No speculative result is used after its predecessor stops. A transient
predecessor pause keeps the successor and its CI for resumption.

`train build` takes ready PRs in dependency order, then approval order, and
keeps that order. PRs that change the same paths stay in the train together
([overlap](../scheduling.md#overlap)): each merges onto the train branch in
turn, and a PR is dropped only when its merge actually conflicts
(`reason=conflict`). Train CI tests the combined result, so the land gate is
unchanged. Each member's changed paths from its head's merge base are still
recorded.

The build then:

1. Numbers the train one above the highest `crew/train-<n>` branch on the
   remote and `trains/train-<n>.json` record, so it never reuses a live
   train branch or a recorded number.
2. In a temporary clone `<worktree-root>/train-<n>-<base7>` (objects shared
   with the repo) at the freshly fetched default branch (the train base),
   merges each PR head (`refs/pull/<pr>/head`) with `--no-ff`, in order.
   PRs touching common paths that merge cleanly stay members. A conflicting
   train merge is aborted and that PR is dropped. The clone has no
   `info/attributes` and the merges ignore a global attributes file: a local
   merge driver such as `merge=union` hid conflicts that GitHub's merge then
   hit (train 4).
3. Skips the local full suite by default and records `local=skipped`.
   `--local` or `runtime.options.train_local_checks = true` opts in to
   `scripts/check-repo.py` and every `scripts/test-*.py` the train has
   (`local=none` when there are none). An opted-in failure stops before
   any push. A local pre-check is a future CI-velocity option, not a merge
   gate; green train CI remains required.
4. Pushes `crew/train-<n>` (never a force push) and opens a draft PR titled
   `crew train <n> (CI only, do not merge)`. It has no `crew:*` label, so
   `crew poll` ignores it.
5. Waits `--grace` seconds (default 20), since `gh pr checks` exits
   non-zero until checks register, then reads `gh pr checks --json` every
   `--interval` seconds (default 20), counting no checks yet as pending,
   until all are done or `--timeout` (default 1800) passes. A red or
   timed-out train's PR is closed and its branch deleted.
6. Removes the clone, saves the record and prints these lines; exit 0
   on green CI or pending CI with `--no-wait`:

```text
member pr=<pr> head=<head-sha> step=<train commit after this member>
dropped pr=<pr> reason=conflict
deferred pr=<pr> reason=predecessor-member
ci-link <CI run URL>
train n=<n> branch=crew/train-<n> base=<sha> sha=<train-sha> pr=<train-pr> local=skipped ci=pass
```

A profile may name a recorded owner standing mirror deferral with
`runtime.options.mirror_deferral` (default `"none"`), including its source and
scope, for example `"#110 roadmap PRs per #140"`. The synthesizer reads that
decision and verifies each PR is covered and does not change live Grok Bot
behaviour. For those PRs it satisfies the mirror gate without a per-PR
coordinator comment or label removal, and names the deferral in the merge
record. Uncovered PRs, unreadable decisions and live Grok Bot behaviour changes
still require a real mirror. This gives no merge permission and gate changes
still need the owner's per-PR merge-ok. For a train member using it, pass
`--mirror-deferred` to record the configured source; without that flag the
record says `Mirror deferral used: none`. The flag refuses to land when no
profile deferral is configured; scope checking remains the synthesizer's duty.

`train land <n> <pr>` lands one member, under the land lock
([C7](#runtime-contract)). `<pr>` must be the next unlanded member, so `sam`
re-runs the whole [§7](../protocol.md#7-merge-gate-synthesizer) check at
that member's head right before each call (synthesizer brief). It refuses a
train without green CI or already closed. Right before the squash it
re-checks, and stops on the first miss:

- the default branch is still the train's tested state: the train base, then
  the commit the previous member's land made;
- the PR head is the head the train tested;
- no `crew:escalated` or `crew:changes`, and no `crew:hold` unless
  `hold_label_blocks` is false;
- a pass verdict at that head, read as `crew poll` reads it;
- no open rereview: no `pass=steer cmd=rereview` at head without a later
  verdict at head;
- no open coordinator hold: no `hold-until-#<n>` in a review or comment
  whose item `#<n>` is still open;
- a `pass=steer cmd=merge-ok` marker at head, or a `merge_grant` other than
  `none` (`sam` checks the grant's scope);
- GitHub reports the PR `MERGEABLE` against the current default branch.
  `UNKNOWN` and transient API errors are retried up to 10 reads, at most
  3 seconds apart (`--interval` can shorten that);
- the train CI is still green; a pending re-run pauses, and red CI closes it.

It then runs `gh pr merge <pr> --squash --match-head-commit <head>`, checks
that the squash sits on the previous state with the tree of that member's
train commit, and posts the `[<SynthesizerBot>/merge]` record citing the
train branch, SHA, base, train PR and CI run. A real gate failure, or the last
member, ends the train: it closes the train PR and deletes the train branch.
A transient stop prints `paused`, retains the branch and green CI, and can
resume with the same `train land` call. A transient merge-record post failure
retains the completed squash and retries only its post, never another squash.
Resuming re-checks the current default
branch against the tested state; a moved branch closes the train.
`train close <n>` is for a real failure in `sam`'s own check, never an
unsettled mergeability or API read.
On completion or a real stop, deferred/dropped members are automatically
routed: mergeable PRs get a head-bound `update-branch` API call; real conflicts
go by `fix` inbox to an attached builder, or spawn a builder for the linked
issue (respecting the band cap). Holds and transient errors stay queued.
`train route <n>` retries queued entries on a later synthesizer wake without
a coordinator turn; successful routes are not dispatched twice. Each dropped
entry records its merge-up status and last error. A builder reads the train
record to resolve the conflict and uses the existing merge-up re-check.

Each call prints:

```text
landed pr=<pr> head=<head-sha> merge=<merge-sha>
stopped pr=<pr> reason=<why>
paused pr=<pr> reason=<transient cause>
merge-up pr=<pr> status=updated|builder|queued
train-report n=<n> members=<prs> landed=<prs> dropped=<pr:reason,...> stop=<cause>
train n=<n> landed=<k>/<m> next=<pr>
train n=<n> landed=<k>/<m> pr-closed=yes branch-deleted=yes
```

The record's `report` field and every member merge record carry the same
`train-report` fields. The synthesizer copies that line into its status file
after every build, land, pause or close, so the coordinator can report the
whole outcome in one line.

`train bisect <n>` takes a red, unlanded train and splits its members into
halves, preserving landing order. It builds each half on the default branch,
waits for CI, and recurses on every red half until it reports `culprit pr=<pr>`
for a failing singleton. Diagnostic trains close without landing. Changed heads,
a moved diagnostic base, incomplete composition or pending/timed-out CI stop
bisection without inferring a culprit from that test.

Culprits are recorded as `dropped=<pr>:ci-culprit` in the original train report.
The remaining members are rebuilt together on the freshly fetched default
branch, with fresh CI and no `--after` on a failed train. The command prints
`bisect train=<n> remaining=<new-n> ci=pass`; the synthesizer reads that new
record, checks every §7 gate, and lands its members in order through the normal
head-bound `train land <new-n> <pr>` path. Bisection supplies no merge permission.
If both halves pass, the combined retry must also pass before reporting
`culprit=none green-on-retry`. A red combined retry remains unresolved (an
interaction or flake); nothing lands.

### crew dequeue

```sh
scripts/crew dequeue --project <project>/crew.toml [--timeout <seconds>]
```

Caps per band ([Q6](#q6-concurrency), #136): `runtime.options.builders`
(default 5) for busy builders in windows 10–19 and `runtime.options.reviewers`
(default 2) for reviewer passes 20–29. A builder is idle after `done:` until
an inbox message arrives; an unacknowledged message or an `ack:` after the
last completion or a running tool child makes it busy. Idle time comes from
its status-file timestamp. The watcher routes expiry through the builder lead
(or mechanically with no lead) using `crew dequeue --idle-only`; it only
reclaims idle clean/pushed work, with output in `retained/builders/`.
When busy builders reach their cap, or all physical band slots are occupied,
`crew spawn` creates no window, worktree or claim; it appends the request
(role, issue, PR, pass, round, tier, queued time) as one JSON line to
`spawn-queue.jsonl`, prints `queued: <role> <pass> <item> ...` and exits 0.
A window name already running is still refused, not queued.

`crew kill` runs the dequeue step automatically for the freed band.
`crew route` also dequeues after removing a terminal window; the coordinator
does the same in recovery. Explicit dequeue takes the oldest queued request
whose band has a free slot, removes it from the queue
and spawns it as `crew spawn` does; requests for a full band stay queued in
order. When the builder band is physically full but its busy cap permits
queued work, dequeue reclaims the oldest idle builder with no unpushed or
uncommitted work, then spawns the queued request. Builder `done:` also runs
dequeue; capped builder spawns queue a mechanical wake so the watcher runs
route promptly. With no eligible request, the spawn stays queued.

### crew route

```sh
scripts/crew route --project <project>/crew.toml [--timeout <seconds>]
```

The watcher calls this step before waking window 0 (#434). It consumes
`new-head` by spawning review, passed-review `done:` by spawning validation,
and terminal reviewer or synthesizer `done:` by killing and dequeuing.
A terminal reviewer is reaped once even when its PR has since merged, closed,
moved to a new head or been held, whether the router or the reviewer lead
(including a `crew kill` reclaim saved as the completion) routes it first (#719).
Builder completion retains the builder and runs dequeue; it and `fix-at-head` also start review once; an older head's
reviewer windows are removed before starting the new head.
`recheck escalate` starts review at the same head and round, then validation
on a pass; the recheck window is removed.
Red CI after a passed review stays queued for the combined findings handoff;
failed Actions jobs with zero steps become `ci-infra` for the coordinator
and allow validation to start. Job steps are read from the Actions jobs API;
unknown evidence or any started failed job remains `ci-failed`. Neither
classification waives green CI at merge. A `ci-failed` record whose head is
no longer the PR head is dropped, here and by `crew poll` in the queue. A
synthesizer `blocked: ... gate-status REVIEW_URL wait=<items>` line, whose
only unmet items are `ci`, `review`, `validation`, `selfgate` (an express
change, woken by `selfgate-passed`) or `train`, is recorded
without a coordinator wake; other gate-status blocks still wake it. A lead's
`crew send` of `unblocked` to the coordinator with the refs of an earlier
`blocked` message is appended to its inbox without a nudge (#578). Changes results retain their section
files after cleanup. Merged PRs get the
close-out in the coordinator brief: crew labels cleared, the closed issue's
`crew:ready` removed, and that PR's head branch deleted only for a same-repo
head that is neither default nor base. Item windows are cleaned up too.
`pr-closed` reaps the assigned builder without merged-PR label or branch cleanup.
A `fix` or `ci-red` send to a missing `ben-<issue>` with PR/head refs queues a
`builder-message` wake. Route checks the live PR, linkage and head, spawns the
builder's fix pass (or waits for its queued spawn), then delivers the refs.
Live builder messages continue through the existing inbox, including train
merge-ups; combined CI/review handoff rules remain in effect.

Spawns are deduplicated by PR/head/pass/round against live and queued runs,
section files and posted pass markers. An expected `--head` travels through
spawn and dequeue, so a head that changes after a read is refused. Ownership,
holds, escalation, draft and stale-head checks precede routing. Interrupted
batches stay under `wake/queue.jsonl.route-*` for retry. Failed actions and
records needing judgement remain queued for the coordinator. Mechanical
batches leave the watcher running without a model turn or coordinator nudge.

### crew watch

```sh
scripts/crew watch --project <project>/crew.toml [--stale <s>] [--backstop <s>] [--source <command>]... [--source-timeout <s>] [--source-failures <n>] [--no-nudge]
```

The zero-token watcher of [Q1](#q1-wake) (#135). The coordinator runs it as
a background command and re-arms it each turn. It writes its PID to
`wake/watcher.pid` (removed on exit only while it holds its own PID; when the
file already names another live `crew watch`, it exits 1 at once and touches
neither that file nor the watch state, #591), then scans every `--interval` seconds
(default 5) and blocks until one of these is actionable:

- `status:` a new line in any `status/<window>.status` of a recorded run
  (read offsets persist in `wake/watch-state.json`, so a line wakes once);
- `stale:` a run that probes `dead` or `missing`, or one with no status
  progress (status file, else run record) for `--stale` seconds (default 900),
  with no live tool session and no pane output within that interval. Tool
  commands launch separate process sessions; `ps stat` marks their leaders
  with `s`. The watcher walks helper descendants to find those live leaders. For a
  verified live pane, either signal appends a supervisor `heartbeat:` instead
  of waking the coordinator; persistent helpers sharing the harness session,
  harness wrappers and zombie children do not count. Dialogs still wake
  immediately. The supervisor never refreshes a dead or replaced pane,
  skipping a run still starting (no `start` and run-record mtime less than 60 s old),
  unless its last line is `failed:`, or `done:` for a reviewer or
  synthesizer run; a builder after `done:` is not flagged while live (it
  waits for fix rounds) but is when `dead` or `missing`; each (window, last
  progress) fires once, whatever its class; the record's `action` is `restart` for a first
  `dead` / `missing`, otherwise `escalate`, never a restart of a live run.
  A live lead with no undone inbox message, or a live synthesizer with no
  unacked message, uncompleted land, open train or held land lock, is idle,
  not stale (#578);
- `dialog:` a run that probes `ambiguous` with a blocking prompt or a
  fatal API error on its screen (the list under
  [crew status](#crew-status)), on the next scan (well inside
  60 s), not after `--stale`; once per (window, last progress), action
  `escalate`. The coordinator escalates to the owner and never types into
  the role window. Also window 0, when the watcher would have typed its
  wake line into a dialog (below);
- `poll:` each stdout line of a `--source` command (repeatable; the
  `crew poll` hook for #134). A source must be one-shot, for example
  `--source "scripts/crew poll --once --project <project>/crew.toml"`: each
  run is cut off after `--source-timeout` seconds (default 60, so a slow
  `crew poll` on a bad GitHub minute is not cut off) and killed, so a
  looping source never wedges the watcher. `crew poll` retries a transient
  `gh` failure (5xx, timeout, connection reset) with bounded backoff and
  exits 75 (`EX_TEMPFAIL`) if it persists. A cut-off run or an exit 75 is a
  line in `wake/incidents.jsonl`, not a wake; `--source-failures`
  (default 3) of them in a row from one source send one `source-failing:`
  wake with the count, and a clean run resets the count (#702). A
  source that grows `wake/queue.jsonl` itself during the call, as
  `crew poll` does, has its stdout ignored, so its events are queued once;
- `poll:` (or the record's own `reason`) new records in `wake/queue.jsonl`
  from another writer, such as a `crew poll` loop in its own window. The
  queue's inode, byte size and mtime persist in `wake/watch-state.json`; the
  records are already queued, so they are not appended again;
- `ask:` an open owner ask whose deadline has passed. The coordinator
  records each open ask's deadline in `asks/<n>.json` as
  `{"deadline": ...}` (ISO 8601 with its UTC offset;
  [C8](#runtime-contract)). Each (ask, deadline) fires once, on the first
  scan at or after the deadline, and the scan sleep is cut short so that
  scan lands on it, whatever the backstop. An unreadable deadline wakes at
  once;
- with `[triage] enabled` ([profile](../profile.md#triage)), no wake: each
  scan runs the triage sweep timer, which starts
  `crew spawn researcher --sweep` once `interval_hours` passed since the last
  slot in `triage/sweep.json` (at once with no slot recorded, so a crew waking
  overdue sweeps on its first scan), records the slot as `started`,
  `queued` or `failed: <reason>` (retried after 600 s), and records
  `skipped: empty queue` without a spawn when `triage/queue.json` has
  `"items": []`. An unreadable queue sweeps (#748);
- `backstop:` none of these within `--backstop` seconds (default 1800). While
  no run is recorded the interval doubles per idle backstop, capped at 16 ×
  `--backstop`, so waiting costs no model turns.

It appends each wake to `wake/queue.jsonl` as one JSON line (under
`wake/queue.lock`), saves `wake/watch-state.json` after every scan, and runs
`crew route`. If the new records were all mechanical it keeps scanning.
Otherwise it prints one
reason line (`stale: ben-7 dead, silent 1200s, restart`) and exits 0, which
re-invokes the coordinator. So that no single hook or harness feature is the
only wake path ([#160](https://github.com/mw-ding/eng-crew/issues/160)
row 4), it also types the fixed line `wake: watcher` into window 0 when the
coordinator is idle: `claude` or `codex` in the foreground and no output for
`--idle` seconds (default 30), the path the Codex recipe uses; like the
`crew send` nudge, it waits 0.3 s before `Enter`. When window 0 shows a
dialog it types nothing (#315) and queues a `dialog:` wake for window 0
instead (liveness `ambiguous`, action `escalate`). `--no-nudge`
turns this off, for a Claude Code coordinator whose exit wake works and
which would otherwise take a second, empty turn per wake. On SIGTERM,
SIGINT or SIGHUP it removes `wake/watcher.pid`, saves `wake/watch-state.json` and exits
128 + the signal number, so a killed watcher neither looks armed to the
guard nor replays old status lines. A signal that arrives during a scan is
held until the scan's `--source`, `tmux` and `ps` children have exited, so
none is left running after the watcher; between scans, or on a second
signal, it exits at once. Each scan, before it queues or routes wakes, it
compares the mtimes of `scripts/crew`, `crew.d/*.py` and `crew-*.py` with
those at start; when a crew-home update changes one, it re-execs itself in
place (same PID, so `wake/watcher.pid` stays valid) without committing that
scan, so the new code finds the same events and resolves any new profile
keys (#702).

### crew drain

```sh
scripts/crew drain --project <project>/crew.toml
```

How the coordinator empties the wake queue at the start of each turn,
instead of reading and truncating `wake/queue.jsonl` itself. Under
`wake/queue.lock` it renames the queue to `queue.jsonl.drain-<pid>-<hex>`,
then prints every record as one JSON line, oldest first, and deletes the
renamed file. Every writer (`crew poll`, `crew watch`) appends under the same
lock, so a record appended during a drain lands either in the renamed file or
in a new `queue.jsonl`, never in a deleted file. A renamed file left by an
interrupted drain is printed first by the next drain. With no queue it prints
nothing. Exit 0.

### crew status

```sh
scripts/crew status --project <project>/crew.toml
```

A `coordinator` row for window 0 (liveness only: `alive` with `claude` or
`codex` in the foreground, `dead`, or `ambiguous`), then one row per run
record: window, role, item, worktree head (7 characters),
heartbeat age (minutes since the last status line, else since spawn),
liveness and the last status line. Liveness is the C5 probe
([Q7](#q7-failure)), from tmux and `ps`, never from the agent:

- `missing`: no window at the recorded index under that name, or the pane id,
  pane pid or that pid's start time differs from the run record (`crew spawn`
  records all three), so a new window with the same name and harness is
  never taken for the run;
- `dead`: the pane is dead (`#{pane_dead}`);
- `alive`: the expected harness (`claude` or `codex`) is
  `#{pane_current_command}` or a foreground process of the pane's tty;
- `ambiguous`: a dialog on the pane's screen (`tmux capture-pane`, the
  visible screen only), anything else in the foreground, `node` included,
  or tmux cannot answer. A dialog is:
  - a blocking prompt (#289): its heading on a line of its own and its
    footer as the last line on screen. Codex approval:
    `Would you like to …?` over `Press enter to confirm or esc to cancel`;
    Codex folder trust: `Trust this folder?` over `enter continue · esc …`;
    Claude Code permission: `Do you want to …?` (proceed, make this edit,
    create) over `Esc to cancel`. Older Claude Code folder trust uses
    `Do you trust the files in this folder?`, newer versions use
    `Accessing workspace:`, both over `Enter to confirm · Esc to cancel`.
    Codex's `Hooks need review` uses `enter confirm · esc skip` as the final
    line. A prompt echo, diff or file quoting the
    same text has the harness's composer below it, so it never counts;
  - a fatal API error line, after which the harness idles at its prompt
    (#289): Codex `■ {"type":"error","status":4xx|5xx,…}`, Claude Code
    `⎿  API Error: 4xx|5xx {"type":"error",…}`.

### crew restart

```sh
scripts/crew restart <window> --project <project>/crew.toml
```

Restarts a run once: it refuses unless the run probes `dead` or `missing`,
refuses a run whose last status line is `failed:`, or `done:` for a
reviewer or synthesizer run (a builder stays for fix rounds after `done:`,
so a dead one restarts), and refuses a
run already restarted (escalate: `crew:escalated` and the owner channel,
[protocol §5](../protocol.md#5-rounds-and-escalation)). Otherwise it
checks the run's worktree for unlanded work, the same check `crew kill`
uses (uncommitted or untracked paths, commits not on the fetched default
branch, run branch or PR head; a failed check counts as unlanded):

- Clean worktree: `crew kill`, then `crew spawn` with the recorded
  arguments, giving a fresh window and worktree from a fresh fetch.
- Unlanded work: nothing is deleted and `--discard` is never used. It
  kills the dead window and opens a new one at the recorded index (or the
  next free one in the band) in the same worktree, with the same brief,
  claim, engine, model and effort. It verifies the harness start like
  `crew spawn`, records the new pane identity and lists the kept items. If
  the harness does not start, it closes that window and keeps the worktree,
  claim and run record.

Either way the run record gets `restarts: 1`.

A builder whose last line is `done: #<issue> #<pr> <sha>` restarts as
`--pass fix --pr <pr>`, never as a second build pass: the fresh spawn
checks out the PR head, and an in-place relaunch records the fix pass and
appends it to the brief.

When the tmux server or `ash` died, `crew up` rebuilds the session and `ash`
from disk (render, guard, the existing wake queue) and lists the recorded
runs, which now probe `missing`. It never respawns role windows; the
coordinator decides per run with `crew status` and `crew restart`.

### crew doctor

```sh
scripts/crew doctor --project <project>/crew.toml [--org-profile <path>] [--fix]
```

Checks whether this host can run the crew, a subset of the
[bootstrap preflight](../bootstrap.md#q5-preflight-checks) (#190), and
prints one `ok`, `warn`, `fail` or `human` line per check with its fix
hint. It is read-only; `--fix` creates the missing state dir layout and
nothing else. It never changes auth, the repo or a harness config: those
steps (a `gh` login, Codex hook trust, Claude Code folder trust) are listed
at the end for a person. Exit 1 on any `fail`. It also runs for a non-tmux
profile, without the tmux checks. `crew doctor --help` lists the checks.

## Role leads (proposed, #521)

**Review prerequisite.** This design is the first slice of #521 and must be
reviewed before implementation. It describes a future binding; the current
commands, coordinator brief and contract table above remain the running
mechanisms until the implementation ships. Builder and reviewer leads ship
first. Folding the synthesizer into this contract is a later slice.

Delivery is three separately reviewed PRs: [1/3] this design, [2/3] the
builder lead, and [3/3] the reviewer lead. The first two reference #521;
only the last closes it after AC2–AC4 are satisfied. Review of the design
does not claim the implementation is complete.

### Authority and continuity

One long-lived builder lead and one long-lived reviewer lead manage their
own pools. They keep references and scheduling context, re-read GitHub on
every wake, and use the existing role identities and profile engine routing.
The reviewer lead schedules passes; it never writes a review or validation
verdict. Review, validation and recheck workers remain fresh per pass, with
the existing engine diversity rules. A builder worker stays with its issue
through fix rounds, including while waiting after its build reports `done:`.

| Actor | May decide | Must hand off |
|---|---|---|
| Coordinator | Triage, work routing, owner decisions and incident escalation | Builder and reviewer lifecycle to the owning lead |
| Builder lead | Spawn, dequeue, reclaim and restart builder workers within `builders` | Spec ambiguity, exhausted retries, unsafe cleanup and owner asks to coordinator |
| Reviewer lead | Spawn review, validate and recheck; deduplicate, reclaim and restart reviewer workers within `reviewers` | Disputed evidence, exhausted retries and owner asks to coordinator |
| Token-free supervisor | Ensure one session per lead; probe recorded identity; restart a dead or missing lead once | Ambiguous lead or second failure to coordinator |

Leads cannot change gates, round caps, CI-fix caps, ownership, holds, flavors
or merge permission. Decisions use the protocol and resolved profile, with
no project-specific steering. Supervisor recovery grants no permission to
manage workers: the restarted lead reconciles its own pool.

### Recorded handoffs and single consumers

The coordinator records reference-only work for the owning lead. A handoff
names its id, kind, issue or PR, full head SHA where applicable, round and
finding/CI references. Each lead has its own durable queue under
`leads/<role>/`, separate from `runs/`, plus inbox and append-only status
files using C3 delivery and C4 status. The sender retains the handoff until
its `ack:`; a queue item remains pending until a worker's matching output
exists or live state makes the request obsolete. Acknowledgment proves
receipt, not completion.

The watcher and router deliver each pool event to exactly one lead. New
heads, passed review sections, recheck escalation, terminal pass status and
pool liveness events go to the reviewer lead; build/fix handoffs and builder
liveness or terminal issue events go to the builder lead. The coordinator
retains owner asks, triage and incidents. Existing synthesizer routes and
serial-land protection remain in place for this slice.

Queue append, claim and completion are serialized per role. Records move to
an in-flight batch under that lock before dispatch; an interrupted batch is
replayed before newer work. Replayed handoffs are deduplicated against live
workers, pending requests, claims and output markers before any spawn.
Neither coordinator recovery nor `crew kill` may dequeue another pool as a
side effect: slot release wakes the owning lead. Manual lifecycle commands
remain available for owner-directed operations; the coordinator brief uses
only recorded lead handoffs for builder and reviewer lifecycle.

### Scaling policy inputs

Built as the crew scheduler: both leads admit through `crew schedule decide`.
Its [inputs](../scheduling.md#inputs) and [policy](../scheduling.md#policy)
(ranking, target, floors, presence) are the admission rules. Lead sessions
use separate reserved windows outside worker bands; they do not consume a
worker slot or enlarge a cap. A lead still retains held work, retires closed
or superseded requests after a live-state check, never dispatches a stale
fix, and follows profile engine routing and fallback.

Load is an admission input, not evidence that a worker died. Step summaries
provide completed-step evidence; an in-flight suite needs a recorded step
start, worker identity and child-process probe. A recorded start alone never
keeps a worker alive indefinitely. No model turns poll queue depth or load:
the plain-script watcher schedules the backstop and wakes the lead when
deferred work becomes eligible. Scaling down means reclaiming terminal
workers, never interrupting an active build or test to meet a load target.

### Deduplication and recovery

Builder dispatch is keyed by issue, with the adopted open PR and head on
fix requests. It checks both recorded and actual windows and queued work,
adopts an existing closing PR, and resumes a finished build as a fix pass.
It never opens a second PR or treats a waiting builder as a free slot.

Reviewer dispatch is keyed by PR/full head/pass/round, with a rereview steer's
id distinguishing a fresh requested pass at the same head. Live runs,
queued requests, retained section files and posted markers all participate.
Review starts with CI pending; validation follows a passing review subject
to the existing held-CI policy; recheck follows the existing merge-up rules.
A replay of a passing review still starts missing validation even if the
review window was already reclaimed. Older-head sections never suppress
current-head work. Retain sections until their consumers finish; cleanup
must not lose evidence referenced by a pending builder handoff.

Worker and lead probes use C5 identity (pane id, pid and process start time).
Known child build/test processes and recent progress keep a long suite from
being reclaimed solely for status silence. Failed probes, stale progress or
an expired suite deadline are `ambiguous`: re-probe and escalate under Q7,
never launch a duplicate. Only `dead` or `missing` permits one restart;
existing explicit dialog exceptions and all retry caps stay unchanged.
Unlanded work and failed teardown checks keep the worktree under C6.

On lead death, the supervisor preserves queues, in-flight batches, inboxes,
claims, worker records and referenced evidence. It restarts only the lead,
with a new recorded identity; workers continue. Before dispatch the lead
reconciles these records with live GitHub state and actual worker identities,
reattaches live workers, recovers missing outputs, and replays unfinished
handoffs once. A second failure or an ambiguous lead blocks that pool and
wakes the coordinator. Ownership loss stops dispatch and writes under C9;
recovery never resets rounds or clears a hold.

### Implementation and fixture review

After design review, implement the builder lead and its coordinator handoff
first, then the reviewer lead and router handoff. Remove automatic cross-pool
dequeue before enabling either lead so two authorities cannot dispatch the
same work. Supervisor bootstrap and lead queues must be available when the
new coordinator brief is deployed; there is no silent fallback to coordinator
spawns when a lead is absent.

Fixtures for each lead must cover cap exhaustion, released capacity, load
deferral/resumption, duplicate handoffs, held/stale work, dead/missing restart,
ambiguous non-restart, retry exhaustion and interrupted dispatch replay.
Builder fixtures also cover waiting continuity and adoption of an existing
PR. Reviewer fixtures cover fresh passes, same-head rereview, missing
validation after review cleanup, and a long local suite without duplicate
spawn. Supervisor fixtures cover lead death with live workers and intact
queued work. Run the full local suite and render/parity checks before each
implementation push. Runtime evidence must show recorded handoff → lead
dispatch → worker completion → slot reclaim and lead restart with queued
work preserved. This design PR carries no implementation evidence.

## Design credit

The watcher, turn-end guard, delivery-ack and liveness-probe patterns, and
the `bypass` default for role-window permissions, are adapted from
[firstmate](https://github.com/kunchenguid/firstmate)
(MIT license). eng-crew takes the contracts only: no code or text
is copied. Delivery proof differs on purpose: an `ack:` status line instead
of checking the composer; `crew send` reads the composer only to clear its
own stale nudges and confirm its `Enter` submitted (#308). Its
owner-communication etiquette, persona removed, became the coordinator's
[owner communication](../roles.md#owner-communication-coordinator) rules
(#186). Not adopted: its persona and forms of address, relay, remote homes,
the away-mode daemon, non-tmux backends and its dispatch and task-lifecycle
modes.

## Ownership fallback

Configure `repo.control_item` and `runtime.instance` ([profile](../profile.md)).
`crew ownership --project FILE --action start|write|land` reads the shared
[record](../protocol.md#ownership-record). Non-owners read/report only.
`spawn`, `restart`, `send`, `train`, discard and land-lock acquisition refuse; the
Stop guard permits ending the turn while read-only, and keeps its normal block
while draining so the coordinator sees in-flight runs end. Poll emits one
coordinator `ownership:` wake per mode change, with no work events while
read-only or draining. Role briefs repeat the check before pushes, posts, tags
and lands. Draining permits only in-flight writes.

The owner's [handoff chat commands](../protocol.md#owner-handoff-commands) map
to `crew handoff`:

```sh
scripts/crew handoff to <runtime-id> [--mode drain|stop] [--deadline <minutes>] --signature <signature> --project FILE
scripts/crew handoff abort --signature <signature> --project FILE
scripts/crew handoff takeover <runtime-id> --signature <signature> --project FILE
```

Each re-reads the record, refuses an illegal transition (exit 1, nothing
posted) and posts one signed `draining`, `aborted` or `takeover` state on the
control item with the default-branch head and `cmd-id=chat`; `--dry-run`
prints it instead. In drain mode `to` writes `asks/handoff.json` with the
deadline, so the watcher wakes the coordinator then ([C8](#runtime-contract))
and the Stop guard holds the turn; the coordinator deletes it when the drain
ends, and `abort` deletes it. Draining, the coordinator dispatches nothing,
lets each run finish its round, then releases claims. In stop mode, or at the
deadline, it runs `crew kill` on each run except a synthesizer holding the land
lock; `crew kill` keeps unlanded worktrees. The drain ends with
`crew handoff manifest --post` (`offered`, #211).

Resume and prompt stop (#212, [handoff](../handoff.md#resume-and-reconcile)):

```sh
scripts/crew handoff reconcile --project FILE
scripts/crew handoff ack [--rules-confirmed] --signature <signature> --project FILE
scripts/crew handoff lift [--owner-confirmed] [--keep <n>]... --project FILE
scripts/crew handoff stopped --signature <signature> --project FILE
```

The incoming coordinator runs `crew up`, `reconcile` (read-only), then
`ack`, which refuses while a `rule` difference has no owner answer and posts
`acked` with the plan once per handoff id. Before any dispatch it holds each
`hold` set with a note, then runs `lift` once the outgoing side posted
`stopped` (or the owner confirms, or the manifest's release reads the
record), keeping those holds with `--keep`; it re-creates `asks/<n>.json`
for each owner ask still open. On the outgoing side, after the ack poll's
mode becomes `lost`: it queues one `ownership:` wake, the watcher exits and
`crew watch` refuses to re-arm. The coordinator runs `crew handoff stopped`.
Because `crew down` kills window 0, `stopped` re-runs itself detached from
the session (log `handoff-stop.log`; `--foreground` from a shell outside
it). It disarms any watcher, runs `crew down` keeping every worktree
(retrying while the land lock is held), and posts `stopped` with the kept
worktree names once no watcher and no session remain.

## Slack progress notifications

With the [Slack owner-channel profile](../profile.md#backendsconcern), the
coordinator queues notifications only during recorded
[away mode](../protocol.md#owner-away-mode). GitHub remains the tool of record:
post asks there with deadlines and defaults first; Slack may link them but
never supplies answers, approvals, merge-ok or a replacement return brief.

After each event's GitHub record exists, write JSON to a local scratch file
and run `crew notify --project FILE --event-file EVENT_FILE`. Use a stable
`id` from that record (same ID on replay), `kind`, and its full HTTPS `url`.
With this binding, mechanical merge cleanup leaves `pr-merged` for the
coordinator to queue its land message after cleanup.
Every required field below is a nonempty string; use `None` for empty digest
sections and `direct` for a land without a train. Copy URLs from live records.

| Kind | Additional fields | Record / message |
|---|---|---|
| `land` | `title`, `train`, `milestone` | One per landed PR, its train number and milestone advanced |
| `milestone` | `title` | One per completed milestone |
| `release-cut`, `release-published` | `title` | One per release transition |
| `ask`, `sensitive`, `mirror` | `title`, `deadline`, `default` | One per open owner blocker; deadline includes timezone; merge permission has no automatic grant default |
| `main-red` | `title` | Red default-branch run after land; link the run |
| `stop` | `title` | CI provider / billing outage or runtime down; link the incident |
| `digest` | `landed`, `in_flight`, `blocked` | Fresh progress with links to the items in each section |

```json
{"id":"record-id","kind":"land","url":"https://github.com/<owner>/<repo>/pull/123","title":"Result","train":"4","milestone":"M16"}
```

Quiet otherwise: do not queue individual review passes. `crew watch` wakes
the coordinator with `notify-digest` after the profile interval without a
new progress event, including when no PR has landed yet. Build a fresh digest
from live records; use the wake's entry and slot as its stable ID. Reconcile
away state first and skip a digest if newer urgent progress made it obsolete.

The helper re-reads signed coordinator away/return records on the tracking
issue before each delivery; an unreadable record defers delivery. Reaching
`until` alone never ends away mode. State under `notifications/` holds
messages, dedupe IDs and outcomes, never the webhook. Dedupe survives restart
and is scoped to an away entry, event kind and record ID. The watcher polls
away changes at most once per minute when no message is due; every actual
post uses a fresh read. Only one due message is attempted per scan with a
bounded network timeout. Confirmed rejection or connection refusal logs a
sanitized failure and retries after 30, 60, 120 seconds, up to hourly.

Incoming webhooks provide no idempotency guarantee after an ambiguous
transport timeout. Such attempts become `uncertain` and require reconciliation
instead of an automatic resend that could duplicate the event. No failure
blocks builds, reviews or lands; the helper returns success for notification
failures. A running crew requires the webhook in its inherited environment.

On return, record `away-return` first, run `crew notify --project FILE --flush`
to cancel pending messages, and include `crew notify --project FILE --status`
output in the standalone return brief, including recovered failures and
uncertain deliveries. Deliver the brief by the existing recorded owner channel
and tracking issue; Slack stops with away mode. Keep the failure records for
audit. Network delivery of an already-started request may finish during return.
