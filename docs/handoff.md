# Runtime handoff (design)

> - **Status:** partly built
> - **Applies to:** tmux and the hand-started session coordinator; Grok Bot guard lines
> - **Current rules:** [ownership record](protocol.md#ownership-record), [§8](protocol.md#8-safety), [§9](protocol.md#9-steering-crew-commands), [C9](runtimes/README.md#c9-ownership-handoff)
> - **Built:** 21.2–21.4 (#210–#212) and A–D (#637–#640) in [Build issues](#build-issues)
> - **Design only:** the 21.5 dry run (#213, open) and row E, the C9 contract tables
> - **Last checked:** 2026-11-04 at `217cec5`

How the owner pauses one crew runtime on a repo and resumes the same work
in another, for example from the Grok Bot crew to a Claude Code or Codex
session (tmux or the session runtime) when orchestration quota runs short,
and back again (roadmap 21.1,
[#157](https://github.com/mw-ding/eng-crew/issues/157); umbrella
[#110](https://github.com/mw-ding/eng-crew/issues/110)). It carries out the
owner's
[#160 row 16 decision](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6532279114)
and does not re-decide it: keep #157's cross-runtime scope, and adopt
read-only fallback, dependency-closed idempotent transfer, retry-until-ack
with a handoff id and prompt stop of the outgoing runtime's wake sources.

The ownership record and guards are implemented by #210 in
[protocol §4](protocol.md#ownership-record), the manifest generator by
[#211](https://github.com/mw-ding/eng-crew/issues/211) ([Manifest](#manifest)),
and on tmux the resume, hold lift and prompt stop by
[#212](https://github.com/mw-ding/eng-crew/issues/212)
([Resume and reconcile](#resume-and-reconcile), [Prompt stop](#prompt-stop)).
The remaining transfer flow below is a design: this page itself adds no
rule, gate, cap or label. It proposes them, and each lands through the [build issues](#build-issues); a change to
what satisfies a gate lands under the
[gate contract](protocol.md#gate-contract) with the owner's merge-ok. Until
then [protocol §8](protocol.md#8-safety) applies as written (only one
automation system may own a repo at a time), and a switch is the manual
pause each binding declares under
[C9](runtimes/README.md#c9-ownership-handoff). GitHub stays the tool of
record (invariant I5).

## Overview

```text
outgoing A                     control item (tool of record)             incoming B
owner: "/crew handoff to B" →  [A/handoff] draining
drain or stop own runs
manifest + offer            →  [A/handoff] offered  (manifest inside)
read-only, waits for ack                                                  install, reconcile
                               [B/handoff] acked                       ←  ack once per id
prompt stop of wake sources →  [A/handoff] stopped                        lift handoff holds,
                                                                          continue each stage
```

| # | Step | Who | Ends with |
|---|---|---|---|
| 1 | [Pause and drain](#pause-and-drain) | Outgoing coordinator, on the owner's command | No run of the outgoing runtime in flight |
| 2 | [Manifest](#manifest) | Outgoing coordinator | One `offered` post carrying the manifest; the outgoing runtime is read-only |
| 3 | [Resume and reconcile](#resume-and-reconcile) | Incoming coordinator | One `acked` post; the incoming runtime owns the repo |
| 4 | [Prompt stop](#prompt-stop) | Outgoing runtime | No wake source of the outgoing runtime can start a pass; a `stopped` post |
| 5 | [Return path](#return-path) | Both, reversed | The same flow from B back to A |

When the outgoing runtime cannot act (quota out, crashed, unreachable), the
owner commands a **takeover** in the incoming runtime instead of steps 1–2.

## Decisions

Rows citing row 16 restate the owner's decision; the others are this
design's choices within it, including answers to #157's open questions
Q1–Q5.

| Question | Decision | Alternatives considered | Section |
|---|---|---|---|
| Scope (row 16 #1) | Between runtime instances on one repo, both ways | Within one runtime only (firstmate's restart and backlog handoffs): does not move work between Grok Bot and a session | [Overview](#overview) |
| Unit of ownership | The repo: one owning runtime instance at a time ([§8](protocol.md#8-safety)). A crew serving several repos hands each off separately | Per item, as today's #111 lane split does by hand (`crew:hold` on roadmap PRs for Grok Bot, `hold_label_blocks = false` for the session): two crews race on land order, update-branch and shared state tags; with a record, the split becomes a handoff. Per crew: one diverged repo blocks the others | [Ownership record](#ownership-record) |
| Where ownership lives | `pass=handoff` markers on one control item per repo, read in post order | A file on a `crew/state` branch: a push is an atomic compare-and-swap, but it may run CI on push, notifies nobody and branch rules may block it. A repo variable or description: not append-only, no audit trail. A local state file: invisible to a runtime on another host (I5) | [Ownership record](#ownership-record) |
| Non-owner (row 16 #2) | Read-only: reads and reports, never starts a pass, posts a pass marker, tags or lands. An unreadable record is read-only for that wake | Stop entirely: the outgoing coordinator could not see the ack. Warn only: two crews act | [Ownership record](#ownership-record) |
| Drain or hard stop (#157 Q1) | The owner's choice: `drain` (default; nothing new starts, runs end by themselves, deadline 30 minutes, then `stop`) or `stop` (kill runs now, keeping unlanded work). A land past its final gate re-check always finishes. `takeover` when the outgoing runtime cannot act | Always drain: a runtime out of quota may never finish. Always hard stop: discards a review minutes from its verdict. Per-pass safe points: not needed, because every external effect is atomic except a land | [Pause and drain](#pause-and-drain) |
| Per-item holds | None by default: the ownership record is the hold. `crew:hold` only for a runtime whose guard predates #210, listed in the manifest so that only those holds are lifted | A hold label on every item (the issue's first shape): many writes, handoff holds look like owner holds, and a tmux crew with `hold_label_blocks = false` ignores it. A new `crew:handoff` label: a second record of what the marker already says | [Pause and drain](#pause-and-drain) |
| Manifest location (#157 Q2; row 16 #7) | On the control item, in the same post as the `offered` marker | A `crew/state` branch file (as above). The umbrella or milestone issue: many comments to page through on every guard read, and it closes. A local outbox file: scratch only (row 16 #7) | [Manifest](#manifest) |
| Manifest format | A short human summary plus one fenced JSON block, references only | TOML: no stdlib writer. YAML: no stdlib parser. Prose only: not machine-readable | [Manifest](#manifest) |
| What moves (row 16 #3) | Dependency-closed sets; the incoming runtime adopts or holds whole sets and skips what it already owns | Item by item: a stacked change or a merge train split by a hold breaks its order. All or nothing: one diverged item blocks the whole handoff | [Resume and reconcile](#resume-and-reconcile) |
| Delivery proof (row 16 #4) | An `acked` marker keyed by the handoff id. Both sides re-read before posting and retry until posted, so a retry is never a second handoff | A message between runtimes: no channel spans two runtimes ([C3](runtimes/README.md#c3-messages-by-reference-with-proof-of-delivery) is within one). No id: a retried offer looks like a new handoff | [Ownership record](#ownership-record) |
| Old runtime stops (row 16 #5) | Read-only from `offered` (from `takeover` in a takeover); wake sources stop after `acked`. Grok Bot routines no-op at once, then are removed | Drain, then stop, with no prompt rule: a lingering watcher or routine acts after ownership moved. Keep no-op routines for good: each event still costs a bot turn ([#109](https://github.com/mw-ding/eng-crew/issues/109)) | [Prompt stop](#prompt-stop) |
| Truth after handoff (row 16 #6) | Live state wins; the manifest is a hint. A pass marker posted while ownership is in transit is re-run, not trusted | Manifest as truth: stale the moment it is posted | [Resume and reconcile](#resume-and-reconcile) |
| Rounds | A handoff never resets rounds: it posts no per-change `cutover` or `resume` marker | A `cutover` per change: resets the round count ([§5](protocol.md#5-rounds-and-escalation)), so a handoff would escape the round cap | [Resume and reconcile](#resume-and-reconcile) |
| Session rules (#157 Q3; row 16 #8) | Rules live in the profile and flavors; the manifest lists their resolved values, and links only to rules not yet in config. A difference is an owner ask before the ack | Rules as manifest text: comment threads again. The incoming runtime adopts the outgoing's rules: a rule changes without the owner | [Session rules as config](#session-rules-as-config) |
| Marker and guard placement (#157 Q4) | One new pass value, `handoff`, with a `state` field. Guard at [§6](protocol.md#6-duties-on-wake-all-roles) step 1 and again right before each push, post and land. Contract capability C9 | A `pass=owner` marker beside `pass=handoff`: two values for one record. Guard at wake start only: a long pass could land after ownership moved | [Ownership record](#ownership-record), [Runtime guards](#runtime-guards) |
| Grok Bot on a handoff marker (#157 Q5) | Every routine's guard no-ops; the parent turns then remove the routines; the return re-creates them and backfills the per-PR watches | Remove routines only: a routine missed in removal still acts. Guard only: no-op wakes keep costing turns | [Runtime guards](#runtime-guards), [Return path](#return-path) |
| Owner command channel | The coordinator chat (the owner channel); the coordinator records each command in its state post with `cmd-id=chat` | A `/crew` comment on the control item: no issue-comment event wakes anyone, so it waits for the next guard read, and it is a second command channel to secure | [Pause and drain](#pause-and-drain) |
| Core or runtime contract (AC2) | Both: the record, the guard and the gate are core; the mechanics are runtime capability C9 | All core: the protocol would name watchers and routines again, which #114 moved out. Fold into C1: C1 wakes; C9 also drains and stops | [Runtime contract](#runtime-contract) |
| Quota trigger (#157 item 6) | The coordinator suggests a handoff; it never switches by itself | Automatic switching: out of scope | [Quota suggestion](#quota-suggestion) |

## Terms

| Term | Meaning |
|---|---|
| Runtime instance | One running crew, written `<runtime>@<instance>`, for example `grok-bot@box`, `tmux@laptop` or `session@laptop`. `<runtime>` is the profile's `runtime.name` (or `session` for a coordinator session that has no binding yet); `<instance>` is a short label the owner picks (proposed key `runtime.instance`), never a host name or path. Two tmux crews on two hosts are two instances, so moving a [multi-device](runtimes/multi-device.md) primary is a handoff |
| Control item | One long-lived tracker item per repo that holds the ownership record and the manifests. On GitHub an issue, with its conversation locked to collaborators. Named by the proposed profile key `repo.control_item` |
| Ownership record | The `pass=handoff` markers on the control item, read in post order |
| Owning runtime | The runtime instance the record names; the only one that may act on the repo. "The owner" still means the human |
| Handoff id | `<yyyymmdd>-<6 hex>`, chosen by the side that opens the handoff; every post of that handoff carries it |
| Set | A dependency-closed group of open items: an issue and its change, plus every open item joined to it by `Depends on`, a stacked base or a merge train |
| Read-only | Reads live state and reports; never starts a pass, pushes, posts a pass marker, sets or clears a state tag, assigns, creates a watch or lands |

## Ownership record

Every state is one coordinator post on the control item, with the signed
header and hidden line of [§4](protocol.md#4-marker-conventions):

```text
[<CoordinatorBot>/handoff] <state> <from> → <to> (<handoff-id>)
<the owner's command or the reason, one line>
<!-- crew:v1 role=coordinator pass=handoff handoff=<handoff-id> state=<state> from=<runtime-id> to=<runtime-id> cmd-id=<cmd-id> sha=<default-branch-head-sha> round=n/a verdict=n/a -->
```

`sha=` is the full default-branch head when the post is made. `cmd-id` is
`chat` for a command given in the coordinator chat, else `n/a`.

| `state` | Posted by | When | Owning runtime after it | Who may act |
|---|---|---|---|---|
| `claimed` | The first runtime to start on a repo with no record (`from=none`) | At start, when the control item has no `pass=handoff` marker | `to` | `to` |
| `draining` | Outgoing coordinator | The owner's handoff command | `from` | `from`, but it starts no new pass |
| `offered` | Outgoing coordinator | Drain done; the post carries the manifest | In transit | Nobody; `to` reconciles (reads only) |
| `takeover` | Incoming coordinator | The owner's takeover command, when `from` cannot act | In transit | Nobody; `to` reconciles |
| `acked` | Incoming coordinator | Reconcile done | `to` | `to` |
| `stopped` | Outgoing coordinator | Its wake sources are stopped | Unchanged | Unchanged |
| `aborted` | The side that opened the handoff | The owner's abort, before `acked` | `from` | `from` |

The owning runtime is a pure function of the record:

1. Only well-formed markers posted on the control item by a login in the
   reading profile's `identities` or `owners` count. Others are ignored and
   reported to the owner.
2. The earliest `claimed` wins when no earlier marker exists; a later
   `claimed` is ignored. This tie-break settles two runtimes starting at
   once, since the backends offer no atomic lock
   ([multi-device](runtimes/multi-device.md#decisions)).
3. One handoff is open at a time. `draining` or `takeover` opens one;
   `acked` or `aborted` closes it. An opener whose `from` is not the owning
   runtime, or a second opener while one is open, is ignored and reported.
   The exception is a `takeover` with the open handoff's id, after its
   `draining` or `offered`: the outgoing runtime stopped answering mid-way.
4. `acked` counts only with the open id and its `to`; the first one wins.
5. `pass=handoff` markers sit on the control item, not on a change, so they
   never touch a change's round count.

**Guard.** Each role reads the record at
[§6](protocol.md#6-duties-on-wake-all-roles) step 1, and again right before
each push, post and land, as the synthesizer already re-reads before it
merges:

| The record says | This runtime |
|---|---|
| No record (no control item set, or no marker) | Acts as today; `crew doctor` warns. Its first start after a control item exists posts `claimed` |
| Owning, no open handoff | Acts |
| Owning, `draining` | Finishes in-flight passes; starts nothing |
| In transit, and this runtime is `to` | Reconciles (reads only), then posts `acked` |
| Anything else | Read-only |
| Unreadable (API error) | Read-only for this wake; the next wake retries |

A read-only coordinator still talks to the owner (the repo is owned by
`<runtime-id>`), and posts only its side's handoff states: `offered`,
`stopped` or `aborted` as the outgoing side, `takeover` or `acked` as the
incoming side.
Owner-SLA duties ([§6](protocol.md#6-duties-on-wake-all-roles)) belong to
the owning runtime; an auto-apply time that passes while ownership is in
transit is applied by the incoming runtime right after its ack.

**Gate contract for #210.** Landing only as the owning runtime is a new
[§7](protocol.md#7-merge-gate-synthesizer) gate, so #210 states it in the
same change and needs the owner's merge-ok:

| Gate | Satisfied by | Who / how fast | Fail-open | Binding |
|---|---|---|---|---|
| Owning runtime | The ownership record names this runtime instance with no handoff open, or no record exists | The owner commands; coordinators post within a turn | The owner aborts the open handoff (the outgoing runtime owns again) or commands a takeover (the incoming owns); no merge-ok or standing grant lands as a non-owner; CI is never waived | core |

## Pause and drain

The owner gives the command in the coordinator chat:
`/crew handoff to <runtime-id> [drain | stop] [deadline <minutes>]`, or
`/crew handoff abort`, or, to the incoming coordinator,
`/crew takeover from <runtime-id>`. The coordinator records it in the state
post (bot text never starts with `/crew`).

| Mode | Use | In-flight runs | Ends when |
|---|---|---|---|
| `drain` (default) | A planned switch | Run to their end; nothing new starts, lands included | Every run has ended, or the deadline (default 30 minutes) passes; then as `stop` |
| `stop` | Quota is out now | Killed now; worktrees with unlanded work stay ([C6](runtimes/README.md#c6-isolation)); a land past its final gate re-check finishes | The land lock is free |
| `takeover` | The outgoing runtime cannot act | Untouched; each one's guard turns it read-only at its next check | The incoming runtime's ack |

`stop` is safe at any moment because every external effect is atomic: a
push lands whole or not at all, and so does a post. The one multi-step
sequence is a land (the merge, then the `merge` post) under the land lock;
the owning-runtime check is part of its final gate re-check, and past that
re-check it finishes. What a stopped run leaves, and what the incoming
runtime does:

| Pass in flight | Drain | Stop leaves | Incoming runtime |
|---|---|---|---|
| Builder build, fix or ci-fix | Finishes the round: push and fix note | Pushed commits, perhaps no fix note; unpushed work in the kept worktree | Continues the round at the branch head and posts the note; lists the kept worktree for the owner |
| Review or validation | Posts its verdict | No verdict at head | Runs the pass at head (no marker at head, §6 step 2) |
| Land past its final re-check | Finishes | Finishes | Close-out from live state if the `merge` post is missing |
| Merge train ([tmux](runtimes/tmux.md#crew-train)) | Finishes the train | The whole train stops | Re-checks the train's PRs as one set |
| Coordinator turn | Finishes | Ends after its current post | Reconciles |

**Holds.** No per-item label by default: the record stops every runtime
whose guard reads it. For a runtime whose guard predates #210 (Grok Bot
until #140 deploys the new render), the outgoing coordinator, or the
incoming one in a takeover, adds `crew:hold` to each open crew item without
one and lists exactly those items in the manifest's `holds_added`, so the
incoming runtime lifts only what the handoff added.

Outgoing coordinator, in order:

1. Post `draining` with the mode and deadline.
2. Drain or stop its runs; release its claims.
3. Generate the [manifest](#manifest) from live state and its own run
   records, and post it with `offered`. From here it is read-only.
4. Check for the ack on its backstop (the tmux watcher backstop, the Grok
   Bot sweeper). With no ack after the owner SLA's 2 awake hours, remind
   the owner how to start the incoming runtime. Re-post the same `offered`
   only if the earlier post is missing on re-read; never open a second
   handoff while one is open.
5. On `acked`: [prompt stop](#prompt-stop), then post `stopped`.

## Manifest

One post on the control item: the human summary, the JSON block, then the
`offered` marker. In a takeover the incoming runtime runs the same
generator from live state and posts the result with its `acked`, so the
record holds a manifest either way.

| #157 asks for | Field |
|---|---|
| Per open issue or PR: stage, head SHA, last verdict and round, pending owner decisions, in-flight claims | `sets[].items[]`: `stage`, `pr`, `head`, `verdict`, `ci`, `labels`, `owner_asks`, `runs` |
| Active milestone and dependency order | `milestone`, `sets[].order`, `items[].depends_on` |
| Active session rules and standing grants, with links | `rules`, `links` ([Session rules as config](#session-rules-as-config)) |
| Backlog | `backlog` |
| Known gotchas | `gotchas` |

Rules:

- **References only:** item and PR numbers, full SHAs, links, worktree
  names, profile keys. Never a diff, log, chat quote, token or real path
  (spec R1, R2). The generator runs the
  [secret scan](../scripts/README.md#what-it-checks) patterns on the post
  and refuses on a match.
- **From live state, not memory:** items, labels, heads, CI and verdicts
  from the backend; runs from the runtime's own records; owner asks from
  their posts, with each deadline unchanged.
- **One post:** within the backend's post limit (65,536 characters on
  GitHub). If it would not fit, `backlog` shrinks to one link per milestone;
  an open item is never dropped.
- **Versioned:** `schema` is `crew-handoff/1`. A reader refuses an unknown
  major version and asks the owner.

**Generator (#211).** On tmux, `crew handoff manifest` fills
[templates/handoff-manifest.md](../templates/handoff-manifest.md) for this
runtime's open `draining` handoff: open crew items, open PRs and their open
`Depends on` / `Closes` items as sets, stage, head, labels, runs from its run
records (worktree name only), the resolved `flavor.*` and merge grant rules,
and the backlog. With `--post` it re-reads the record before every attempt
and posts only while no `offered` post with that id exists, so a retried or
timed-out post is never a second one; after `acked` it posts nothing.
`crew handoff reconcile` is the incoming side's read-only plan: per set
`adopt`, `hold` (an open PR's head moved since the manifest) or `skip`
(every item already claimed here), plus `missed` crew items; #212 extends
it to the whole [reconcile table](#resume-and-reconcile). Verdicts, CI,
owner asks, milestone and gotchas fields are not generated yet.

### Manifest template

````markdown
[<CoordinatorBot>/handoff] offered <from> → <to> (<handoff-id>)

**TL;DR:** <n> open items in <k> sets, milestone <milestone>; <a> owner asks pending; mode <mode>; <h> holds added.

| Set | Items | Stage | Head | Next |
|---|---|---|---|---|
| s1 | #<issue> / #<pr> | changes | <sha7> | fix round <k> |

Rules: <profile keys and values>. Not yet in config: <links>. Backlog: <count>. Gotchas: <links>.

```json
{
  "schema": "crew-handoff/1",
  "handoff": "<handoff-id>",
  "repo": "<owner>/<repo>",
  "from": "<runtime-id>",
  "to": "<runtime-id>",
  "mode": "drain",
  "eng_crew_version": "<vX.Y.Z>",
  "default_branch": {"name": "<default-branch>", "sha": "<default-branch-head-sha>"},
  "milestone": {"active": "<milestone>", "tracking": "#<n>"},
  "sets": [
    {"id": "s1", "order": 1, "items": [
      {"issue": "#<issue>", "pr": "#<pr>", "stage": "changes",
       "head": "<head-sha>", "ci": "passed",
       "verdict": {"round": 1, "result": "changes", "post": "<url>"},
       "labels": ["crew:changes"], "depends_on": ["#<n>"],
       "owner_asks": [{"post": "<url>", "default": "<default>", "deadline": "<ISO 8601>"}],
       "runs": [{"role": "builder", "pass": "fix", "end": "stopped", "worktree": "<worktree-name>"}]}
    ]}
  ],
  "holds_added": ["#<n>"],
  "rules": [{"key": "runtime.options.merge_grant", "value": "<value>", "source": "<url>"}],
  "links": [{"rule": "<rule>", "source": "<url>"}],
  "backlog": ["#<n>"],
  "gotchas": ["<url or one line>"]
}
```

<!-- crew:v1 role=coordinator pass=handoff handoff=<handoff-id> state=offered from=<runtime-id> to=<runtime-id> cmd-id=n/a sha=<default-branch-head-sha> round=n/a verdict=n/a -->
````

`stage` is a state tag name without `crew:` (`ready`, `in-review`,
`changes`, `approved`, `hold`, `escalated`, `needs-md`), or `build` for an
assigned item with no change yet. A run's `end` is `done`, `stopped` or
`kept` (unlanded work left in that worktree).

## Resume and reconcile

Incoming coordinator, in order:

1. **Install.** `crew bootstrap` with the project profile
   ([bootstrap](bootstrap.md), #144), or `crew doctor` on an existing
   install; the self-test passes and `runtime.instance` is set.
2. **Find the handoff.** The open handoff whose `to` is this runtime, in
   state `offered`; or, on the owner's command, post `takeover` (reusing
   the open handoff's id if there is one).
3. **Reconcile** each set against live state (the table below), reading
   only. The manifest is a hint; live state wins. A diverged set is only
   planned as held here.
4. **Rules.** Compare the manifest's `rules` with its own resolved profile.
   Any difference is an owner ask before the ack; the incoming runtime
   never silently adopts or drops a rule.
5. **Ready its wake sources** ([Return path](#return-path) for Grok Bot;
   `crew up` for tmux).
6. **Ack.** Re-read the record; if an `acked` with this id exists, stop.
   Otherwise post `acked`, and retry until it is posted. Then, before any
   dispatch, apply the holds planned in step 3 (`crew:hold` with a
   coordinator note), so no diverged set is adopted with the others.
7. **Lift holds.** Remove `crew:hold` from the `holds_added` items only
   once the outgoing runtime has posted `stopped`, or the owner confirms
   its wake sources are gone, or its guard reads the record (the
   manifest's `eng_crew_version` is a release that includes #210). A set
   held in step 6 keeps its hold until the owner answers.
8. **Continue.** The [§6](protocol.md#6-duties-on-wake-all-roles) step 3
   sweep picks up every set at its stage. Owner-ask deadlines carry over
   unchanged; rounds keep counting.

| Live state vs manifest | Meaning | Action |
|---|---|---|
| Same | Nothing moved | Adopt |
| Ahead by crew passes posted before `offered` | The drain finished work | Adopt at live state |
| A pass marker posted after `offered` or `takeover` and before `acked` | A stale run of the outgoing runtime | Do not let it satisfy anything; re-run that pass at head |
| Head moved by a non-crew actor, or state tags contradict the record | Diverged | Plan a hold; after the ack and before dispatch, hold the set (`crew:hold` with a coordinator note) and ask the owner; adopt the other sets |
| Item closed or merged | Gone | Close-out duties ([§2](protocol.md#2-stages) step 10) |
| Open crew item missing from the manifest | Missed | Adopt it through the sweep; name it in the ack |
| A run with `end` `stopped` or `kept` | Unfinished work | Re-run the pass at head; list a kept worktree for the owner, since it stays on the outgoing host |

**On tmux** (#212), `crew handoff reconcile` prints the plan, one line per
row above: per set `adopt`, `hold` (a head or stage tag moved since the
manifest) or `skip`, then `gone`, `rerun` (a kept or stopped run, or a
`stale` pass marker posted in transit), `missed` and `rule` differences.
`crew handoff ack` re-reads, refuses while a `rule` line has no owner
answer (`--rules-confirmed` once it has), and posts `acked` with the plan
once per id; after a takeover the post also carries the manifest generated
from live state. `crew handoff lift` removes `crew:hold` from the
`holds_added` items only once step 7 allows it; `--keep <n>` leaves a set
held in step 6.

**Idempotent.** Reconcile reads live state and writes nothing before the
ack, so a rerun after a crash gives the same result. After the ack, an item
this runtime already acted on (its own marker or claim) is skipped. Claims
are runtime-local: the incoming runtime never trusts a foreign claim file
and takes its own.

## Prompt stop

After `acked` (in a takeover: read-only at `takeover`, stop after `acked`),
every wake source of the outgoing runtime stops or no-ops within one wake
or poll interval, including one in the middle of a wait:

| Runtime | Wake sources | Stop |
|---|---|---|
| tmux | Watcher, `crew poll`, the Stop hook, role windows | `crew poll` reads the record each tick. When this runtime is no longer the owner (mode `lost`) it queues one `ownership:` wake; the watcher exits and `crew watch` refuses to re-arm; the coordinator runs `crew handoff stopped`, which re-runs itself detached from the session, disarms any watcher, runs [crew down](runtimes/tmux.md#crew-down) keeping every worktree, and posts `stopped` with the kept worktree names only once no watcher and no session remain |
| Grok Bot | Standing routines, per-PR watches B2 and V2, the dispatcher, the sweeper | Every routine's guard no-ops from its next wake. The parent turns then remove the per-PR watches and standing routines, as in [offboarding](runbook-new-repo.md#rollback-and-offboarding) step 2, and mark them removed in the wiring doc, because each no-op wake still costs a bot turn ([wiring checklist](../templates/runtimes/grok-bot/wiring.md#handoff-stop-and-return)) |
| Session (no binding yet) | The coordinator session and its subagents | The coordinator dispatches nothing more and ends its subagents; the session ends |

Then the outgoing coordinator posts `stopped`. A Grok Bot crew that keeps
its routines as no-op guards for a short switch says so in that post.

## Return path

The same flow with the roles swapped: the steps depend on which runtime
is incoming, not on the direction. A Grok Bot incoming runtime also does,
before its ack:

- **Drift check.** Rules may have changed while it was away. Deploy the
  render for the live profile and run `check-skill-drift.py --project`
  until it exits 0, as the [mirror hold gate](runtimes/grok-bot.md#mirror-hold-gate)
  requires (#128; box skills: #140).
- **Routines.** The parent turns re-create the standing routines from the
  wiring doc, then backfill B2 and V2 for every open crew PR outside the
  lighter lane, with the builder's `pass=watch` marker, as in the
  [cutover plan](../templates/runtimes/grok-bot/wiring.md#5-cutover-plan-for-open-prs)
  but with no `cutover` marker. Without the watch marker, the
  [builder watch gate](runtimes/grok-bot.md#builder-watch-gate) holds a PR
  another runtime opened.

Both checklists, stop and return, are in the Grok Bot
[wiring template](../templates/runtimes/grok-bot/wiring.md#handoff-stop-and-return).

A tmux incoming runtime starts with `crew up`. Its `crew poll` first run
records a baseline and emits nothing, so the reconcile is its sweep; the
coordinator re-creates `asks/<n>.json` for each owner ask in the manifest
so the deadline wakes fire.

## Session rules as config

Rules that lived in comment threads during the #110 run, and where each
lives instead (#157 Q3, decided by
[#160 row 15](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6532247500)):

| Rule | Source | Config | Status |
|---|---|---|---|
| Single-identity verdicts | #111 | One login for every role in `[identities]`; the [single-identity profile](interfaces.md#single-identity-profile) | In config |
| Standing merge grant | #111 | tmux `runtime.options.merge_grant`; the flavor knob `merge` ([flavors](flavors.md#knobs), #195) | In config (tmux) |
| `crew:hold` as a lane label | #111 | tmux `runtime.options.hold_label_blocks = false` | In config (tmux) |
| Inline-only evidence | #143 | The flavor knob `evidence = "inline"` (#195), or the protocol once #143 lands | Proposed |
| Engine order and quota steers | [Quota routing](roles.md#quota-routing) | `[engines]` | In config |
| Mirror deferral | #112, #140 | None: a temporary decision that ends with #140 | Link only |

The manifest's `rules` carries the resolved value and source of each key
above; `links` carries the rest. Each row still marked "Link only" is a gap
to close in config, not a pattern to grow.

## Runtime guards

Where each runtime runs the [guard](#ownership-record) (#157 Q4, Q5):

| Runtime | Guard placement | Read-only behaviour |
|---|---|---|
| Core | [§6](protocol.md#6-duties-on-wake-all-roles) step 1, and before each push, post and land | As defined in [Ownership record](#ownership-record) |
| Grok Bot | The "Guard first" line of every routine template (B1, B2, V1, V2, S1, the after-merge routine, the dispatcher, the sweeper) and the coordinator's parent turn; one read of the control item's comments | Ends the wake in a few tool calls. The sweeper reports a lost ownership to the coordinator once per handoff id. The dispatcher no-ops every `/crew` command |
| tmux | `crew poll` each tick; `crew spawn` and `crew restart` refuse; the synthesizer brief before it takes the land lock; `crew guard` allows the stop | `crew poll` emits nothing but the one `ownership:` record; no window starts |
| Session | The [coordinator-session brief](../templates/runtimes/session/coordinator.md): `crew ownership --runtime session` at each turn and before each dispatch, push, post and land | Dispatches nothing |

The control item read needs item-level marker write and read in the
[markers interface](interfaces.md#markers), which today puts markers on
changes only; on GitHub it is an issue comment. #210 adds both operations
and the GitHub mapping.

## Quota suggestion

When [quota routing](roles.md#quota-routing) shows the owning runtime's
orchestration meter under its skip threshold (15% of the short window, 10%
of the weekly or monthly limit), the coordinator suggests a handoff to the
owner once per window: the target runtime and why. Nothing auto-applies: a
handoff is never an allowed [§6](protocol.md#6-duties-on-wake-all-roles)
default. The duty and what the suggestion carries are in
[roles](roles.md) (Quota handoff suggestion). In tmux and the session runtime
the meter is the coordinator engine's own subscription. Grok Bot gives the
crew no orchestration meter today (#109,
[Orchestration cost](roles.md#orchestration-cost)), so there the coordinator
acts only on a reading the owner gives.

## Failure cases

| Case | Handling |
|---|---|
| Outgoing runtime dies mid-drain | The owner commands a takeover; it reuses the open id |
| Incoming runtime dies before its ack | Ownership stays in transit and nobody acts. The outgoing coordinator reminds the owner; the owner restarts the incoming runtime (its reconcile is idempotent) or aborts (the outgoing runtime owns again) |
| Incoming runtime dies after its ack | It owns the repo; its normal restart reconciles from live state |
| Two runtimes claim, or two take over | The earliest marker wins; the other goes read-only |
| An offer or ack post fails | Re-read, then retry with the same id |
| The owner changes their mind | `aborted` before the ack; after it, a new handoff back |
| A stale outgoing run posts after ownership moved | The guard before each post narrows the window to seconds; reconcile re-runs any pass marker posted in transit |
| Control item unreadable | Read-only for that wake |
| The other runtime's login is not in this profile | Its markers are ignored, so the handoff fails closed; `crew doctor` names the login |
| Unknown manifest schema major | The incoming runtime refuses and asks the owner |

## Runtime contract

The rule is core: one owning runtime per repo, recorded on the tool of
record, read-only for every other runtime, and the land gate above. How a
runtime meets it is not: reading the record on every wake, draining its own
runs, stopping its own wake sources (a Grok Bot routine run cannot delete a
routine; a tmux watcher waits in a background command) and starting from a
manifest. C1–C8 do not cover that, so the runtime contract gains
[C9 Ownership handoff](runtimes/README.md#c9-ownership-handoff). The Grok
Bot and tmux bindings declare it unsupported today, compensated by the
manual pause, until #210–#212 close the gap.

## Build issues

The M21 issues, mapped onto this design. Rows A–E are proposed follow-ups
for the coordinator to file.

| ID | Issue | Scope from this design | Depends on |
|---|---|---|---|
| 21.2 | [#210](https://github.com/mw-ding/eng-crew/issues/210) | [Ownership record](#ownership-record): `pass=handoff` and its states in §4; the owner function; the guard at §6 step 1 and before each push, post and land; the owning-runtime gate under the gate contract (owner merge-ok); profile keys `repo.control_item` and `runtime.instance`; item-level marker operations; guard lines in the Grok Bot templates and in tmux `crew poll`, `spawn`, `restart`, `guard` and the synthesizer brief; tests for the owner function (claim race, one open handoff, ignored markers, unreadable record). Likely two PRs: protocol and templates (mirror), then tmux code | #157 |
| 21.3 | [#211](https://github.com/mw-ding/eng-crew/issues/211) | [Manifest](#manifest): the template from [Manifest template](#manifest-template) and a generator `crew handoff manifest` (`scripts/crew.d/handoff.py`; its tests in `scripts/test-crew-handoff.py` run under CI's `test-crew-*` glob, with no workflow edit); sets; secret scan; size rule; tests for retry (same id, same post), partial (one set held, the rest adopted) and duplicate (a second ack ignored) | #210 |
| 21.4 | [#212](https://github.com/mw-ding/eng-crew/issues/212) | [Prompt stop](#prompt-stop) per runtime; [resume](#resume-and-reconcile) steps 1–8 and the reconcile table; lifting `holds_added`; the Grok Bot [return](#return-path) checklist; tests | #211, A |
| 21.5 | [#213](https://github.com/mw-ding/eng-crew/issues/213) | Dry run: Grok Bot → session runtime → Grok Bot on a sandbox repo, recorded and linked from #157 (#157 AC3). Needs a live Grok Bot crew: blocked on Grok Bot quota and #140 | #212 |
| A | [#637](https://github.com/mw-ding/eng-crew/issues/637) | Owner commands and drain: `/crew handoff to`, `drain`, `stop`, `deadline`, `abort` and `/crew takeover from` in §9 as chat commands; the `draining` state per runtime | #210 |
| B | [#638](https://github.com/mw-ding/eng-crew/issues/638) | Session runtime guard: the coordinator-session brief carries the guard and the outgoing and incoming steps until the session binding that [bootstrap](bootstrap.md#build-issues) proposes exists | #210 |
| C | [#639](https://github.com/mw-ding/eng-crew/issues/639) | `crew doctor` rows: control item set and readable, `runtime.instance` set, current owning runtime (a scope note for #190) | #210, #190 |
| D | [#640](https://github.com/mw-ding/eng-crew/issues/640) | Quota suggestion in the coordinator's duties | #212, #109 |
| E | proposed | Contract tables: C9 rows in the [multi-device](runtimes/multi-device.md#runtime-contract-across-hosts) design, and the session binding's table | #212 |

## Out of scope

- The dry run (#157 AC3) is #213: it needs a live Grok Bot crew, which is
  blocked on quota and on the box-skill sync (#140).
- Switching without the owner; the quota trigger only suggests.
- Building any of this before the build issues land.
- Two runtimes acting on one repo, even on separate items.
- Moving unlanded worktrees between hosts: they stay where they are, and
  the manifest names them for the owner.

## Design credit

Read-only fallback for a second session, dependency-closed idempotent
transfer, retry until receipt with a stable id and a take-over that stops
the old watcher at once are adapted from
[firstmate](https://github.com/kunchenguid/firstmate) (MIT license), as
decided in #160 row 16. eng-crew takes the contracts only: no code or text
is copied. Not adopted: a local outbox file as the record (row 16 #7) and
a session lock per home.
