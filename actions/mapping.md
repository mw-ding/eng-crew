# Actions mapping by environment

Status: draft v0.1 (2026-11-07), a snapshot of `main` at
`acc29c0a57702075fe3064e051b29791793c6e17`. Documentation only. It records
how each environment carries out each action in [README.md](README.md)
today; the terminal environment's `crew action` (#1232) is noted at the end.

Source: the mapping tables and gap list of the
[#1213 research finding](https://github.com/mw-ding/eng-crew/issues/1213#issuecomment-6702910041),
re-read against the files named in each row.

## How to read the tables

- **tmux** is the terminal runtime (`runtime.name = "tmux"`), documented in
  [tmux.md](../docs/runtimes/tmux.md).
- **herdr** is the same terminal runtime with
  `runtime.options.session_backend = "herdr"`
  ([session backends](../docs/runtimes/session-backends.md)). It shares
  every tmux command and state file; only session operations differ. "Same
  as tmux" means the same code path, not identical session capabilities.
- **Grok Bot** is the routine-and-parent-turn runtime
  ([grok-bot.md](../docs/runtimes/grok-bot.md)). Entries describe the
  documented routines and templates, not a live probe of the platform.
- **Gap** marks an action an environment does not implement with every
  guarantee in the contract. Under the
  [capability declaration](README.md#capability-declaration) a gap row is
  `unsupported` for that environment until closed. Gaps already declared in
  a binding's contract table are named by their C number.
- The session binding and Hermes are not mapped: session has no runner yet
  ([session.md](../docs/runtimes/session.md)), and no source in this repo
  names a Hermes binding.

## Coordination actions (A1–A8)

| Action | tmux | herdr | Grok Bot |
|---|---|---|---|
| A1 `read` | Roles read GitHub plus inbox, status, run and queue files; `crew poll` snapshots live PR and issue state without a model (`environments/terminal/crew.d/poll.py`) | Same as tmux. Screen and process reads use `pane read` and `pane process-info` | Each routine wake re-reads GitHub, plus shared wiring, claim and watch files |
| A2 `resolve-policy` | Briefs direct the live flavor and path resolution; `scripts/crew-config.py sensitive` and `class-flavor` compute sensitivity and lane | Same as tmux | Same protocol directives in the role templates; express resolves but always runs the normal lane. **Gap:** no express lane |
| A3 `check-ownership` | `crew ownership --action start\|write\|land`, exit 0 permitted, 1 refused (`environments/terminal/crew.d/ownership.py`, `environments/terminal/crew.d/_ownership.py`) | Same as tmux | Control-item guard in routines and parent turns. **Gap:** C9 handoff unsupported, compensated by a manual pause; not covered by the owner's gap acceptance |
| A4 `claim` / `release` | `crew spawn` creates the claim file exclusively; reviewer keys include round and pass; teardown removes its own claim (`environments/terminal/crew.d/spawn.py`, `environments/terminal/crew.d/_shared.py`) | Same as tmux | Role bot takes a `noclobber` claim before dispatching a worker and deletes it after the result |
| A5 `heartbeat` | Builder writes `heartbeat:` into its claim; the watcher writes a separate supervised status heartbeat (`environments/terminal/crew.d/watch.py`) | Same files. **Gap:** herdr gives no activity timestamp, so supervision cannot read activity from the session | Builder worker writes the claim heartbeat; the hourly sweeper flags 15 minutes of silence, then the role bot checks liveness |
| A6 `notify` / `ack` | `crew send` appends refs to `inbox/<window>.jsonl` and types `inbox: <id>`; delivery is proven only by `ack: <id>` in the status file; `crew acked` checks it (exit 3 no ack, 4 ambiguous) (`environments/terminal/crew.d/send.py`, `environments/terminal/crew.d/acked.py`) | Same inbox and ack. The nudge uses `pane send-text` then `pane send-keys enter` and refuses an unknown or non-empty composer (exit 4). **Gap:** C3 partial, declared in tmux.md | Parent-turn bot messages and event routines. A verified B2 handoff proves a watch exists, not that a message was picked up. **Gap:** no general receipt (C3 partial, compensated by the sweeper) |
| A7 `wait` | `crew watch` with `crew poll --once`, status and deadline scans, wake queue, idle backoff and the coordinator turn-end guard (`environments/terminal/crew.d/watch.py`, `environments/terminal/crew.d/guard.py`) | Same watcher. **Gap:** no cursor or activity data from the session | Platform event routines (B1, B2, V1, V2, S1), the steering dispatcher and the hourly sweeper. **Gap:** no `pr-pushed` subscription; V2 starts on CI green; the dispatcher runs on a fixed cron (C1 partial) |
| A8 `report` | Status files read by `crew route`; builder `done:` is pass completion, not process exit (`environments/terminal/crew.d/route.py`) | Same as tmux | Ack and pass markers, claim removal, hold or escalation labels and coordinator messages; the researcher returns `done: ... <url>` to its parent. C4 is met through GitHub records, with no status file |

## Run lifecycle actions (A9–A12)

| Action | tmux | herdr | Grok Bot |
|---|---|---|---|
| A9 `spawn-worker` | The builder or reviewer lead dispatches; `crew spawn` writes the run record, brief and claim, creates the worktree and launches the chosen CLI, or queues it for capacity (`environments/terminal/crew.d/spawn.py`, `environments/terminal/crew.d/lead.py`) | Same admission; launches with `workspace create --no-focus --env ...` then `pane run`. **Gap:** private coordinator environment delivery is unsupported | Role parent turns dispatch fresh workers; a routine that needs B2 or V2 leaves watch creation to the parent; `crew brief` renders the run block |
| A10 `supervise` | `crew status` and the watcher compare pane id, PID and start time plus harness dialogs; the owning lead restarts; `crew kill` stops the process group before removing the window (`environments/terminal/crew.d/status.py`, `environments/terminal/crew.d/kill.py`) | Workspace and pane identity from terminal id, shell PID and OS start time; OS process-group stop, then workspace close. **Gap:** no activity timestamp | Claim, sweeper and role-bot liveness check. **Gap:** no unique handle plus start-time comparison (C5 partial) |
| A11 `workspace` | Fresh fetched detached worktree per run; `crew kill` removes it only after the unlanded-work check or a recorded discard (`environments/terminal/crew.d/spawn.py`, `environments/terminal/crew.d/kill.py`) | Same worktrees; herdr closes only the run's workspace after its processes stop | Unique worker worktrees with cleanup after the pass. **Gap:** no landed or uncommitted check before deletion (C6 partial, not covered by the owner's gap acceptance) |
| A12 `artifact` | Typed files: run records, review sections, queue, ask deadlines, train records and land intents; `crew drain` renames under a lock (`environments/terminal/crew.d/drain.py`, `environments/terminal/crew.d/land.py`) | Same file store; the lead inbox survives a stop | Shared claim, wiring, B2 folder-id and sweeper files plus worker summaries |

## Tool-of-record actions (A13–A20)

| Action | tmux | herdr | Grok Bot |
|---|---|---|---|
| A13 `post-marker` | Backend operations post the record; single-identity verdicts are COMMENT reviews, research is an issue comment, gate-status is edited in place | Same as tmux; herdr is not a review backend | Formal APPROVE or REQUEST_CHANGES reviews from the reviewer identity; other PR narrative is a COMMENT review; research is an issue comment |
| A14 `tracker` | Coordinator and backend operations edit labels, issues and the board; `crew route` handles close-out; triage applies only permitted labels | Same as tmux | Parent turns and routines edit labels and issues; a label change alone does not wake mirror completion, so the coordinator messages the synthesizer. **Gap:** no researcher triage host |
| A15 `run-check` | Local targeted checks and proof; optional `crew runner` on a forge-less host with pinned-head validation and local fallback; the validator re-runs scoped checks (`environments/terminal/crew.d/runner.py`) | Same as tmux; where checks run does not depend on the session backend | Worker checks and GitHub CI; the coordinator renders, deploys and runs drift for the mirror. **Gap:** no forge-less runner |
| A16 `publish-change` | Worker branch and commits, backend change-open and upload; the original body is immutable; the coordinator prunes branches safely | Same as tmux | The worker opens a linked non-draft PR; B2 handles later fixes on the same branch. **Gap:** B1 both has the worker open the PR and forbids worker GitHub posts; the boundary needs a recorded choice |
| A17 `update-base` | Backend update operation or train application; a conflict goes to the builder | Same as tmux | Update at land; a clean previous passing verdict routes to the synthesizer, a conflict to the builder; the rebase strategy forbids trains |
| A18 `compare-content` | `crew content` or the train's member patch comparison over four SHAs (`environments/terminal/crew.d/content.py`, `environments/terminal/crew.d/train.py`) | Same as tmux | The synthesizer calls `crew content` with fetched B, H, B2 and H2, then checks live CI and gates |
| A19 `land` | `crew land-lock`, head-bound backend squash or `crew train land`; async `crew land request\|status\|resume\|done` where configured (`environments/terminal/crew.d/land-lock.py`, `environments/terminal/crew.d/land.py`, `environments/terminal/crew.d/train.py`) | Same as tmux; no separate herdr land path | `flock` plus `gh pr merge --squash --match-head-commit`; immediate manual train. **Gap:** no train timer, pipeline or bisect commands; no async land |
| A20 `owner-channel` | Coordinator terminal plus a signed GitHub ask or closure and a deadline file; the watcher wakes on the deadline; optional notification channel | Same GitHub ask and deadline path; read-only attach streams the screen. **Gap:** private coordinator notification environment unsupported | Coordinator parent chat plus the GitHub record; the sweeper promotes owner waits. **Gap:** the coordinator's own quota meter needs an owner-supplied reading |

## Gaps summary

| Action | tmux | herdr | Grok Bot |
|---|---|---|---|
| A2 `resolve-policy` | | | Gap (no express lane) |
| A3 `check-ownership` | | | Gap (manual handoff, C9) |
| A5 `heartbeat` | | Gap (no activity time) | |
| A6 `notify` / `ack` | | Gap (C3 partial) | Gap (no general receipt, C3) |
| A7 `wait` | | Gap (no cursor or activity) | Gap (no push event, cron dispatcher, C1) |
| A9 `spawn-worker` | | Gap (private env) | |
| A10 `supervise` | | Gap (no activity time) | Gap (C5 partial) |
| A11 `workspace` | | | Gap (C6 partial) |
| A14 `tracker` | | | Gap (no triage host) |
| A15 `run-check` | | | Gap (no forge-less runner) |
| A16 `publish-change` | | | Gap (B1 boundary unresolved) |
| A19 `land` | | | Gap (no timed train, no async land) |
| A20 `owner-channel` | | Gap (private env) | Gap (quota meter) |

Actions not listed have no gap in any of the three environments. No
environment exposes these actions behind one entry point today: commands go
through the tmux runtime helper, which selects the session backend and
refuses other runtime names (`environments/terminal/crew.d/_shared.py`). That single entry
point is the M32 `crew action` command ([cli.md](cli.md)). Since #1232 the
terminal environment (tmux and herdr) runs `check-ownership`, `heartbeat`,
`notify`, `ack` and `report` through it, over the same files and commands
named above; the role policy fragments call those five, and the other
actions still answer `unsupported`
([crew action](../docs/runtimes/tmux.md#crew-action)).
