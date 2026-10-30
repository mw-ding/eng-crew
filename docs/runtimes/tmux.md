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
worktree, build output, run record, inbox, status file and claim, and only
when its work has landed or was explicitly discarded (#172).

## Usage

`scripts/crew` (Python 3.11+ stdlib) is the CLI; every tmux call goes
through `scripts/crew-tmux.py`, so tests run it against a fake `tmux` on
`PATH` (`scripts/test-crew.py`). Run it from an eng-crew checkout:

```sh
scripts/crew up --project <project>/crew.toml [--org-profile <path>] [--inputs <inputs-dir>]
scripts/crew down --project <project>/crew.toml [--org-profile <path>]
scripts/crew spawn <role> --issue <n> | --pr <n> [--pass <pass>] [--round <k>] [--tier <tier>] --project <project>/crew.toml
scripts/crew kill <window> [--discard --reason "<why>"] --project <project>/crew.toml
scripts/crew poll [--once] --project <project>/crew.toml
```

`crew up` (#131):

1. Resolves the profile and refuses unless `runtime.name` is `tmux`.
2. If the session (`runtime.options.session`, default `crew-<owner>-<repo>`)
   is already running, prints the attach command and changes nothing.
3. Renders the briefs with `crew-render.py` into
   `<state-dir>/<owner>__<repo>/render/`. `--inputs` defaults to
   `templates/`, whose [tmux briefs](../../templates/README.md) render to
   `render/runtime/<role>.md` (#137); `crew up` and `crew spawn` use
   `render/briefs/<role>.md` when the inputs have a `core/`, else that file.
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
   It sets `renumber-windows off` and `base-index 0` on that session only
   (never `-g`), and `crew spawn` / `crew kill` set them again, so a user
   config cannot renumber the index bands.

`crew down` refuses while `locks/merge.lock` is held, runs `crew kill` on
each role window (highest index first), then kills the session. If any
window holds unlanded work, it keeps that worktree, names the windows, keeps
the session and exits 1. With no session running it is a no-op.

`crew spawn` (#132) follows [Spawn and kill](#spawn-and-kill) steps 2 to 7;
the band cap queue (step 1) lands in #136:

- Roles and passes: `builder --issue <n>` (`build`), `builder --issue <n>
  --pr <n> --pass fix` (a restart; fix rounds normally reuse the window),
  `reviewer --pr <n> [--pass review|validate] [--round <k>]` and
  `synthesizer --pr <n>` (`land`). It refuses when the session is not
  reachable (the socket check), the window name is taken, the band is full,
  the claim exists or `crew up` has not rendered the role brief.
- Worktree: a detached checkout of a fresh `git fetch` of
  `origin/<default-branch>`, or of `refs/pull/<n>/head` for a `--pr` pass,
  at `<worktree-root>/<n>-<sha7>-<role>-<pass>/`. A failed fetch refuses (no
  stale base); so do a path inside the primary checkout and an existing path.
- Engine: the first `claude-code` or `codex` entry of `engines.<tier>.order`
  (`--tier`, default `default`) with that tier's effort. A reviewer or
  validator skips every engine named in the PR's `Engine:` commit trailers;
  with no trailer the builder counts as non-Claude, so Claude Code goes first.
  Muse Code and OpenCode have no interactive launch yet and are skipped.
- Window: `-e` passes `CREW_ROLE`, `CREW_ID`, `CREW_STATE`, `CREW_STATUS`,
  `CREW_INBOX`, `CREW_BRIEF` and the login `CREW_IDENTITY`, never a token.
  `CREW_BRIEF` is `runs/<window>.brief.md`: the rendered role brief plus the
  run's item, pass, worktree, base SHA, engine and claim path.
- Pre-trust: Codex gets `-c projects."<worktree>".trust_level="trusted"` for
  that worktree only. Claude Code: accept its trust dialog once for
  `<worktree-root>`, which covers the worktrees under it (not yet verified on
  the real CLI); an untrusted window waits at the dialog with `claude` in the
  foreground, which liveness (#135) must probe `ambiguous`.
- Sandbox inheritance: if the coordinator's environment has
  `CREW_SANDBOX_ENV=<NAME>=<value>`, set by the org pack for a nested
  sandboxed session, Codex windows get `-e <NAME>=<value>`. eng-crew never
  names the variable.
- Verify start: `#{pane_current_command}` must become `claude` or `codex`
  within `--timeout` seconds (default 15). Otherwise it prints `failed:`,
  cleans up as `crew kill` does and records no run.
- Records: the claim (`claims/builder-issue<n>` for a build, else
  `claims/<role>-pr<n>-<sha7>`, created atomically) and `runs/<window>.json`.

`crew kill <window>` refuses window 0, kills the window, removes the
worktree named in `runs/<window>.json` (with the build output inside it)
only when it sits directly under `<worktree-root>`, then deletes that run's
record, brief, inbox, status file and claim. Nothing else is touched.

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
  `coordinator`), types the fixed nudge `inbox: <msg-id>` into the window
  through the adapter (`send-keys -l`, then `Enter`) and prints
  `crew: sent <msg-id> to <window>`. The inbox file is the message; the
  nudge carries no payload.
- Delivery is proven only by a line `ack: <msg-id>` in
  `status/<window>.status`; nothing reads the screen. `--wait-ack <secs>`
  waits for it, and `crew acked <window> <msg-id> [--wait <secs>]` checks
  later: exit 0 when acked, 3 with `crew: no ack: ...` when not. The
  re-nudge and liveness check after a missed ack are the coordinator's.
- Lifecycle (interrupt, exit, relaunch) never goes through a message; use
  `crew kill` and `crew spawn`.

### crew poll

`crew poll [--once] --project <project>/crew.toml` (#134) is the GitHub wake
source of [Q1](#q1-wake) and the decision function of [C2](#runtime-contract).
It needs no model and makes read-only `gh` calls only, with the logged-in
identity:

- `gh pr list --state open --json number,state,headRefOid,labels,statusCheckRollup,reviews`;
  a PR counts as a crew PR when it has a `crew:*` label. A tracked PR missing
  from that list is read with `gh pr view <n>` for its merged or closed state.
- `gh issue list --state open --label crew:ready --json number,labels,assignees`.

Per crew PR it keeps the head SHA, the CI rollup (`passed`, `failed` or
`pending`) and the latest verdict at head, read only from hidden `crew:v1`
lines with `role=reviewer-validator pass=verdict sha=<head>`
([protocol §4](../protocol.md#4-marker-conventions)). It compares them with
`poll-state.json` in a pure function and emits one event per change, each to
exactly one consuming role ([protocol §8](../protocol.md#8-safety)):

| Change | Event | Consumer |
|---|---|---|
| CI rollup at head turns green | `ci-passed` | reviewer |
| CI rollup at head turns red | `ci-failed` | builder |
| New `verdict=changes` at head | `review-changes-requested` | builder |
| New `verdict=pass` at head | `review-approved` | synthesizer |
| Tracked PR merged / closed | `pr-merged` / `pr-closed` | coordinator |
| `crew:ready` issue newly assigned | `issue-assigned` | builder |

No change emits nothing. Each event is one wake record appended to
`wake/queue.jsonl` before `poll-state.json` is saved (at least once):

```json
{"id": "poll-<ts>-<hex>", "source": "poll", "reason": "poll", "event": "ci-passed", "consumer": "reviewer", "refs": ["#171", "<head-sha>"], "ts": "<ts>"}
```

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

## Design credit

The watcher, turn-end guard, delivery-ack and liveness-probe patterns are
adapted from [firstmate](https://github.com/kunchenguid/firstmate)
(MIT license). eng-crew takes the contracts only: no code or text
is copied. Delivery proof differs on purpose: an `ack:` status line instead
of checking the composer, so no screen parsing is needed. Not adopted: its
persona and communication style, relay, remote homes, the away-mode daemon,
non-tmux backends and its dispatch and task-lifecycle modes.
