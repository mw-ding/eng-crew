# Session backend interface

What a runtime needs from the program that hosts its role sessions (a
session backend, such as a terminal multiplexer) to create them, show them
to the owner, ring them, probe them and stop them, so adding a backend
means filling in one section here, not editing the runtime (portable
eng-crew, roadmap 15.5,
[#178](https://github.com/mw-ding/eng-crew/issues/178); operations from
[#160 row 13](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6532100410)).
Each operation names the [runtime contract](README.md#contract) capability
it serves. This page adds no rule, gate, cap, marker field or label; the
[protocol](../protocol.md) still owns them.

What runs inside a session (launch line, dialogs, wake recipe, idle rule,
expected foreground process) belongs to its
[harness adapter](harness-adapters.md). The tmux backend records what the
[tmux binding](tmux.md) does today through
`environments/terminal/sessions/tmux/adapter.py`, the
adapter module every tmux call goes through.

## Operations

| Operation | The backend provides | Serves |
|---|---|---|
| Create | A new session object (a window or pane) for one run, never two runs in one, created in the background so the owner's focus does not move. It starts in the run's directory with environment variables that hold names, paths and logins only (never a token), runs the harness adapter's launch line and is addressable by a stable name. It fails loudly when the object cannot be created and refuses when the backend cannot be reached. | C6 |
| Attach | The owner's live view of one session object, read-only by default so keystrokes never reach the agent; typing only on an explicit opt-in. Detaching leaves the run untouched. | C8 (coordinator); [observe](../observe.md#tmux-attach-and-logs) |
| Doorbell | One short fixed line (such as `inbox: <msg-id>` or `wake: watcher`) typed into a session object and submitted, with a check that it left the composer. Nothing is typed while a dialog is on screen, and a line that did not submit is reported, never retyped. The line carries no payload: delivery is proven by the run's `ack:` status line, never by the doorbell. | C1, C3 |
| Identity probe | The session object's unique handle and its start time, read from the backend and the OS, never from the agent ([Identity probe](#identity-probe)). | C5 |
| State read | For an object whose identity matched: whether its process has exited, the names of its foreground processes, its visible screen text and the time of its last output. The runtime matches them against the harness adapter's expected process, dialog text and idle rule. | C1, C5 |
| Kill | Every process of the run's session object stopped, with a grace period and then a forced stop, a check that none survives, then the object removed. If a process survives, the object stays and the call fails. The run's worktree and state files are the runtime's to remove ([C6](README.md#c6-isolation)). | C6 |

## Identity probe

The [C5](README.md#c5-liveness) run identity, as backend operations:

1. **Record.** Once the harness has started (at spawn and at an in-place
   restart), the runtime takes the new object's handle and start time from
   the identity probe and writes both to the run record.
2. **Unique handle.** The handle names one live session object; two live
   objects never share it. A name that a respawn or the owner can reuse,
   such as a window name, only locates the object; it is not the handle.
3. **Start time.** The start of the object's first process, read from the
   OS or the backend. It tells apart two objects that held the same handle
   at different times, since a backend may reuse a handle (for example
   after a server restart).
4. **Compare.** The probe reads both again and compares them exactly with
   the run record before any state read:

| Probe finds | Class |
|---|---|
| No object under the recorded name | `missing` |
| The backend cannot answer | `ambiguous` |
| A different handle or start time | `missing`, never `alive` |
| The recorded handle, its process exited (no start time left to read) | `dead`, which allows the same restart as `missing` |
| The recorded handle and start time | Identity matches; the state read decides `alive` or `ambiguous` |

## tmux (`tmux`)

`<session>` is `crew-<owner>-<repo>` (`runtime.options.session`) and
`<index>` is the run's window index in its band
([layout](tmux.md#layout-and-naming)). Every target is exact:
`=<session>:<index>`.

| Operation | tmux |
|---|---|
| Server | `tmux -L <session>` on every call: the crew's own server, so a pane's bare `tmux` cannot reach the owner's default server (#818). A session started before #818 on the default server (named by path, never an inherited `$TMUX`) stays there until its next `mdstack up`. After a lost server, `mdstack up` stops a recorded lead whose pane process survived, by recorded pid, start time and parent pid 1 ([mdstack up](tmux.md#mdstack-up)). |
| Create (C6) | Role run: `tmux new-window -d -t =<session>:<index> -n <window> -c <worktree> -e CREW_<NAME>=<value> ... '<launch>'` ([mdstack spawn](tmux.md#mdstack-spawn)); `-d` keeps focus on window 0. Coordinator: `tmux new-session -d -s <session> -n <name> -c <project> -e ... '<launch>'`, then `renumber-windows off` and `base-index 0` on that session only (never `-g`) and the window moved to index 0 ([mdstack up](tmux.md#mdstack-up)). A non-zero exit raises tmux's error; `mdstack spawn` first refuses when `has-session` cannot reach the session. |
| Attach (C8) | `tmux attach-session -r -t =<session>:<index>`; `--rw` drops `-r` ([mdstack attach](tmux.md#mdstack-attach)). Detach with the prefix and `d`. Attaching selects the window for every client of the session; indices and names do not change. `mdstack attach builders` shows the builder band in a temporary tiled session of its own. |
| Doorbell (C1, C3) | `tmux send-keys -l '<line>'`, a 0.3 s settle, then `send-keys Enter`: an `Enter` right behind typed text lands in Codex's paste burst (#308). The composer is read with `capture-pane -p` and `#{cursor_x} #{cursor_y}`; only the doorbell's own stale lines are cleared (`C-u`), `Enter` is retried up to 3 times without retyping, and no key is sent while a dialog is on screen (#315). Not submitted: `mdstack send` exits 4 ([mdstack send](tmux.md#mdstack-send)). |
| Identity probe (C5) | Located by window name at the recorded index (`list-windows -F '#{window_index} #{window_name}'`). Handle: `#{pane_id}` plus `#{pane_pid}` (`display-message -p`). Start time: `ps -o lstart= -p <pane_pid>`. Pane ids are unique only while the tmux server lives and the OS reuses pids, so the start time is required ([Q7](tmux.md#q7-failure)). Order: no window → `missing`; no answer → `ambiguous`; other pane id or pid → `missing`; `#{pane_dead}` → `dead`; other start time → `missing`. |
| State read (C1, C5) | `#{pane_dead}`; `#{pane_current_command}` and the names in the pane tty's foreground process group (`ps -o stat= -o comm= -t <pane_tty>`, `+` in `stat`); `capture-pane -p`, the visible screen only; `#{window_activity}` as the last output time ([mdstack status](tmux.md#mdstack-status)). |
| Kill (C6) | `SIGTERM` to the process group of `#{pane_pid}`, up to 2 s, `SIGKILL`, wait again and check the group is gone, then `tmux kill-window -t =<session>:<index>`; `kill-window` alone sends `SIGHUP`, which Codex ignores. A surviving group keeps the window and `mdstack kill` exits 1 ([mdstack kill](tmux.md#mdstack-kill)). `mdstack down` stops window 0 the same way (unless it runs inside that group), then runs `kill-session`. |

## herdr (`herdr`)

Select `session_backend = "herdr"` under `[runtime.options]`, keeping
`runtime.name = "tmux"` for the event/runtime binding.
`environments/terminal/sessions/herdr/adapter.py` uses the installed CLI and
the already-running local default server. It never starts, stops or
reconfigures that shared server, and uses no hooks or agent-reported metadata.
Each run owns one workspace labelled `<session>:<index>:<window>`; workspace display numbers do not set the bands.

| Operation | herdr |
|---|---|
| Create (C6) | `herdr workspace create --cwd <worktree> --label <label> --no-focus --env CREW_<NAME>=<value> ...`, then `herdr pane run <pane-id> 'exec <launch>'`. Refuse an occupied run index or an unreachable server. Only names, paths and logins cross argv; the launch derives credentials inside the pane. Private coordinator environment delivery is unsupported and refused before create. |
| Attach (C8) | `mdstack attach <window>` streams the visible screen without sending keys; Ctrl-C detaches and leaves the run untouched. `--rw` explicitly focuses that workspace and attaches the default herdr client. Tiled `builders` attach is unsupported; attach individual runs. |
| Doorbell (C1, C3) | The shared dialog check runs first. An empty harness composer (`›` or `❯`) must be visible before `pane send-text <pane-id> '<fixed-line>'`, a 0.3 s settle and `pane send-keys <pane-id> enter`. Confirm a new empty composer and no draft holding the line; otherwise report ambiguous, never retype. There are no cursor coordinates, so nonempty or unrecognizable composers refuse input. Delivery still requires the inbox `ack:`. |
| Identity probe (C5) | Locate the workspace by its exact crew label and index, require one pane, read its `terminal_id` from `pane get` and `shell_pid` from `pane process-info`, then `ps -o lstart= -p <pid>`. The terminal handle, PID and OS start time use the existing recorded identity comparison; missing PID means dead, and unavailable process data means ambiguous. |
| State read (C1, C5) | `pane process-info` supplies foreground process names; `pane read <pane-id> --source visible --format text` supplies screen text. Agent lifecycle reports are ignored. The CLI has no last-output timestamp; activity is unknown (`0`), never a fabricated fresh time. |
| Kill (C6) | Use the existing OS process-group and descendant stop: SIGTERM, grace period, SIGKILL, survival check. Only then `workspace close <workspace-id>`. Unavailable probes or surviving groups retain the workspace and fail. Other workspaces and the shared server remain running. |

### herdr capability gaps

The tmux runtime binding's contract applies with these explicit gaps:

- **C1:** no last-output timestamp or cursor coordinates from the CLI.
  Unknown activity remains zero and ambiguous doorbells fail with exit 4;
  this supplies no new liveness or delivery proof.
- **C6:** private coordinator environment delivery is unsupported. A
  coordinator needing it (such as Slack notification credentials) cannot
  start on this backend; use tmux.
- **C8:** single-run read-only attach streams snapshots, without scrollback
  navigation; the tiled builders view is unsupported.
- In-place `mdstack upgrade` uses a tmux-specific respawn and is unsupported;
  stop the crew and restart with the updated install. Remote herdr is out
  of scope ([#203](https://github.com/mw-ding/eng-crew/issues/203)).

## Adapter modules

Each backend is one module, `environments/terminal/sessions/<name>/adapter.py`,
named by its `runtime.options.session_backend` value.
`environments/terminal/crew-session.py` discovers them in sorted name order
(a `_`-prefixed directory is not an adapter). For one release (#1222) an
adapter left at the old `scripts/session.d/<name>.py` is still discovered,
unless `sessions/` has that name. The profile's choices, the
active backend in `environments/terminal/crew.d/_shared.py` and `mdstack doctor`'s
CLI check all come from that discovery. The OS process helpers every backend
shares (start time, parent pid, the process tree under a run) live in
`environments/terminal/crew-proc.py`, not in an adapter.

An adapter declares:

| Name | What it holds |
|---|---|
| `EXECUTABLE` | The CLI `mdstack doctor` looks for on `PATH`. |
| `RANK` | Its place among the choices; an unranked adapter sorts after the ranked ones, by name. |
| `CAPABILITIES` | The optional behaviours below that it supports. |

It provides every operation above as functions: `bind`, `has_session`,
`new_session`, `new_window`, `pin_layout`, `list_windows`, `has_window`,
`kill_window`, `kill_session`, `pane` (the identity and state read:
`id`, `pid`, `dead`, `activity`, `tty`, `command`), `pane_command`,
`foreground`, `capture`, `cursor`, `press`, `send_keys`, `attach`,
`attach_hint` and `view`. A call the backend cannot answer returns `None`
(`pane`, `cursor`, `has_window`) or raises `RuntimeError`; the runtime treats
an unanswered probe as `ambiguous`, never as proof of death.

| Capability | Meaning | Without it |
|---|---|---|
| `doorbell` | `doorbell(name, index, text)` rings the run itself and returns why a line was not submitted, or `None`. | The runtime's cursor-checked composer nudge (`mdstack send`) drives `capture`, `cursor`, `press` and `send_keys`. |
| `reload` | `hold(name, index)` and `respawn(name, index, cwd, env, command)` restart a run in place. | `mdstack upgrade` refuses before stopping any run. |
| `dead-keeps-pid` | An exited object still reports its pid, so a dead probe compares handle and pid. | An exited object with the recorded handle is `dead`. |

The runtime branches on these capabilities and on operation results, never
on a backend's name. tmux declares `reload` and `dead-keeps-pid`; herdr
declares `doorbell`.

## Adding a session backend

1. Copy the tmux section, name the backend in its heading and fill in every
   operation.
2. An operation the backend cannot meet is a gap against the capability it
   serves. Each binding offering the backend declares it in its contract
   table, in the [gap format](README.md#gap-declaration).
3. Add `environments/terminal/sessions/<name>/adapter.py`
   ([Adapter modules](#adapter-modules)) and its tests, with a fake binary on
   PATH. No registry, schema or command edit is needed; keep the default tmux behaviour.
