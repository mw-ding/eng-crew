# Grok Bot runtime binding

Routine-only mechanics of the Grok Bot runtime, moved verbatim from
[protocol §6](../protocol.md#6-duties-on-wake-all-roles), the protocol's
pilot notes and [templates/README.md](../../templates/README.md) (#114,
roadmap 13.2). Every rule, gate, cap, marker field and label keeps its
meaning; the [§7 merge gate](../protocol.md#7-merge-gate-synthesizer) and the
gate registry still hold the builder-watch and mirror-hold gates as runtime
gates, whose Grok Bot satisfaction rules are in [Runtime gates](#runtime-gates)
(#119). Abstract terms are in
[concepts.md](../concepts.md).

## Runtime contract

How Grok Bot meets each capability of the
[runtime contract](README.md#contract) (#120), with gaps declared in the
[gap format](README.md#gap-declaration). Mechanisms only; no rule changes.

| Capability | How Grok Bot meets it | Gap |
|---|---|---|
| C1 Wake on event | Event routines per role ([wake wiring](#wake-wiring-event-to-consuming-role)), per-PR watches B2/V2, parent-turn hand-offs; each wake sweeps missed PRs ([protocol §6](../protocol.md#6-duties-on-wake-all-roles) step 3); the scheduled stuck-PR sweeper is the backstop; waiting is token-free: the platform pushes each subscribed event, so no turn runs between wakes | C1 wake on event: partial, compensated by messages from the reviewer, coordinator and sweeper ([lighter-lane routing](#lighter-lane-routing)); residual risk: a lighter-lane fix waits up to the sweeper threshold<br>C1 wake on event (waiting cost): partial, compensated by the hourly sweeper cadence and by ending no-op wakes in a few tool calls ([routine limits](#routine-limits)), such as the dispatcher's cheap check on each bot post ([pilot notes](#pilot-notes)); residual risk: the sweeper's fixed cron never backs off, so it spends one bot turn an hour while nothing is in flight, and each bot post costs the dispatcher a no-op turn |
| C2 One consumer per event | One routine per event (wake wiring table); claim file per pass per head and marker check make re-wakes no-ops | C2 one consumer per event: partial, compensated by cleanup-only handling: PR-scoped `pr-merged` / `pr-closed` reach both B2 and V2, because a routine run cannot delete another routine ([protocol §8](../protocol.md#8-safety)); residual risk: none for passes |
| C3 Messages by reference, proof of delivery | Wake payload is a trigger only; roles re-read live state ([protocol §6](../protocol.md#6-duties-on-wake-all-roles) step 1). Bot messages carry PR, head SHA and findings link. B2 creation is proven by the [verified hand-off](#verified-hand-off) and `pass=watch` | C3 messages by reference: partial, compensated by the stuck-PR sweeper rows (changes requested or CI failed with no builder action); residual risk: a lost bot message is noticed only after the row threshold |
| C4 Status protocol | `ack` → `pass=ack` marker; `done` → the pass marker (`verdict`, `fix`, `ci-fix`, `merge`, ...) plus claim deleted; `blocked` → `crew:needs-md` or message to the coordinator; `paused` → `crew:hold` or `pass=hold`; `failed` → `pass=escalation` and `crew:escalated` | None |
| C5 Liveness | Builder claim-file heartbeat; sweeper `builder-silent` (15 min) and "claimed or acked, no output" (3 h) rows; the role bot checks worker liveness and restarts only after that check | C5 liveness: partial, compensated by the role bot's liveness check before any restart; residual risk: silence stands in for `ambiguous` with no runtime probe, and reviewer workers have only the 3 h row |
| C6 Isolation | Unique worktree per run, never a shared or branch-named path, cleanup per run and on merge/close ([roles](../roles.md#worker-isolation-worktrees)) | C6 isolation: partial, compensated by cleanup timing: a worker deletes its worktree only when its pass finishes (a builder's pass ends after its push, and a reviewer's worktree holds no work to land), and the builder's merge/close cleanup ([B2](../../templates/runtimes/grok-bot/builder-b2.md), or the coordinator's message in the [lighter lane](#lighter-lane-routing)) runs only on `pr-merged` / `pr-closed`, when `refs/pull/<n>/head` on GitHub holds every pushed commit; residual risk: no landed check runs before the delete, so uncommitted or untracked paths, or commits a failed pass never pushed, are lost, and no discard reason is recorded |
| C7 Serial land | Synthesizer takes `<state-dir>/<owner>__<repo>/locks/merge.lock` (`flock`) around the head-bound squash ([protocol §7](../protocol.md#7-merge-gate-synthesizer)) | None |
| C8 Owner channel and SLA | Coordinator chat plus the matching GitHub post; 2h awake-hours SLA and sweeper `crew:needs-md` promotion ([protocol §6](../protocol.md#6-duties-on-wake-all-roles)) | None |
| C9 Ownership handoff | Ownership record and read-only guard implemented ([protocol](../protocol.md#ownership-record)); transfer remains pending ([handoff design](../handoff.md)); a switch is the [offboarding](../runbook-new-repo.md#rollback-and-offboarding) pause, then routine removal from each bot's parent turn | C9 ownership handoff: unsupported, compensated by the manual pause: `crew:hold` on every open crew PR and `crew:ready` issue, on which work roles no-op ([protocol §5](../protocol.md#5-rounds-and-escalation)), then routine removal; residual risk: holds are per item and manual, so a missed item can still wake a routine; each event on a held PR costs a no-op bot turn until its watches are removed; the incoming runtime rebuilds its context from GitHub ([#210](https://github.com/mw-ding/eng-crew/issues/210)–[#212](https://github.com/mw-ding/eng-crew/issues/212)) |

## Review start gap

C1 wake on event (`new-head` review start): partial. The reviewed protocol
starts review on an opened or pushed head alongside CI. Grok Bot's live V2
reviewer still wakes on `ci-passed` until a later PR mirrors the change to the
live box skill (deferred to #140). Compensation: existing V1 intake and V2
CI-green review wiring and the stuck-PR sweeper remain in place. Residual
risk: Grok Bot review waits for green CI, so CI and review run in series and
CI-red fixes may precede review findings. This PR changes no live Grok Bot
wiring or box skill; CI green at head remains the §7 merge gate in both
runtimes.

## Wake wiring: event to consuming role

Each event has exactly one consuming role, with one narrow exception (stated in
[the protocol, section 8](../protocol.md#8-safety)): PR-scoped `pr-merged`
and `pr-closed` are terminal events that go to both the builder's watch (B2) and
the reviewer's watch (V2). A routine run cannot delete another routine, so each
watch gets the terminal event itself, cleans up its own state and deletes
itself. Only the dispatcher subscribes to comment events. Nobody subscribes to
`review-commented`, where all bot narrative lands.

| Event | Consuming role | Routine |
|---|---|---|
| `issue-assigned` | Builder | B1 |
| `pr-opened` | Reviewer-validator | V1 |
| `ci-passed` | Reviewer-validator | V2 |
| `review-requested` | Reviewer-validator | V2 |
| `ci-failed` (PR watch) | Builder | B2 outside lighter lane; sweeper/coordinator message in lighter lane |
| `review-changes-requested` | Builder | B2 outside lighter lane; reviewer parent-turn message on lighter-lane REQUEST_CHANGES |
| `review-approved` | Synthesizer | S1 |
| `pr-merged` (repo-wide) | Coordinator | After merge |
| `ci-failed` on `<default-branch>` | Coordinator | After merge |
| `pr-comment` | Coordinator | Steering dispatcher |
| `inline-review-comment` | Coordinator | Steering dispatcher |
| `pr-merged`, `pr-closed` (PR-scoped) | Builder (B2 outside lighter lane) and reviewer (V2) | Each watch cleans up its own state and self-deletes; coordinator messages lighter-lane builder for cleanup |
| `review-commented` | Nobody | Not subscribed |
| `pr-pushed`, `review-thread-*` | Nobody | Not subscribed |

Note on the two kinds of `ci-failed` and `pr-merged`: the repo-wide listeners
(coordinator) and the PR-scoped watches (builder, reviewer) are different
routines with different scopes, and the PR-scoped ones are cleanup-only
terminal events. Keep the repo-wide `ci-failed` limited by `ciBranch`. A
PR-scoped `ci-failed` belongs to B2 alone where installed, and `ci-passed` to
V2 alone.

## Per-PR watches

**Per-PR watches (routine limits).** A routine run cannot create or delete
routines. A listener wake that needs a per-PR watch hands the request off to its
parent bot turn, which creates it. PR-scoped watches that include
`pr-merged` / `pr-closed` delete themselves after that terminal wake, so no
delete handoff is needed.

## Verified hand-off

**The hand-off is verified, not fire-and-forget.** Lighter-lane PRs skip this
B2 hand-off and its marker. For other PRs, after the builder's parent turn
creates B2 for PR `<n>`, it lists its routines and confirms a watch exists
for PR `<n>` with exactly `ci-failed`, `review-changes-requested`, `pr-merged`
and `pr-closed`. It records the **routine folder id** in the marker file
`<state-dir>/<owner>__<repo>/watches/pr-<n>.b2`, then posts the `pass=watch`
marker on the PR. The folder id is the one identifier both a routine run and
the parent turn can see; a platform watch UUID is not recorded, because the
parent turn's routine `get` returns only the folder id. The builder routine run
(B1) only requests the hand-off; verifying, writing the marker file and posting
the marker belong to the parent turn alone. If it cannot confirm the watch, it
messages `<CoordinatorBot>`. The stuck-PR sweeper also flags a crew PR with
no watch marker (`no-builder-watch`), except lighter-lane PRs. The
reviewer-validator never creates B2.

## Comment-listener wakes

**Comment reviews do wake comment listeners.** A COMMENT review with a body
fires `pr-comment` for the steering dispatcher (see the
[pilot notes](#pilot-notes)). The dispatcher must end such wakes
in one cheap check; keep bot posts few (one per pass).

## Lighter-lane routing

B1 listens only for `issue-assigned`; without B2, CI failures and
`REQUEST_CHANGES` do not wake the builder directly. On lighter-lane PRs, when
its verdict pass posts `REQUEST_CHANGES`, the reviewer-validator's parent turn
messages `<BuilderBot>` with the PR, head SHA and findings link; the builder
starts a fix round as if B2 had fired `review-changes-requested`. The stuck-PR
sweeper's "CI failed at head, no ci-fix" row routes red CI to the builder by
message (or the coordinator messages it directly); its changes-requested row
backs up the reviewer hand-off. The coordinator routes close-out cleanup to
the builder when the PR merges or closes. Lane membership is judged from the
full diff at head: a fix round touching code, `.github/`, `templates/` or
`docs/protocol.md` takes the PR out of the lane, and the builder then attaches
B2.

Lighter-lane PRs touch only docs, with no code, no `.github/`, no `templates/`
and no `docs/protocol.md`, judged from the full diff at head. They install no
B2, post no `pass=watch` and never get `crew:needs-mirror`. The reviewer's
verdict-pass parent turn messages `<BuilderBot>` on `REQUEST_CHANGES` with PR,
head SHA and findings link; the sweeper's changes-requested row is a backstop.
The sweeper's CI-failed row or a direct coordinator message routes red CI
(no lighter-lane `ci-failed` listener fires). The coordinator messages the
builder for merge/close cleanup. If a fix leaves the lane, the builder attaches
B2 using the verified hand-off.

## Runtime gates

The two runtime gates of the
[§7 merge gate](../protocol.md#7-merge-gate-synthesizer) on Grok Bot, moved
verbatim from §7 (#119). The synthesizer checks them with every other §7 gate
at the current head SHA, right before merging. Who satisfies each, how fast,
and its fail-open are in the
[gate registry](../protocol.md#gate-registry).

### Builder watch gate

The builder's `pass=watch` marker (`role=builder pass=watch watch=b2
status=attached`) is on the PR, with `sha=` the full 40-char SHA of **any**
commit on the PR, not only the head (match on the full SHA, not a prefix; same
rule as the reviewer cross-check). Four exemptions: external PRs, which have
no crew builder and so no B2 watch to require; cutover PRs, which predate
the watch protocol; coordinator-opened `crew:spec` PRs, which have no crew
builder and no B2 watch and merge on the user's `/crew merge-ok`; and
lighter-lane PRs ([protocol §6](../protocol.md#6-duties-on-wake-all-roles)),
which install no B2 and post no watch marker. A cutover
PR is subject to the gate again as soon as its builder posts its
`[<Builder>/watch]` review or any builder `crew:v1` marker after the cutover
(by post time), whatever commit it sits on. This includes attaching B2 at the
unchanged cutover SHA, which needs no new commit. That trigger does not depend
on the `pass=watch` marker. From then on a valid full-SHA marker (any PR commit) is
required as usual. If it is missing or malformed, hold the PR: do not merge,
and ping the builder with priority to attach B2 and post the marker (the
synthesizer never creates the watch). The merge re-checks once the marker
appears. If attachment remains blocked, tell the coordinator and use the
[§6](../protocol.md#6-duties-on-wake-all-roles) owner-decision SLA
(`crew:needs-md`, user decision or allowed default); this does not waive the
watch gate.

### Mirror hold gate

No `crew:needs-mirror` hold. Lighter-lane PRs are exempt. A PR that changes
`docs/protocol.md` or `templates/` carries the label from the reviewer's
verdict pass (added before the formal review) until the coordinator posts
the box-skill mirror comment and removes it. The synthesizer derives the hold from the changed paths, not
only the label: if the PR's diff touches `docs/protocol.md` or `templates/`,
hold the PR unless the label is absent **and** the coordinator's box-skill
mirror comment exists on the PR and is newer than the last commit touching
`docs/protocol.md` or `templates/`. While held, do not merge; wait for the
coordinator's ping (label changes don't wake listeners), then re-check the
gate.

The mirror comment counts only if it records, at a commit no older than the
last one touching those paths (#128):

1. the rendered output for the live profile deployed to the live dir
   (`crew-render.py --out <live-dir>`; the coordinator deploys, never CI);
2. `python3 scripts/check-skill-drift.py --project <crew.toml>` (render vs
   live) and, if `docs/protocol.md` changed, `--only pipeline
   --pipeline-skill <path>`, each exiting 0: no `DRIFT`, `MISSING` or `EXTRA`
   (`WORDING` allowed), with each command and its output inline.

A comment without both, or with a non-zero exit, is not a mirror comment; the
label stays.

## Routine limits

- **A routine run cannot create or delete routines.** A listener wake that needs
  a per-PR watch (B2 after a build outside the lighter lane, V2 after V1) hands
  the request off to its parent bot turn, which creates it. The builder's parent turn verifies B2 after
  creating it: it lists its routines, confirms the four events, records the
  routine folder id in `<state-dir>/<owner>__<repo>/watches/pr-<n>.b2` and posts
  the full-SHA `pass=watch` marker. B1 only requests the hand-off. If it cannot confirm, it messages the coordinator.
- **PR-scoped watches self-delete on terminal events.** Every per-PR watch
  includes `pr-merged` and `pr-closed`; the wake on either one does cleanup and
  the watch then deletes itself, so no delete handoff is needed.
- **Per-watch repo caps.** A single watch can cover only a small number of
  repos (4 on the pilot platform). Repo-wide forwarding for many repos needs
  several routines of the same shape.
- **Every wake costs a full bot turn.** Keep triggers tight and end no-op wakes
  in a few tool calls.
- **Bots never post plain PR comments or inline comments.** Narrative goes in
  COMMENT reviews. A COMMENT review still fires `pr-comment`, so the dispatcher
  wakes once per bot post and no-ops.
- **Schedule trigger shape.** The sweeper's `schedule` block shows the intent
  (cron and timezone). Use the platform's own schedule syntax when creating it.

## Pilot notes

Facts from the agentconnect pilot (`mw-ding/agentconnect`), kept out of the
generic rules in the protocol. They illustrate the protocol and do not change it.

- **Comment reviews wake comment listeners (pilot finding, Oct 18, 2026).** A
  COMMENT review with a body fires `pr-comment` for the steering dispatcher.
  This is why the dispatcher ends such wakes in one cheap check and why bots keep
  their posts to one per pass.
- In the pilot, the per-repo wiring doc lived under the shared state dir as
  `mw-ding__agentconnect/wiring.md`, following the
  `<state-dir>/<owner>__<repo>/wiring.md` convention.
