# Away permission auto-approve

Harness permission prompts (Claude Code `PermissionRequest`) stall an
unattended crew. `scripts/crew-permit.py` lets the owner approve a fixed
allowlist of role commands while an [away entry](protocol.md#owner-away-mode)
is open, without a blanket bypass mode or a hand-written hook per machine
([#646](https://github.com/mw-ding/eng-crew/issues/646)).

This page adds no gate, cap, marker or label. Away still changes no
authority: an approved prompt is a tool call the role was already allowed to
make, and every §7 gate applies.

## What it approves

The hook answers `allow` only when all of these hold. Anything else prints
nothing, so the normal prompt stays:

1. The session is a tagged crew role: `CREW_ROLE` is a core role and
   `CREW_PROJECT` names a project in the trust file.
2. The trust file is a regular, owner-only file with no symlink in its path,
   and neither it nor the hook copy is under a crew root.
3. The project's away record is open, not `quiet`, has an `until`, and that
   time has not passed. The hook reads the record as the coordinator does: the
   signed tracking-issue comments located by `away-control.json`. An open
   entry with `until` null never auto-approves.
4. The checker approves every part of the request (below).
5. The FYI was delivered. If delivery fails, the prompt stays.

Each approval appends a line to `<state>/permit/approvals.jsonl`. The return
brief lists them:

```sh
python3 <eng-crew>/scripts/crew-permit.py log --trust <trust-file> --project <crew.toml> --entry <away-entry>
```

## The checker

The checker is an allowlist. A Bash command is split into simple commands
by its own small tokenizer, which decides from argv rather than a regex over
shell text. Each part must match one rule family:

| Rule | Approves |
|---|---|
| `read` | Read-only tools (`cat`, `grep`, `ls`, `jq`, ...) without state-changing options such as `printf -v`, `sed` line-range prints, `find`/`sort`/`rg` without their writing or executing options, read-only `git` verbs, read-only `gh` verbs and `gh api` GET |
| `crew` | The trust file's `crew` CLI, with a non-install subcommand and `--project` resolving to this project |
| `write` | `mkdir`, `touch`, `cp`, `mv`, `rm`, `tee`, redirects, `git add`, `commit` and `fetch`, and a new branch at HEAD (`checkout -b`, `switch -c`), when every resolved target is under a crew root and outside `.git`, `.claude`, `.codex`, `.mcp.json` and `.envrc` |
| `tracker` | `gh` write verbs in `tracker_verbs` with exactly one `-R` equal to `repo`; `issue create` and `issue comment` on `upstream`; a plain `git push origin <ref>` whose push URL is `repo` |
| `assign` | `NAME=value` for a new shell variable; later expansion uses that value |
| `setup` | A line equal to one of the trust file's `setup` entries |

Always ask: command or process substitution, backticks, `eval`, `source`,
here-docs, subshells, background jobs, environment prefixes, assignments to
inherited or tool-steering variables (`PATH`, `GIT_*`, `GH_*`, ...), unknown
variables (only `CREW_*`, `HOME`, `USER`, `TMPDIR` and `PWD` expand), unquoted
expansions that split or glob, glob write operands, credential paths, the
trust file, recursive deletes that name or contain a root, a second or
conflicting repo selector, a URL naming another repo, force or delete pushes,
`git` verbs that rewrite worktree files (`checkout <path>`, `restore`, `merge`, `pull`, `rm`, `mv`),
package managers, interpreters and network tools. The Write and Edit tools
are `write` checks of their file path.

`check` runs the checker alone, without the away record or an FYI:

```sh
python3 scripts/crew-permit.py check --trust <trust-file> --project <crew.toml> --command 'git status'
```

## Trust file

Trust settings are an owner-only TOML file outside every crew root, keyed by
the project's `crew.toml` path. No `crew.toml` key turns this on, because a
crew can edit its own profile. An empty value revokes that permission.

| Key | Type | Meaning; empty revokes |
|---|---|---|
| `repo` | `owner/name` | Project repo: away record, default FYI, tracker writes and push; empty means nothing is approved |
| `coordinator` | login | Author of the signed away records; empty means nothing is approved |
| `state_dir` | path | Per-project state dir: `away-control.json` and the approval log |
| `roots` | paths | Write roots; empty means no `write` rule |
| `crew` | path | The crew CLI; empty means no `crew` rule |
| `tracker_verbs` | strings | `gh` write verbs on `repo`, such as `"pr create"`; empty means no tracker writes |
| `upstream` | `owner/name` | Repo allowed issue-only verbs; empty means none |
| `setup` | strings | Exact allowed lines; empty means none |
| `fyi` | argv | FYI command that reads the text on stdin; empty means a comment on the away tracking issue |

## Install

Bootstrap lists the install as an optional human step, and the crew never
installs the hook that answers its own prompts. The owner runs it in a
terminal:

```sh
python3 <bundle>/scripts/crew-permit.py install --project <crew.toml>
```

It refuses inside a crew session (`CREW_ID`, `CREW_ROLE` or `CREW_PROJECT`
set), without a terminal, or when the trust dir is under a crew root, the
project's directory or the bundle. It shows the planned trust section, a copy of the hook script
and the `PermissionRequest` entry for `~/.claude/settings.json`, then asks
for confirmation before writing them. The default trust dir is
`~/.config/eng-crew/permit`. Re-running for a project already in the trust
file refuses; edit the file by hand instead.

## Owner channel

The FYI goes through the trust file's `fyi` command. A non-GitHub owner
channel binds it as a pack command map; see
[packs: owner-channel commands](packs.md#owner-channel-commands).

## Not covered

Codex approvals have no hook binding yet. Owner approve or deny over the
owner channel, answered in the prompt's thread, is a follow-up; until then
the normal prompt stays.
