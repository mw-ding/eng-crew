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
| Q1 wake model | Status files, inbox nudges and `crew poll` feed one zero-token watcher; its exit wakes the coordinator; a turn-end guard keeps it armed | [Q1](#q1-wake) |
| Q2 session lifetime | Coordinator and synthesizer for the session; builder window per issue; reviewer and validator windows per pass | [Q2](#q2-lifetime) |
| Q3 coordinator engine | Claude Code or Codex, chosen by profile; role engines by tier routing | [Q3](#q3-coordinator-engine) |
| Q5 identities | Per-role identity from the profile, token derived inside the window at launch; single-identity rule from #111 | [Q5](#q5-identities) |
| Q6 concurrency | Per-band caps, default 5 builders and 2 reviewer passes; serial land under `flock` | [Q6](#q6-concurrency) |
| Q7 failure | Liveness probe from tmux that matches the run identity recorded at spawn (pane id, pane pid and that process's start time), plus watcher stale timers; restart only on `dead` / `missing` | [Q7](#q7-failure) |

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
| `runs/<window>.json` | Run record: index, role, item, worktree, engine, expected harness, start time, run identity (pane id, pane pid and that process's start time), spawn arguments, restart count |
| `inbox/<window>.jsonl` | Messages to a window, one JSON line each, with a `msg-id` |
| `status/<window>.status` | Append-only status lines from a window (`$CREW_STATUS`) |
| `wake/queue.jsonl` | Durable wake queue the coordinator drains each turn (`crew drain`) |
| `wake/queue.lock` | Lock held around each queue append and `crew drain`'s rename |
| `wake/watcher.pid` | PID of the armed watcher; the turn-end guard reads it |
| `poll-state.json` | Last GitHub state seen by `crew poll` |
| `claims/` | Claim files per [protocol §6](../protocol.md#6-duties-on-wake-all-roles) step 2 |
| `spawn-queue.jsonl` | Spawn requests refused by a cap |
| `locks/merge.lock` | Land lock |

Profile paths ([`[paths]`](../profile.md#paths)): `<state-dir>` is
`paths.state_dir` and `<worktree-root>` is `paths.worktree_root`.
`<eng-crew>` is `paths.eng_crew` (#244), the absolute path of the eng-crew
checkout, so rendered briefs cite its docs and scripts (`<eng-crew>/docs/`)
from any repo.

## Runtime contract

How tmux meets each capability, with gaps in the
[gap format](README.md#gap-declaration). Mechanisms only; no rule changes.

| Capability | How tmux meets it | Gap |
|---|---|---|
| C1 Wake on event | Watcher blocks on status files, stale timers and `crew poll`; its exit re-invokes the coordinator, which routes each wake by `crew send` or `crew spawn`; turn-end guard blocks an idle coordinator with no armed watcher ([Q1](#q1-wake)); waiting is token-free: the watcher and `crew poll` are plain scripts, and the backstop doubles per idle wake while no run is recorded, capped at 16 × `--backstop` ([crew watch](#crew-watch)) | C1 wake on event: partial, compensated by `crew poll` diffing against `poll-state.json` and the §6 step 3 sweep on the first wake after the machine resumes; residual risk: no work moves while the machine sleeps or the tmux server is down<br>C1 wake on event (waiting cost): partial, compensated by `--no-nudge` for a coordinator whose exit wake works ([crew watch](#crew-watch)); residual risk: with the default nudge, kept so that no single harness feature is the only wake path ([#160](https://github.com/mw-ding/eng-crew/issues/160) row 4), a Claude Code coordinator may take a second, empty turn per wake |
| C2 One consumer per event | `crew poll`'s decision function maps each GitHub change to one consumer ([protocol §8](../protocol.md#8-safety)); each wake record names one window; terminal `pr-merged` / `pr-closed` go to the coordinator alone, which runs `crew kill`, so the Grok Bot two-watch exception is not needed | None |
| C3 Messages by reference, proof of delivery | `crew send` appends refs only (issue, PR, full SHA, link, path) to `inbox/<window>.jsonl`, then types a fixed nudge `inbox: <msg-id>`; delivery is proven only by `ack: <msg-id>` in the window's status file; no ack in the profile timeout → one re-nudge, then a liveness check; lifecycle goes through `crew kill` and spawn, never message text | None |
| C4 Status protocol | One line per event in `status/<window>.status`: `ack:`, `done:`, `blocked:`, `paused:`, `failed:`, each with refs; the matching GitHub marker stays the record; a window that exits with no `done:` / `failed:` is `missing` or `dead` under C5 | None |
| C5 Liveness | Probe from tmux and `ps`, not the agent: window present, run identity (`#{pane_id}`, `#{pane_pid}` and that process's start time) vs the run record, `#{pane_dead}`, then `#{pane_current_command}` and the pane's foreground process names vs the run record's expected harness ([Q7](#q7-failure)) | None |
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
| `alive` | Window present with the recorded run identity, pane live, expected harness in the foreground | None; a wedge timer with no status progress turns it `ambiguous` |
| `dead` | Window present with the recorded pane id and pid, pane dead or harness gone, no `failed:` (nor `done:` for a reviewer or synthesizer run) | Restart once |
| `missing` | Run record or claim present, and no window, or a window whose pane id, pane pid or that pid's start time differs from the run record | Restart once |
| `ambiguous` | Probe failed, unexpected foreground process, a blocking prompt (trust, hooks review, Codex approval, Claude Code permission) or a fatal API error on screen, or wedge timer expired | Re-probe; after a bounded time escalate to the coordinator; never restart |

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
   harness interactively with a short pointer only, for example
   `claude --permission-mode acceptEdits 'Read your brief at $CREW_BRIEF and
   follow it.'`. Briefs never travel through `send-keys` or argv.
6. Verify start: within the profile timeout, the expected harness must be a
   foreground process of the pane's tty, as for liveness, or
   `#{pane_current_command}`; through a symlinked install that reads as the
   name of the file the link resolves to, which also counts. Otherwise
   record `failed:` and no live run.
7. Write the run record and the claim.

`crew kill <window>`: stop the pane's processes, `tmux kill-window`, then remove only that run's
worktree, build output, run record, inbox, status file and claim, and only
when its work has landed or was explicitly discarded (#172).

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
it uses: every command checks `paths.state_dir`; `spawn`, `kill`, `down` and
`restart` also check `paths.worktree_root`; only `spawn builder` also checks
`paths.toolchain_bin`. An unrendered copy, such as the `crew.toml` inside a
worktree, would put the land lock and state under the worktree. In a window,
use `--project "$CREW_PROJECT"`.

### crew up

```sh
scripts/crew up --project <project>/crew.toml [--org-profile <path>] [--inputs <inputs-dir>]
```

`crew up` (#131):

1. Resolves the profile and refuses unless `runtime.name` is `tmux`.
2. If the session (`runtime.options.session`, default `crew-<owner>-<repo>`)
   is already running, prints the attach command and changes nothing.
3. Renders the briefs with `crew-render.py` into
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
   `-c projects."<project-dir>".trust_level="trusted"`. Claude Code has no
   documented per-project trust option, so a Claude Code coordinator starts
   at its trust dialog in a new project, whose default answer is `No, exit`:
   attach with `crew attach ash --rw` and accept it once. Until then
   `crew status` shows `ash` as `ambiguous`.
   It sets `renumber-windows off` and `base-index 0` on that session only
   (never `-g`), and `crew spawn` / `crew kill` set them again, so a user
   config cannot renumber the index bands.

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
scripts/crew spawn <role> --issue <n> | --pr <n> [--pass <pass>] [--round <k>] [--tier <tier>] --project <project>/crew.toml
```

`crew spawn` (#132) follows [Spawn and kill](#spawn-and-kill) steps 2 to 7;
step 1, the band cap queue, is under [crew dequeue](#crew-dequeue) (#136):

- Roles and passes: `builder --issue <n>` (`build`), `builder --issue <n>
  --pr <n> --pass fix` (a restart; fix rounds normally reuse the window),
  `reviewer --pr <n> [--pass review|validate] [--round <k>]` and
  `synthesizer --pr <n>` (`land`). It refuses when the session is not
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
- Step summaries: `.crew/` is added to the worktree's `info/exclude`, so
  `.crew/runs/**` never counts as unlanded work.
- Pre-trust: Codex gets `-c projects."<worktree>".trust_level="trusted"` for
  that worktree only. Every Codex pass runs `-s workspace-write --add-dir
  <state-dir>/<owner>__<repo>`, so review and validate can write
  `$CREW_STATUS` and `verdicts/` without an escalation prompt. Claude Code: accept its trust dialog once for
  `<worktree-root>`, which covers the worktrees under it (not yet verified on
  the real CLI); an untrusted window waits at the dialog with `claude` in the
  foreground, which liveness probes `ambiguous`.
- Sandbox inheritance: if the coordinator's environment has
  `CREW_SANDBOX_ENV=<NAME>=<value>`, set by the org pack for a nested
  sandboxed session, every window gets `-e <NAME>=<value>`, whatever its
  engine, window 0 included. eng-crew never names the variable.
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
the `SIGHUP` that `kill-window` sends. If the group survives, it keeps the
window, worktree and state files and exits 1. Otherwise it kills the window, removes the
worktree named in `runs/<window>.json` (with the build output inside it)
only when it sits directly under `<worktree-root>`, then deletes that run's
`runs/<window>.*` files (record, brief and any scratch file such as a PR
body), inbox, status file and claim, and a reviewer run's verdict
file. A `review` pass whose last line is `done: … review pass` keeps its
file for the validate pass; killing the `validate` run removes the round's
`review` file too. Nothing else is touched.

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
| New builder `pass=fix` marker at head after a `verdict=changes` there (an evidence-only fix: no new commit, so no `ci-passed`) | `fix-at-head` | reviewer |
| Tracked PR merged / closed | `pr-merged` / `pr-closed` | coordinator |
| `crew:ready` issue newly assigned | `issue-assigned` | builder |

No change emits nothing. Each event is one wake record appended to
`wake/queue.jsonl` before `poll-state.json` is saved (at least once):

```json
{"id": "poll-<ts>-<hex>", "source": "poll", "reason": "poll", "event": "ci-passed", "consumer": "reviewer", "refs": ["#171", "<head-sha>"], "round": 1, "ts": "<ts>"}
```

`ci-passed` and `fix-at-head` records also carry `round`: the verdict round
`k` the review pass is for, 1 + the `verdict=changes` verdict markers since
the latest `cutover` or `resume` marker
([protocol §5](../protocol.md#5-rounds-and-escalation)). A `fix-at-head`
record is the code side of the coordinator's rule for a builder `done:` at
the round's verdict head: spawn the review pass at that head with
`--round <k>`.

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

### crew dequeue

```sh
scripts/crew dequeue --project <project>/crew.toml [--timeout <seconds>]
```

Caps per band ([Q6](#q6-concurrency), #136): `runtime.options.builders`
(default 5) for builder windows 10–19 and `runtime.options.reviewers`
(default 2) for reviewer passes 20–29. When the band already holds its cap,
`crew spawn` creates no window, worktree or claim; it appends the request
(role, issue, PR, pass, round, tier, queued time) as one JSON line to
`spawn-queue.jsonl`, prints `queued: <role> <pass> <item> ...` and exits 0.
A window name already running is still refused, not queued.

The coordinator runs `crew dequeue` after a window closes. It takes the
oldest queued request whose band has a free slot, removes it from the queue
and spawns it as `crew spawn` does; requests for a full band stay queued in
order. With no eligible request it changes nothing.

### crew watch

```sh
scripts/crew watch --project <project>/crew.toml [--stale <s>] [--backstop <s>] [--source <command>]... [--source-timeout <s>] [--no-nudge]
```

The zero-token watcher of [Q1](#q1-wake) (#135). The coordinator runs it as
a background command and re-arms it each turn. It writes its PID to
`wake/watcher.pid` (removed on exit), then scans every `--interval` seconds
(default 5) and blocks until one of these is actionable:

- `status:` a new line in any `status/<window>.status` of a recorded run
  (read offsets persist in `wake/watch-state.json`, so a line wakes once);
- `stale:` a run that probes `dead` or `missing`, or one with no status
  progress (status file, else run record) for `--stale` seconds (default 900),
  unless its last line is `failed:`, or `done:` for a reviewer or
  synthesizer run; a builder after `done:` is not flagged while live (it
  waits for fix rounds) but is when `dead` or `missing`; each (window, last
  progress) fires once, whatever its class; the record's `action` is `restart` for a first
  `dead` / `missing`, otherwise `escalate`, never a restart of a live run;
- `dialog:` a run that probes `ambiguous` with a blocking prompt or a
  fatal API error on its screen (the list under
  [crew status](#crew-status)), on the next scan (well inside
  60 s), not after `--stale`; once per (window, last progress), action
  `escalate`. The coordinator escalates to the owner and never types into
  the role window;
- `poll:` each stdout line of a `--source` command (repeatable; the
  `crew poll` hook for #134). A source must be one-shot, for example
  `--source "scripts/crew poll --once --project <project>/crew.toml"`: each
  run is cut off after `--source-timeout` seconds (default `--interval`, at
  least 5, so a short `--interval` does not cut off a slow `crew poll`),
  killed and recorded as a `source-timeout:` wake, so a looping source never
  wedges the watcher. A
  source that grows `wake/queue.jsonl` itself during the call, as
  `crew poll` does, has its stdout ignored, so its events are queued once;
- `poll:` (or the record's own `reason`) new records in `wake/queue.jsonl`
  from another writer, such as a `crew poll` loop in its own window. The
  queue's inode, byte size and mtime persist in `wake/watch-state.json`; the
  records are already queued, so they are not appended again;
- `backstop:` none of these within `--backstop` seconds (default 1800). While
  no run is recorded the interval doubles per idle backstop, capped at 16 ×
  `--backstop`, so waiting costs no model turns.

It appends each wake to `wake/queue.jsonl` as one JSON line (under
`wake/queue.lock`), saves `wake/watch-state.json` after every scan, prints one
reason line (`stale: ben-7 dead, silent 1200s, restart`) and exits 0, which
re-invokes the coordinator. So that no single hook or harness feature is the
only wake path ([#160](https://github.com/mw-ding/eng-crew/issues/160)
row 4), it also types the fixed line `wake: watcher` into window 0 when the
coordinator is idle: `claude` or `codex` in the foreground and no output for
`--idle` seconds (default 30), the path the Codex recipe uses. `--no-nudge`
turns this off, for a Claude Code coordinator whose exit wake works and
which would otherwise take a second, empty turn per wake. On SIGTERM,
SIGINT or SIGHUP it removes `wake/watcher.pid`, saves `wake/watch-state.json` and exits
128 + the signal number, so a killed watcher neither looks armed to the
guard nor replays old status lines. A signal that arrives during a scan is
held until the scan's `--source`, `tmux` and `ps` children have exited, so
none is left running after the watcher; between scans, or on a second
signal, it exits at once.

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
  - a trust dialog (`trust` and `No, exit`) or Codex's `Hooks need review`;
  - a blocking prompt (#289): its heading on a line of its own and its
    footer as the last line on screen. Codex approval:
    `Would you like to …?` over `Press enter to confirm or esc to cancel`;
    Codex folder trust: `Trust this folder?` over `enter continue · esc …`;
    Claude Code permission: `Do you want to …?` (proceed, make this edit,
    create) over `Esc to cancel`. A prompt echo, diff or file quoting the
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

## Design credit

The watcher, turn-end guard, delivery-ack and liveness-probe patterns are
adapted from [firstmate](https://github.com/kunchenguid/firstmate)
(MIT license). eng-crew takes the contracts only: no code or text
is copied. Delivery proof differs on purpose: an `ack:` status line instead
of checking the composer, so no screen parsing is needed. Its
owner-communication etiquette, persona removed, became the coordinator's
[owner communication](../roles.md#owner-communication-coordinator) rules
(#186). Not adopted: its persona and forms of address, relay, remote homes,
the away-mode daemon, non-tmux backends and its dispatch and task-lifecycle
modes.
