# Multi-device tmux crew (design)

How one coordinator runs role sessions on several hosts (laptops, a
desktop, cloud VMs, a machine with a simulator or phone attached) joined by
a private overlay network (portable eng-crew roadmap 20.1,
[#158](https://github.com/mw-ding/eng-crew/issues/158); umbrella
[#110](https://github.com/mw-ding/eng-crew/issues/110)). It extends the
[tmux binding](tmux.md); it is not a new binding. It carries out the
owner's [#160 row 6 decision](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6531687881)
and does not re-decide it. Design only: nothing here is built yet; the
build issues are under [Build issues](#build-issues).

This page adds no rule, gate, cap, marker field or label; the
[protocol](../protocol.md) still owns them, and GitHub stays the tool of
record (invariant I5). Every tmux mechanism not named here is unchanged.

## Decisions

Rows citing row 6 restate the owner's decision; the others are this
design's choices within it, including answers to #158's open questions
Q1–Q5.

| Question | Decision | Alternatives considered | Section |
|---|---|---|---|
| What goes on a host (row 6) | One role run: a worktree and a window | A whole home per host, as firstmate's secondmates do: splits the record and the merge lock (row 6) | [Placement](#placement) |
| Placement policy (#158 Q1; row 6) | Project affinity by default; capability exceptions from profile rules; least-loaded among eligible hosts | Static per role: leaves spare capacity idle. Load only: every host must be prepared for every project | [Placement](#placement) |
| Who places (row 6) | A pure function inside `crew spawn`; the coordinator only overrides, with a reason posted on the item | The coordinator choosing by judgment: not reproducible across turns, not testable | [Placement](#placement) |
| Separate binding or tmux capability (#158 Q5) | A capability of the tmux binding: same CLI, session layout and run records, plus a host per run | A `remote-tmux` binding: `runtime.name` picks one binding, but one crew mixes local and remote runs, and every C1–C8 mechanism would be duplicated | [Contract across hosts](#runtime-contract-across-hosts) |
| Engine auth and quota per host (#158 Q2) | Each host keeps its own logins; the profile lists them per host; the tier's engine order is walked first, then hosts. Quota routing stays manual ([roles](../roles.md#quota-routing)): steering around one host's exhausted subscription is a `--host` override or a profile edit | Host first: a warm host would override the owner's engine order (row 7). Shipping logins to hosts: breaks R1 and least privilege. Automatic per-host quota: row 7 defers quota headroom | [Placement](#placement), [Security](#security-model) |
| Merge lock (#158 Q3) | On the primary only. If the primary is gone, nothing lands (fail closed); moving the primary is a runtime handoff ([#157](https://github.com/mw-ding/eng-crew/issues/157)) | Per-host locks: two lands at once. A lock on the tool of record: the backend interfaces offer no atomic lock, and #157's planned ownership marker says who may land | [Contract across hosts](#runtime-contract-across-hosts) |
| Security model (#158 Q4) | Credentials follow roles; the crew SSH key can run one fixed entrypoint only; no forwarding; no secret crosses the wire | Plain SSH with a shell: a leaked primary key is a shell on every host | [Security](#security-model) |
| Remote transport (row 6) | Hardened SSH call to a fixed entrypoint; a per-account runner on the host owns the runs | Runs as children of the SSH session: die with the link and may not see the account's logins. Detached `nohup`: survives, but has no supervisor and the same login gap | [Remote call](#remote-call-and-runner) |
| Wake across hosts | The primary pulls new status lines from each host by offset; hosts never call the primary | Hosts push to the primary: role hosts would need a credential for the primary. A long-lived stream: loses lines when the link drops | [Contract across hosts](#runtime-contract-across-hosts) |
| Unreachable host (row 6) | `unreachable` liveness class: never restarted, here or elsewhere; escalate; reconcile on return | Treat as `dead`: duplicate agents on one item. A fifth C5 class in the contract: deferred until a second runtime has remote runs | [Failure](#failure-and-partition) |
| Review file between passes on two hosts | The primary pulls the review pass's verdict file and hands it to the validate spawn | Pin validate to the review host: blocks a simulator-only validate. Post the review on GitHub first: changes how a verdict is posted | [Placement](#placement) |

## Terms

| Term | Meaning |
|---|---|
| Host | A machine in the profile's inventory, reached by its overlay network name |
| Primary | The one host that runs the coordinator (`ash`), the synthesizer (`sam`), `crew poll`, the watcher, the wake queue, claims and the land lock. It may also run role runs |
| Role host | Any other host. It runs builder and reviewer-validator runs only |
| Project mirror | A persistent clone of one repo on one host. Never a working checkout; every worktree on that host starts from it |
| Ready | `crew host check` passed for this (host, project) |
| Entrypoint | The one command the crew SSH key may run on a host |
| Runner | A per-account service on a host that starts and owns that host's role runs |

## Overlay network assumptions

| # | Assumption | Why | If not met |
|---|---|---|---|
| N1 | Every host joins one private overlay network (any WireGuard-style mesh, for example a Tailscale tailnet) | Hosts in different places reach each other with nothing exposed publicly | Not supported. No host or port is ever exposed publicly |
| N2 | The overlay gives each host a stable name that resolves on the primary | The profile names hosts, never addresses (spec R1) | `crew host check` fails *reachable* |
| N3 | Overlay access rules let the primary open SSH to role hosts; role hosts need no route to the primary or to each other | Commands flow one way; a compromised role host has no lateral path | Works with a wider blast radius; the runbook lists it as a human step |
| N4 | SSH on each host listens on the overlay only | Nothing public | Human step |
| N5 | Role hosts reach GitHub and the engine vendors over their own internet access | Runs fetch, push, post and call engines themselves; the overlay carries crew control traffic only | `crew host check` fails *project mirror* or *logins* |
| N6 | eng-crew configures no overlay | Direction rule; no product names, keys or rules in eng-crew or a profile | n/a |

## Host inventory (profile extension)

Proposal for [#204](https://github.com/mw-ding/eng-crew/issues/204),
building on the [profile schema](../profile.md) (#122). All keys are
optional, so every existing profile stays valid; with no `[hosts]` table the
crew is today's single-machine tmux crew.

```toml
[runtime]
name = "tmux"
options = { builders = 5, reviewers = 2, host_scan_interval = 15 }

[hosts.host-a]
primary = true
capabilities = { os = "macos", arch = "arm64", engines = ["claude-code", "codex"] }
max_runs = 2

[hosts.host-b]
capabilities = { os = "linux", arch = "x86_64", engines = ["codex", "claude-code"] }
max_runs = 4
roles = ["builder", "reviewer"]

[hosts.host-c]
capabilities = { os = "macos", arch = "arm64", devices = ["ios-simulator"], engines = ["claude-code", "codex"] }
max_runs = 1
roles = ["reviewer"]

[placement]
hosts = ["host-b", "host-a"]

[[placement.rules]]
role = "reviewer"
pass = "validate"
paths = ["ios/**"]
needs = { devices = ["ios-simulator"] }
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `hosts.<name>` | table; `<name>` is a DNS label (`[a-z0-9-]`, 1–63 characters) | none | The host's overlay name, also its SSH destination; user, port and key come from the primary's SSH config, by mechanism |
| `hosts.<name>.primary` | boolean | `false` | Exactly one host is `true` |
| `hosts.<name>.capabilities.os` | `linux` or `macos` | *required* | Checked against the host by `crew host check` |
| `hosts.<name>.capabilities.arch` | `x86_64` or `arm64` | *required* | Same |
| `hosts.<name>.capabilities.devices` | list from `ios-simulator`, `ios-device`, `android-emulator`, `android-device` | `[]` | Attached devices; a new kind is a schema change |
| `hosts.<name>.capabilities.engines` | non-empty list of `<engine>` ([profile](../profile.md#engines)) | *required* | Engines logged in on that host |
| `hosts.<name>.max_runs` | integer ≥ 1 | *required* | This crew's concurrent role runs on that host, on top of the band caps |
| `hosts.<name>.roles` | list from `builder`, `reviewer` | both | Roles placed there; the primary also runs the coordinator and synthesizer |
| `hosts.<name>.root` | string: path on that host | `~/.crew` | Mirrors, worktrees and host state; ignored on the primary, which uses [`[paths]`](../profile.md#paths) |
| `hosts.<name>.toolchain_bin` | string: path on that host | none | `<toolchain-bin>` for builders there |
| `placement.hosts` | non-empty list of host names, preferred first | the primary | Project affinity |
| `placement.rules` | array of `{ role, pass?, paths?, needs }` | `[]` | Capability exceptions; first match wins; `needs` takes `os`, `arch`, `devices` |
| `runtime.options.host_scan_interval` | integer ≥ 1 (seconds) | `15` | How often the watcher pulls each role host |

`validate` also fails on: an IP literal, `@` or `:` in a host name; zero or
several primaries; `placement` without `hosts`; a `placement.hosts` entry
that names no host; a role host listing a coordinator or synthesizer role;
a role (`builder`, `reviewer`) that no `placement.hosts` host takes; a rule
whose `needs` no host taking that role can meet; `[hosts]` with a runtime
other than `tmux`; and the existing secret-pattern and unknown-key checks.

**Where it lives.** Host names are not secrets, but they are environment
facts. Keep `[hosts]` and `[placement]` in the project `crew.toml`, which is
already host-local (it holds absolute paths), or in the org / environment
layer shared by several projects; never in eng-crew. `resolve` merges
`hosts` tables by key like any table ([layers](../profile.md#layers-and-precedence)).
One coordinator still runs one repo, so `max_runs` is this crew's budget on
a host; another crew on the same host has its own.

## Placement

`crew spawn` gathers facts, then calls a pure function, tested offline on
fixtures like `crew poll`'s decision function (#134):

```text
place(request, profile, facts) -> (host, engine) | queue(reason) | refuse(reason)
```

- **request:** role, pass, item, tier, the PR's changed paths (none for a
  build), engines to skip (reviewer diversity, invariant I2), and an
  optional override.
- **facts:** per host, ready for this project (which includes its engine
  logins, check 6), reachable, and this crew's live runs there (from the
  primary's run records).

Steps:

1. No `[hosts]`: return the primary, today's behaviour.
2. Coordinator and synthesizer: always the primary (C7).
3. Needs: the `needs` of the first rule matching role, pass and, when
   given, a changed-path glob. No match: no needs.
4. Candidates: no needs, the `placement.hosts` list in order; with needs,
   every host whose capabilities hold them all, affinity hosts first in
   their order, then the rest by name. Drop hosts whose `roles` exclude the
   role.
5. Engine: the first engine of the tier's order, minus skipped engines,
   that some candidate lists. It depends on the profile and the request
   only, never on load, so the engine order stays deterministic (row 7). No
   such engine, or no candidate: refuse with a `blocked:` line, which the
   coordinator escalates.
6. Host: among candidates listing that engine that are ready, reachable and
   below `max_runs`, the lowest ratio of live runs to `max_runs`; ties go by
   candidate order.
7. None: queue in `spawn-queue.jsonl` with one reason per host
   (`host-b: at cap 4/4; host-c: unreachable`). `crew dequeue` retries when
   a run closes and when a host turns ready or reachable.

The band caps ([Q6](tmux.md#q6-concurrency)) are checked before placement,
as today.

**Override.** `crew spawn ... --host <h> --reason "<why>"` replaces steps 4
to 6 with `<h>` and the first engine in order that `<h>` lists. It still
refuses a host that lacks a need, excludes the role, is not ready, is
unreachable, is at cap or lists no eligible engine, and it never moves the
coordinator or synthesizer. Before the spawn it posts the reason on the
item (a narrative post on the PR, else an issue comment), as
`crew kill --discard` does; if the post fails, nothing is spawned.

**Later passes.** A builder's fix rounds reuse its window, so they stay on
its host. A clean restart re-runs placement; an in-place restart (unlanded
work, [crew restart](tmux.md#crew-restart)) stays where the worktree is. A
validate pass may land on another host than its review pass: on the review
pass's `done:` line the primary pulls its verdict file, and the validate
spawn carries it to the validate host.

**Record.** The run record gains `host`, `placement` (`local`, `affinity`,
`capability` or `override` with the post link) and the per-host rejection
reasons. A default placement is a computed fact and stays local; an
override is a decision, so it is on the tool of record.

## Host readiness

`crew host check <host> --project <project>/crew.toml [--fix]` has the shape
of `crew doctor` ([#190](https://github.com/mw-ding/eng-crew/issues/190)):
read-only by default, `--fix` repairs what it can and lists the steps only a
person can take, exit 1 on any `fail`.

| # | Check | Read-only probe | `--fix` | Human step |
|---|---|---|---|---|
| 1 | Reachable | The entrypoint's `version` verb answers in time | none | Join the overlay; fix the SSH config or host key |
| 2 | Version | The host's eng-crew version equals the primary's | none | Install the pinned version on the host (bootstrap, [#144](https://github.com/mw-ding/eng-crew/issues/144)) |
| 3 | Runner | The runner service is up | Install or restart the user-level runner | none |
| 4 | Host doctor | The host's own `crew doctor` checks (tools, Python, tmux, state root) | Its `--fix` | Its human steps |
| 5 | Capabilities | Declared `os` and `arch` match; each device is present (device adapter TBD: `unverified` until one exists, as in [verification](../verification.md)) | none | Correct the profile |
| 6 | Logins | `gh` holds each identity of the host's roles; each listed engine is logged in (harness adapter, [#177](https://github.com/mw-ding/eng-crew/issues/177)) | none: never changes auth | Log in on the host |
| 7 | Project mirror | The mirror exists, fetches, and has the default branch; builders' toolchain path exists | `crew host prepare` | Give the host's identity repo access |
| 8 | Capacity | Free disk under `root` above a floor; live runs against `max_runs` | none | Free disk |

The result is kept on the primary per (host, project) with its time.
`crew spawn` re-runs checks 1–3 (one cheap call) before it places a run
there.

`crew host prepare <host> --project <project>/crew.toml` creates the project
mirror with the host's own `gh` login, or fetches an existing one, creates
the host's worktree and state directories, then runs `crew host check`. It
is idempotent; a failed step leaves the host not ready and names the step.

`crew hosts --project <project>/crew.toml` prints one row per host: name,
primary, OS and arch, devices, engines, roles, ready projects, reachability
(`reachable`, or `unreachable` since a time) and load (this crew's runs
against `max_runs`, and the host's total from its runner).

Host-side layout under `root`:

| Path | Holds |
|---|---|
| `mirrors/<owner>__<repo>.git` | Project mirror |
| `wt/<n>-<sha7>-<role>-<pass>/` | Run worktrees ([C6](README.md#c6-isolation)) |
| `state/<owner>__<repo>/` | `status/`, `inbox/` and `verdicts/` of the runs on this host, their run identity and brief, and the runner's request results |

## Remote call and runner

Contract for [#208](https://github.com/mw-ding/eng-crew/issues/208)
(firstmate's remote transport, as contracts only):

| Property | Contract |
|---|---|
| Transport | SSH over the overlay to the host's profile name. Never prompts (batch mode); strict host-key checking, so a changed key fails and is never auto-accepted |
| Forwarding | None: no agent, X11, TCP or stream forwarding, and no environment sent |
| Dead peer | Bounded connect timeout and keepalive, so a dead link fails in under a minute instead of hanging |
| Entrypoint | The crew key's `authorized_keys` line forces one command and restricts everything else (a TTY only for `attach`). Arguments arrive as one encoded payload, decoded and checked against the verb's schema; never a shell string, never evaluated |
| Verbs | Closed set: `version`, `check`, `prepare`, `spawn`, `probe`, `pull`, `send`, `kill`, `logs`, `capture`, `attach`. Anything else is refused |
| Paths | Every path stays under the host's `root`; `..` and absolute paths elsewhere are refused |
| Idempotency | Mutating verbs carry a request id; a retry with the same id returns the first result, so a retried `spawn` never opens a second window |
| Results | Structured: `ok`, `refused: <reason>` or `failed: <error>`. Only a transport failure, seen by the client, can yield `unreachable` |
| Version | The entrypoint refuses a call from a different eng-crew version: no silent skew after an upgrade |
| One primary per run | The runner tags each run with the primary that spawned it and refuses lifecycle verbs on it from any other primary, so two coordinators never drive one run |
| Runner | A user-level service of the host account (for example a launchd agent or a systemd user unit), never root. It owns the host's crew tmux server, so runs outlive the SSH session and the client, and they start in the account's own session, where some harnesses keep their logins |
| Probe | `probe` and `pull` read tmux and `ps` directly, so liveness still answers while the runner is down; `spawn` needs the runner |

## Runtime contract across hosts

How each [capability](README.md#contract) holds when a run is on a role
host. Runs on the primary use the [tmux table](tmux.md#runtime-contract)
unchanged. Gaps use the [gap format](README.md#gap-declaration).

| Capability | Across hosts | Gap |
|---|---|---|
| C1 Wake on event | Every `host_scan_interval` the watcher makes one `pull` per role host with a run: new status lines since the stored offsets (in `wake/watch-state.json`), plus probe results. It appends the lines to the primary's `status/<window>.status` mirror and wakes as for a local line. `crew poll` stays on the primary | C1 wake on event: partial, compensated by offset-based pulls that resume losslessly and the §6 step 3 sweep after a host returns; residual risk: wakes from an unreachable host wait until it returns or the owner abandons its runs, and remote wakes lag by up to one scan interval |
| C2 One consumer per event | Unchanged: one `crew poll` on the primary decides every consumer; role hosts never read GitHub events. Runs there still fetch, push and post to GitHub themselves | None |
| C3 Messages by reference, proof of delivery | `crew send` calls `send`: the host appends the refs to its `inbox/<window>.jsonl` and types the fixed nudge locally. Proof is still `ack: <msg-id>`, read from the mirrored status file. An unreachable host makes `crew send` fail after the bounded timeout (exit 1), never queue silently; the coordinator then probes | None |
| C4 Status protocol | Runs append to the host's status file; the mirror on the primary is a cache rebuilt by pulling from offset 0. The coordinator reads only primary files | None |
| C5 Liveness | `probe` runs the [Q7](tmux.md#q7-failure) probe on the host, comparing pane id, pane pid and start time on that host's own clock, so clock skew between hosts cannot fake `alive`. Calls failing for 3 scans in a row make the run `unreachable`, a binding class ([Failure](#failure-and-partition)); under C5 it takes `ambiguous`'s action (never restart) and adds: never re-placed | None |
| C6 Isolation | `spawn` fetches the host's project mirror (a failed fetch refuses: no stale base) and creates the worktree from it, with tmux's refusals (the mirror, a branch-named path, an existing path). `kill` runs the unlanded-work check on the host ([crew kill](tmux.md#crew-kill)) and removes only that run's worktree; never the mirror | None |
| C7 Serial land | The synthesizer and `locks/merge.lock` stay on the primary; no host has a lock. Primary gone: no land until it returns or a #157 handoff moves the crew | None |
| C8 Owner channel and SLA | Unchanged: the coordinator's terminal on the primary plus the GitHub post. Remote asks arrive as mirrored `blocked:` lines | As [tmux](tmux.md#runtime-contract) (unchanged); asks from an unreachable host fall under C1's residual risk |
| C9 Ownership handoff | The ownership record is on GitHub, so the guard is unchanged: `crew poll` on the primary reads it each tick, and a run on a role host runs `crew ownership` itself before each push and post (it never lands). Moving the primary is a handoff between two tmux instances ([handoff](../handoff.md#terms)); the runner's one-primary-per-run rule keeps the incoming primary off the outgoing runs. Prompt stop: `crew handoff stopped` on the outgoing primary runs `crew down`, which stops remote runs through `kill` and keeps their worktrees on their hosts; `stopped` names each kept worktree with its host, and the manifest's runs carry the host | C9 ownership handoff: partial, compensated by each run's own guard (read-only once the record moves) and the owner's abandon on the item ([Failure](#failure-and-partition)); residual risk: a run on an unreachable host cannot be stopped, so `crew down` exits 1 naming it and `stopped` is not posted until the host returns or the owner abandons the run; kept worktrees stay on their role hosts |

## Failure and partition

| Case | Detection | Action | Never |
|---|---|---|---|
| Host drops off (link, sleep, power) | Calls to it fail for 3 scans in a row | Its runs become `unreachable`; claims stay; placement skips the host; queued work waits with the reason. After the watcher's `--stale` time, one `escalate` wake per outage: the coordinator escalates on the item and the owner channel ([§5](../protocol.md#5-rounds-and-escalation)) | Restart or re-place the runs |
| Host returns | A call succeeds | Reconcile each run: probe, pull missed lines from the stored offsets, re-read GitHub (§6 step 1). `alive` continues; `dead` or `missing` follows tmux's restart rules on that host | Assume progress from memory |
| Host rebooted | Reachable; probe finds other handles or start times | `missing`; restart once ([Q7](tmux.md#q7-failure)), in place if work is unlanded | Treat a new same-named window as the run |
| Runner down | `spawn` refused, `probe` still answers | Host not ready; `crew host check --fix` restarts the runner; live runs keep going | Count it as `unreachable` |
| Partition, both sides alive | Primary cannot reach the host; the run still reaches GitHub | GitHub stays the truth: `crew poll` still sees its pushes and markers and routes them. No duplicate starts, since the claim stays | Force-push: two writers cannot silently overwrite a branch |
| Owner abandons a host | The owner's decision on the item | On an `unreachable` run, `crew kill <window> --discard --reason "<why>"` posts the reason, drops the run record and claim on the primary (the window cannot be reached) and writes a tombstone; placement may then start a fresh run. On return, reconcile stops the tombstoned run and keeps its worktree for the unlanded-work check | Delete unlanded work |
| Primary down | No scans, wakes or lands | Role runs continue and write status locally; `crew up` reconciles every host from offsets, run records and GitHub | Land from a role host |
| Version skew, changed host key | Entrypoint refuses; host-key check fails | Host not ready; human step in `crew host check` | Auto-update or auto-accept |

`crew down` stops remote runs through `kill`. A run on an unreachable host
keeps its records, and `crew down` exits 1 naming it, as it does for
unlanded work.

## Security model

| Asset | Lives on | Used for | Never |
|---|---|---|---|
| Overlay membership | Each host's overlay client | The network | In eng-crew, a profile or a brief |
| Crew SSH client key | The primary only, by mechanism (agent or key file) | The remote call | On a role host, forwarded, or in a profile |
| Its public half | Each role host's `authorized_keys`, forced to the entrypoint | Entrypoint verbs | A shell |
| Host keys | The primary's known-hosts | Host authentication | Accepted on change without the owner |
| GitHub login | Each host, for the identities of its `roles` only | `GH_TOKEN` derived in the window at launch ([Q5](tmux.md#q5-identities)) | Sent over SSH, put in argv, or written to disk by eng-crew |
| Engine logins | Each host, for the engines it lists | Harness launch | Copied between hosts |
| Repo contents | Mirrors and worktrees | Runs | On a host the owner does not control |

Rules:

- **Credentials follow roles.** A host holds only the logins its `roles`
  need. A reviewer-only host in a profile with a separate reviewer identity
  holds no credential that can push (#158 Q4). A single-identity profile
  ([#111](https://github.com/mw-ding/eng-crew/issues/111)) cannot split
  privilege by token; that residual risk is the same as on one machine.
- Remote reviewer runs keep the single-host engine sandbox
  ([crew spawn](tmux.md#crew-spawn)); being remote adds no write path.
- **Blast radius.** A stolen primary key drives the closed verb set on each
  role host, not a shell. A compromised role host exposes its own logins
  and repos only; it has no route or key to the primary (N3).
- Only hosts the owner controls join; shared or multi-tenant hosts are out
  of scope.

## Observability

| Command | Across hosts |
|---|---|
| `crew status` | Adds a `host` column; liveness may read `unreachable since <time>`; remote rows show the age of the last pull |
| `crew attach <window>\|<role>` | For a remote window, `ssh -t` to the `attach` verb, which runs the host's `tmux attach-session`, read-only unless `--rw` |
| `crew attach builders` | Includes remote builders through `capture`, refreshed every scan |
| `crew logs` | The `logs` verb returns the step summary tail; never raw logs |
| `crew hosts` | The inventory view above |

## Build issues

The milestone M20 issues
([#160 milestones](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6532947853)),
mapped onto this design. Rows marked *proposed* are not filed yet.

| ID | Issue | Scope from this design | Depends on |
|---|---|---|---|
| 20.2 | [#204](https://github.com/mw-ding/eng-crew/issues/204) | [Host inventory](#host-inventory-profile-extension) keys and `validate` rules | #158 |
| 20.3 | [#205](https://github.com/mw-ding/eng-crew/issues/205) | `crew host check` and `crew hosts` ([Host readiness](#host-readiness)) | #204, #190; proposed: also #208 |
| 20.4 | [#206](https://github.com/mw-ding/eng-crew/issues/206) | `crew host prepare` and the host-side layout | #205; proposed: also #208 |
| 20.5 | [#207](https://github.com/mw-ding/eng-crew/issues/207) | `place()`, `--host --reason`, the run record fields and the `crew status` host column | #204 |
| 20.6 | [#208](https://github.com/mw-ding/eng-crew/issues/208) | [Remote call and runner](#remote-call-and-runner): client, entrypoint and verbs, runner, and the failure-semantics doc section | #158 |
| 20.7 | [#209](https://github.com/mw-ding/eng-crew/issues/209) | Two-host dry run, coordinator local and builder remote (#158 AC3) | #205–#208; proposed: also 20.8–20.12 |
| 20.8 | proposed | Remote run lifecycle: `crew spawn`, `kill`, `restart` and `down` executed on the placed host; brief and review-file hand-off | #206, #207, #208 |
| 20.9 | proposed | Remote wake and messages: watcher pulls and status mirror (C1, C4), `crew send` and `crew acked` through `send` (C3), `host_scan_interval` | 20.8 |
| 20.10 | proposed | Partition handling: `unreachable`, reconcile on return, owner-approved abandon with tombstone | 20.9 |
| 20.11 | proposed | Remote `crew attach`, `crew attach builders` and `crew logs` | 20.8 |
| 20.12 | proposed | Runbook "add a host" (overlay, forced-command key, runner, host logins) and host rows in the tmux contract table | 20.10 |

## Design credit

The hardened remote call, the account-owned runner, the readiness check with
a repair mode and "an unreachable remote is never silently replaced" are
adapted from firstmate's remote secondmates
([firstmate](https://github.com/kunchenguid/firstmate), MIT license).
eng-crew takes the contracts only, as for the [tmux binding](tmux.md#design-credit):
no code or text is copied. Not adopted: whole homes per host, a
sub-supervisor per host, and per-host merging (#160 row 6).
