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
[tmux binding](tmux.md) does today through `scripts/crew-tmux.py`, the M14
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
| Create (C6) | Role run: `tmux new-window -d -t =<session>:<index> -n <window> -c <worktree> -e CREW_<NAME>=<value> ... '<launch>'` ([crew spawn](tmux.md#crew-spawn)); `-d` keeps focus on window 0. Coordinator: `tmux new-session -d -s <session> -n <name> -c <project> -e ... '<launch>'`, then `renumber-windows off` and `base-index 0` on that session only (never `-g`) and the window moved to index 0 ([crew up](tmux.md#crew-up)). A non-zero exit raises tmux's error; `crew spawn` first refuses when `has-session` cannot reach the session. |
| Attach (C8) | `tmux attach-session -r -t =<session>:<index>`; `--rw` drops `-r` ([crew attach](tmux.md#crew-attach)). Detach with the prefix and `d`. Attaching selects the window for every client of the session; indices and names do not change. `crew attach builders` shows the builder band in a temporary tiled session of its own. |
| Doorbell (C1, C3) | `tmux send-keys -l '<line>'`, a 0.3 s settle, then `send-keys Enter`: an `Enter` right behind typed text lands in Codex's paste burst (#308). The composer is read with `capture-pane -p` and `#{cursor_x} #{cursor_y}`; only the doorbell's own stale lines are cleared (`C-u`), `Enter` is retried up to 3 times without retyping, and no key is sent while a dialog is on screen (#315). Not submitted: `crew send` exits 4 ([crew send](tmux.md#crew-send)). |
| Identity probe (C5) | Located by window name at the recorded index (`list-windows -F '#{window_index} #{window_name}'`). Handle: `#{pane_id}` plus `#{pane_pid}` (`display-message -p`). Start time: `ps -o lstart= -p <pane_pid>`. Pane ids are unique only while the tmux server lives and the OS reuses pids, so the start time is required ([Q7](tmux.md#q7-failure)). Order: no window → `missing`; no answer → `ambiguous`; other pane id or pid → `missing`; `#{pane_dead}` → `dead`; other start time → `missing`. |
| State read (C1, C5) | `#{pane_dead}`; `#{pane_current_command}` and the names in the pane tty's foreground process group (`ps -o stat= -o comm= -t <pane_tty>`, `+` in `stat`); `capture-pane -p`, the visible screen only; `#{window_activity}` as the last output time ([crew status](tmux.md#crew-status)). |
| Kill (C6) | `SIGTERM` to the process group of `#{pane_pid}`, up to 2 s, `SIGKILL`, wait again and check the group is gone, then `tmux kill-window -t =<session>:<index>`; `kill-window` alone sends `SIGHUP`, which Codex ignores. A surviving group keeps the window and `crew kill` exits 1 ([crew kill](tmux.md#crew-kill)). `crew down` stops window 0 the same way (unless it runs inside that group), then runs `kill-session`. |

## Adding a session backend

1. Copy the tmux section, name the backend in its heading and fill in every
   operation.
2. An operation the backend cannot meet is a gap against the capability it
   serves. Each binding offering the backend declares it in its contract
   table, in the [gap format](README.md#gap-declaration).
3. Today `scripts/crew` reaches tmux only, through `scripts/crew-tmux.py`.
   The herdr backend, and a profile choice between backends, are M19
   ([#203](https://github.com/mw-ding/eng-crew/issues/203)).
