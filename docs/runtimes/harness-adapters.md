# Harness adapter interface

What a runtime must know about one agent CLI (a harness) to launch it in a
role session, wake it and probe it, so adding a harness means filling in one
adapter here, not editing the runtime (portable eng-crew, roadmap 15.4,
[#177](https://github.com/mw-ding/eng-crew/issues/177); fields from
[#160 row 13](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6532100410)).
Each field names the [runtime contract](README.md#contract) capability it
serves. This page adds no rule, gate, cap, marker field or label; the
[protocol](../protocol.md) still owns them.

The Claude Code and Codex adapters record what the tmux binding does today
([tmux.md](tmux.md), M14 and M14.1). A value tmux.md marks as not yet
verified on the real CLI is marked the same way here.

## Fields

| Field | The adapter states | Serves |
|---|---|---|
| Launch line | The command that starts the harness interactively in the run's directory, with the role run's model and effort. The brief goes by pointer only: one short fixed line naming `$CREW_BRIEF`, never the brief in argv or typed keys. Any flag the run needs to write its status file. | C3 |
| Trust and first-run dialogs | Each prompt the harness can show before it reads the pointer, how to avoid it (a pre-trust flag or a one-time owner step) and the screen text that identifies it. A run waiting at one probes `ambiguous`, never `alive`. | C5 |
| Turn-end and wake recipe | How a finished coordinator turn is started again when the watcher exits, the turn-end guard that keeps a turn from ending blind, and how a typed line starts a turn in a role session. | C1 |
| Idle detection | How the runtime tells that the harness is waiting for input, so a typed wake line goes only into an idle session. | C1 |
| Expected foreground process | The process name the liveness probe and the spawn start check expect in the session's foreground while the harness runs. Any other name probes `ambiguous`. | C5 |

Out of scope here: creating the window, attaching, delivering the doorbell
line, probing run identity and stopping the run belong to the session backend
([#178](https://github.com/mw-ding/eng-crew/issues/178)). The tmux stop
signals the process group because Codex ignores the `SIGHUP` that closing a
tmux window sends ([crew kill](tmux.md#crew-kill)).

Every launch line below runs in the window's own shell after
`export GH_TOKEN="$(gh auth token --user "$CREW_IDENTITY")"; exec`, so no
token reaches argv ([tmux.md Q5](tmux.md#q5-identities)). `<pointer>` is
`"Read your brief at $CREW_BRIEF and follow it."`, double-quoted so the shell
expands the path.

## Claude Code (`claude-code`)

| Field | Claude Code |
|---|---|
| Launch line (C3) | Role: `claude --model <model> --effort <effort> --add-dir <state-dir>/<owner>__<repo> <mode-flags> <pointer>`, `<mode-flags>` per `runtime.options.permission_mode` ([crew spawn](tmux.md#crew-spawn)); default `bypass`: `--permission-mode bypassPermissions --settings '{"skipDangerousModePermissionPrompt":true}'`. Coordinator: `claude <pointer>` in the project directory, with no model or effort flags. |
| Trust and first-run dialogs (C5) | Folder trust, with no documented per-project trust option. The dialog's default answer is `No, exit`, so a blind Enter exits. The owner accepts it once with `crew attach <window> --rw`: for the coordinator's project directory, which also covers the role worktrees: Claude Code keys a linked worktree's trust on its repository root (Claude Code 2.1.310). Identified by `trust` and `No, exit` on the pane's screen. Later stops that also probe `ambiguous` ([crew status](tmux.md#crew-status), #289): a permission prompt in `auto` and `safe`, `Do you want to …?` over an `Esc to cancel` last line, and a fatal `⎿  API Error: <4xx or 5xx> {"type":"error",…}` line. |
| Turn-end and wake recipe (C1) | Coordinator: its background `crew watch` command completes and the harness starts a turn. Backup: the watcher types `wake: watcher` into an idle window 0 unless run with `--no-nudge`. Turn-end guard: a `Stop` hook running `crew guard --state <state-dir>/<owner>__<repo>`, which `crew up` adds to `<project>/.claude/settings.local.json`; it blocks at most once per stop cycle (`stop_hook_active`) and is a safety net, not the only wake path ([#160 row 4](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6531265464)). Role session: a typed line plus Enter is a new prompt (the `inbox: <msg-id>` nudge). |
| Idle detection (C1) | `claude` in the foreground and no pane output for `--idle` seconds (default 30), read from tmux's window activity time; no screen parsing. |
| Expected foreground process (C5) | `claude`: as `#{pane_current_command}` or any foreground process of the pane's tty, within the spawn `--timeout` (default 15 s) and then in every probe. The spawn start check also takes the name of the file `claude` resolves to on `PATH` as the pane command, since tmux reports the native installer's symlink by its target's name, the version (for example `2.1.314`, [#286](https://github.com/mw-ding/eng-crew/issues/286)). `node` probes `ambiguous`. |

## Codex (`codex`)

| Field | Codex |
|---|---|
| Launch line (C3) | Role: `codex -m <model> -c model_reasoning_effort=<effort> -c 'projects={"<worktree>"={trust_level="trusted"},"<repo-root>"={trust_level="trusted"}}' <mode-flags> --add-dir <state-dir>/<owner>__<repo> <pointer>`, `<mode-flags>` per `runtime.options.permission_mode` ([crew spawn](tmux.md#crew-spawn)); default `bypass`: `--dangerously-bypass-approvals-and-sandbox`. `--add-dir` lets every pass write `$CREW_STATUS` and `verdicts/` (C4) in `auto` and `safe`. Coordinator: `codex -c projects."<project-dir>".trust_level="trusted" <pointer>`, with no model or effort flags. |
| Trust and first-run dialogs (C5) | Folder trust: avoided by the `projects` table, for the worktree and its repository root, where Codex applies a linked worktree's trust; the `projects."<dir>".trust_level` form did not avoid it on codex-cli 0.164 ([#262](https://github.com/mw-ding/eng-crew/issues/262)). Hooks review: one untrusted hook in the host's own Codex config shows `Hooks need review` in every Codex window; trust every host hook before `crew up`, since answering one window does not persist. Identified by `Hooks need review` on the pane's screen. Folder trust shown anyway: `Trust this folder?` over an `enter continue · esc …` last line. Later stops that also probe `ambiguous` ([crew status](tmux.md#crew-status), #289): an approval prompt in `auto` and `safe` (for example `gh` with no network, [#269](https://github.com/mw-ding/eng-crew/issues/269)), `Would you like to …?` over a `Press enter to confirm or esc to cancel` last line, and a fatal `■ {"type":"error","status":<4xx or 5xx>,…}` line. |
| Turn-end and wake recipe (C1) | Coordinator: a completed background command does not start a turn, so the watcher types `wake: watcher` into an idle window 0 (on by default). Turn-end guard: Codex runs its `notify` program after each turn; the [documented recipe](tmux.md#crew-guard) points it at `crew guard` and types `wake: turn-end guard` into window 0 when it blocks (not installed by `crew up`; not yet verified on the real CLI). Role session: a typed line plus Enter is a new prompt (the `inbox: <msg-id>` nudge). |
| Idle detection (C1) | `codex` in the foreground and no pane output for `--idle` seconds (default 30), read from tmux's window activity time; no screen parsing. |
| Expected foreground process (C5) | `codex`: as `#{pane_current_command}` or any foreground process of the pane's tty, within the spawn `--timeout` (default 15 s) and then in every probe; the start check also takes the name of the file `codex` resolves to on `PATH` as the pane command. Any other name probes `ambiguous`. |

## Adding a harness

1. Copy an adapter section, name the profile's engine id in its heading and
   fill in every field.
2. A field the harness cannot meet is a gap against the capability that
   field serves. Each binding offering the harness declares it in its
   contract table, in the [gap format](README.md#gap-declaration).
3. Today `crew spawn` launches only `claude-code` and `codex` and skips other
   engines in the tier order. The Pi, Cursor and Muse adapters are M19
   ([#200](https://github.com/mw-ding/eng-crew/issues/200)–[#202](https://github.com/mw-ding/eng-crew/issues/202)).

The field list follows #160 row 13; the per-harness layout borrows the
pattern of [firstmate](https://github.com/kunchenguid/firstmate)'s harness
adapter docs (MIT license). No code or text is copied.
