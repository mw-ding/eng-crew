# Stage protocol

> **Two copies, kept in sync (spec R4).** The box skill `eng-pr-pipeline` is the
> **live** copy the bots load. This document is the **reviewed** copy. Any
> change to one must be mirrored to the other in the same change, through a PR
> in this repo plus a matching edit to the box copy. See
> [the spec](specs/framework.md).

One [tracker item](concepts.md#tracker-item--milestone--board) → one branch →
one [change](concepts.md#change) → one squash merge. Each stage is woken by a
[wake event](concepts.md#wake-event) (on Grok Bot, a GitHub-triggered routine
on that bot; see the
[runtime binding](runtimes/grok-bot.md#wake-wiring-event-to-consuming-role)),
does its job through fresh workers, and leaves its result **on the
[backend](concepts.md#backend)** (GitHub today: state tags, markers, a verdict)
so the next stage can read it. Nothing important lives only in a bot's chat.
On Grok Bot, a per-repo wiring doc (trigger JSON per bot) lives in the shared
state dir at `<state-dir>/<owner>__<repo>/wiring.md`.

Engines, tiers, worker briefs, branch naming, PR body sections, worktree
isolation and cleanup are covered by the roles doc
([roles.md](roles.md), worktree isolation in
[Worker isolation](roles.md#worker-isolation-worktrees); the box skill is
`eng-crew-roles`). This document adds the stage
protocol on top of it. For a shorter overview with a diagram, see
[architecture.md](architecture.md).

**Hard rules, everywhere:**

- Reviewer engine ≠ builder engine (the engine that actually wrote the round),
  except under the [quota diversity waive](roles.md#quota-diversity-waive);
  reviewer identity must still differ from the builder / author of the
  [change](concepts.md#change).
- Never `--no-verify`.
- Never force-push a shared branch.
- Merge-up uses a merge commit or the backend's update-branch
  ([GitHub update-branch](backends/github.md#land-and-merge-up)), never a
  rebase.
- Squash-merge only.
- Only the synthesizer merges.
- `crew:sensitive` requires the owner's per-change merge-ok; no standing grant covers it.
- Eng workers never use Cursor CLI.
- One [verdict](concepts.md#verdict) per [change head](concepts.md#change-head) (a clean merge-up after changes gets a merge-up ack instead; see [Duties on wake](#6-duties-on-wake-all-roles)).
- Max 3 verdict rounds and ≤3 CI-fix attempts per change.
- Workers never post to a [backend](concepts.md#backend) (GitHub today); only
  role bots post.

Placeholders: `<owner>/<repo>`, `<state-dir>`, `<default-branch>`,
`<author-login>`, `<reviewer-login>`, `<user-logins>`, `<CoordinatorBot>`,
`<BuilderBot>`, `<ReviewerBot>`, `<SynthesizerBot>`.

<a id="1-roles-and-github-identities"></a>

## 1. Roles and identities

See [architecture.md](architecture.md) for the identity model. How each role
selects its identity on a backend is in the backend binding
([GitHub backend](backends/github.md#identities)).

"Woken by" names today's [wake events](concepts.md#wake-event); how the
runtime delivers each one is in the runtime binding
([Grok Bot wake wiring](runtimes/grok-bot.md#wake-wiring-event-to-consuming-role)).

| Role | Woken by | Owns | Identity |
|---|---|---|---|
| Coordinator (also **steering dispatcher**) | The user ([owner channel](concepts.md#owner-channel)), escalations, `pr-merged`, `pr-comment` / `inline-review-comment` | Spec, [tracker items and board](concepts.md#tracker-item--milestone--board), escalations, next assignment, `/crew` commands | Author identity (`<author-login>`); reviewer identity (`<reviewer-login>`) for steering signals |
| Researcher | The coordinator's message | Research notes for specs; no changes unless asked | Author identity |
| Builder | `issue-assigned`, `review-changes-requested`, `ci-failed` | Branches, commits, changes, fix rounds, conflict resolution | Author identity |
| Reviewer-validator | `pr-opened`, `new-head`, `review-requested` | Review pass, validation pass, the one verdict | **Reviewer identity** (`<reviewer-login>`), which must differ from the change author ([why, on GitHub](backends/github.md#identities)) |
| Synthesizer | `review-approved`, `ci-passed` (with approval at head) | Merge gate check, land rules and merge trains, serial squash [land](concepts.md#land), update-branch of changes that are behind ([land and merge-up on GitHub](backends/github.md#land-and-merge-up)) | Author identity (later: its own identity, such as a GitHub App) |

The bots share accounts, so **the account cannot tell bots apart**. A bot
action's identity comes from its **signed [marker](concepts.md#marker)**, not
the account (see [Marker conventions](#4-marker-conventions)).

## 2. Stages

1. **Spec (coordinator + user, researcher on demand).** The coordinator writes
   `docs/specs/<topic>.md` plus incremental sub-specs (one per buildable
   slice), lands them through a `crew:spec` change (review pass only, merges
   on `/crew merge-ok`), then opens one
   [tracker item](concepts.md#tracker-item--milestone--board) per slice. Each
   item body: goal, numbered testable acceptance criteria, out-of-scope, spec
   link, role + tier hint, dependencies (`Depends on #n`;
   [linkage on GitHub](backends/github.md#linkage)). Add each item to the
   board. Heavy research goes to the researcher in the background so the
   coordinator keeps talking with the user.
2. **Handoff.** The coordinator adds the `crew:ready`
   [state tag](concepts.md#state-tag) and assigns the tracker item to the
   author identity. The assignment (`issue-assigned`) wakes the builder.
3. **Build.** The builder fans out one worker per tracker item (see
   [Duties on wake](#6-duties-on-wake-all-roles)). The worker builds, runs
   tests and build, and opens a **non-draft** change that links the item
   (`Closes #n`; [linkage on GitHub](backends/github.md#linkage)) with the
   evidence body ([Evidence requirements](#3-evidence-requirements)). The builder tags it
   `crew:in-review`, then attaches and verifies the per-change watch its
   runtime requires (except lighter-lane changes), as the runtime binding
   states ([Grok Bot verified hand-off](runtimes/grok-bot.md#verified-hand-off);
   [§6](#6-duties-on-wake-all-roles)).
4. **CI (parallel with review).** The [CI signal](concepts.md#ci-signal)
   must settle green before merge. A red signal (`ci-failed`) wakes the
   builder (fix on the same branch, ≤3 CI-fix attempts, then escalate). On
   tmux, the coordinator holds it while a pass runs and hands the builder
   both CI failures and review findings together. A green signal (`ci-passed`)
   lets the synthesizer retry a pending merge; it never starts review.
5. **Review pass.** Each new change head (`new-head`, opened or pushed)
   starts review immediately, alongside CI. A fresh worker reviews code,
   design and implementation
   against the change body **and** the tracker item/spec.
6. **Validation pass.** Only if review passed. A *separate* fresh worker that
   has **not** seen the review gathers its own evidence (checks out head,
   reruns acceptance tests, exercises each criterion, re-derives numbers) and
   judges whether the builder's evidence matches the spec.
7. **Verdict.** The reviewer-validator submits **one verdict per change
   head**: pass (`APPROVE`) iff review = pass and validate = pass, else
   changes requested (`REQUEST_CHANGES`) (a clean merge-up after changes gets
   a merge-up ack instead; see [§6](#6-duties-on-wake-all-roles)). **A failed
   validation pass can never become a pass verdict (`APPROVE`)**: the reviewer
   may not override it, and if the fail looks wrong, it posts
   `REQUEST_CHANGES`, followed by the escalation on round 3, and flags it to the
   coordinator. The body carries the review section, the validation section (or
   "skipped: review failed") and the verdict marker with the round number.
   State tag → `crew:approved` or `crew:changes`. How a verdict is posted on
   GitHub: [GitHub backend](backends/github.md#review-types-and-the-events-they-fire).
8. **Iterate.** A changes-requested verdict (`review-changes-requested`) wakes
   the builder, which relaunches a worker on the same branch with the findings.
   Push → CI and step 5 in parallel. Max **3 verdict rounds**; the 3rd
   `REQUEST_CHANGES` escalates
   ([Rounds and escalation](#5-rounds-and-escalation)).
9. **Merge.** A pass verdict (`review-approved`) wakes the synthesizer, which
   picks a [land rule](#land-rules-and-merge-trains), checks the gate
   ([Merge gate](#7-merge-gate-synthesizer)) and lands the change by
   squash-merge, serially, alone or in a merge train. After a lone land, or
   once a train ends, it update-branches any other crew change that is
   behind but mergeable
   ([GitHub](backends/github.md#land-and-merge-up)); changes with real
   conflicts go to the builder.
10. **Close-out.** The land (`pr-merged`) wakes the builder (clean worktree)
    and the coordinator (tick the board item, unblock dependents, assign the
    next `crew:ready` tracker item, file the soft-finding follow-up (§6)).

## 3. Evidence requirements

**Change body (builder).** The description the builder writes when it opens
the change (the PR body on [GitHub](backends/github.md#linkage)). Sections
from the roles doc: `## Context` with
`Closes #n`, `## Changes Made`, `## Testing Done`, `## Test Output`, signature
last. Plus:

- `## Acceptance Evidence`: one row per acceptance criterion: criterion → how it
  is met → proof (test name + result, command + output excerpt, or screenshot,
  plus the artifact path or link). "N/A" needs a reason. For a
  behaviour-changing criterion, name the shape (web, CLI, service, API,
  mobile) and the artifact path on the change head, as set out in the
  [verification protocol](verification.md).
- **Inline evidence.** `## Test Output` and every `## Acceptance Evidence`
  proof cell show the evidence **inline** in the change body: the pasted
  command →
  key output snippet (text) and/or an embedded screenshot. A path-only pointer
  to `evidence/` (or a bare link) is not sufficient alone; the reviewer must
  not have to dig to see the proof. Committed `evidence/<issue-or-pr>/`
  artifacts on the change head stay required as the durable audit trail whenever
  runtime proof exists (see [verification.md](verification.md)); the inline
  snippet is an excerpt of them, not a replacement. Example `## Test Output`:

  ```text
  $ curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/healthz
  200
  $ curl -s http://localhost:8080/healthz
  ok
  ```

  Example `## Acceptance Evidence` row:

  | Criterion | How met | Proof |
  |---|---|---|
  | Health endpoint answers | `/healthz` handler | shape: service, `evidence/<pr>/healthz.txt`; `curl …/healthz` → `200`, `ok` |

- **Mutation evidence.** A behaviour-changing change that adds or changes a
  user-visible create, update or complete (or equivalent) mutation must
  show, in both `## Test Output` and `## Acceptance Evidence`, an inline
  happy-path snippet that creates at least one entity, progresses or
  completes (or updates) it, then deletes it (item DELETE and/or a list or
  parent DELETE with cascade) and shows it is gone (404 or absent from the
  list). An update-only change still shows the full create → update → delete
  sequence. Unit-pass lines or path pointers alone do not meet this. Example
  (generic):

  ```text
  $ curl -s -X POST localhost:8080/todos \
      -H 'Content-Type: application/json' -d '{"title":"buy milk"}'
  {"id":1,"title":"buy milk","completed":false}
  $ curl -s -X POST localhost:8080/todos/1/complete
  {"id":1,"title":"buy milk","completed":true}
  $ curl -s localhost:8080/todos
  [{"id":1,"title":"buy milk","completed":true}]
  $ curl -s -o /dev/null -w '%{http_code}\n' -X DELETE localhost:8080/todos/1
  204
  $ curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/todos/1
  404
  ```

  With lists, a list DELETE with cascade also counts. Record the child item
  IDs before the delete (`GET /lists/1/todos` → ids `2`, `3`), run
  `DELETE /lists/1` → `204`, then show the children are gone too:
  `GET /todos/2` → `404` and `GET /todos/3` → `404` (or `GET /todos` no
  longer lists them). A `404` on the list alone does not prove the cascade.

  An app with no delete endpoint shows create → progress/update and states
  in the snippet or `## Risks / Not Done` that it has no delete; the
  validator checks that claim.

  Docs-only and no-behaviour changes stay N/A with a reason. Non-CRUD behaviour
  shapes keep their existing shape-specific rules; this rule only adds
  create+progress+delete where such mutations are in scope.

- **Deploy secret sync.** New deploy milestones must include an AC in the
  milestone/tracker-item ACs: before the first gated production deploy,
  assert each shared secret is equal across GitHub Actions secrets, Fly secrets, Vercel
  env and every other named host that consumes it. Verify this before
  declaring the milestone done. Name the GitHub store the workflow actually
  reads: repo-level or Environment secrets. GitHub Free-plan Path A uses
  repo-level Actions secrets when Environment protection rules (such as
  required reviewers) are unavailable on the plan/private repo. A mismatch
  between repo and Environment stores is itself drift.

  Show redactable command/output comparing SHA-256 fingerprints (or short
  prefixes), or a dashboard screenshot showing the hosts match. Never put
  plaintext secrets in the change, tracker item or `evidence/`. GitHub
  Actions secrets are write-only via API: get that fingerprint from a workflow step that
  prints only the hash, or re-set all hosts from one source in one step and
  show set timestamps/digests. Example output (fake SHA-256 prefixes):

  ```text
  NAME gh repo <app>       sha256: 012345abcdef
  NAME fly <app>           sha256: 012345abcdef
  NAME vercel <app> prod   sha256: 012345abcdef
  NAME comparison: MATCH
  ```

  Existing repos may file a soft follow-up tracker item; this is not a
  blocker for them. New deploy milestones must carry the AC. Docs-only and
  non-deploy changes stay N/A with a reason.

- `## Risks / Not Done`: known gaps, follow-ups, deliberate scope cuts.
- A hidden line right before the signature:
  `<!-- crew:v1 role=builder issue=<n> tier=<tier> engine=<engine> model=<model> -->`.
- Write the body once when the change opens. **Never edit it afterwards**:
  body edits
  rerun some CI workflows and re-wake the reviewer. Later evidence goes in a
  fix-round note.

**Evidence on the change head.** Any evidence a reviewer's verdict relies on
(screenshots, crops, logs, other artifacts) is committed **on the change's
branch**, so it is in the head commit.

- Never put it on a side branch. Side branches are deleted after merge, which
  broke images in a merged PR body (PR #12 in this repo).
- An evidence-only commit on the change's branch is a new commit: the change
  head moves and `new-head` re-wakes review immediately, alongside CI. Only
  evidence outside the branch (an image in the change body, an external link) leaves the head
  unchanged and wakes nobody. In that case the coordinator posts a rereview
  steer (the `steer cmd=rereview` marker); the ack and re-request mechanics are in
  [Steering](#9-steering-crew-commands).
- Lesson record:
  [2026-10-20-evidence-on-pr-head.md](lessons/2026-10-20-evidence-on-pr-head.md).

**Typed runtime evidence.** A change that alters behaviour attaches evidence
matched to the software shape. [verification.md](verification.md) states, per
shape, when evidence is required or N/A, what the builder attaches, what the
validation pass checks and when the synthesizer may merge. Docs-only changes are
N/A with a stated reason.

**Fix-round note (builder, after each push).** A
[narrative post](concepts.md#narrative-post) headed
`[<BuilderBot>/fix] round <k> @ <sha7>`: each finding → what changed (commit) → proof.
The note names the engine, model and effort that actually wrote the round, and
every commit of the round carries an `Engine: <engine> <model> <effort>` trailer.
The note's hidden line carries the engine too (same for `pass=ci-fix`):

```text
<!-- crew:v1 role=builder pass=fix pr=<n> sha=<head-sha> round=<k> verdict=n/a engine=<engine> model=<model> effort=<effort> -->
```

`<k>` is the verdict round the fix answers
([Rounds and escalation](#5-rounds-and-escalation)); a ci-fix before any verdict
uses `round=0`. See [Actual builder engine](roles.md#actual-builder-engine).

**Run summary (builder).** A multi-step run (build, tests, fix attempts)
writes short step lines with `scripts/step-summary.py` and promotes the
summary in its signed narrative post (the fix, ci-fix or first builder note),
never the raw logs. Raw logs stay local under the worktree. Protocol, paths,
what the reviewer skims and the risks are in [observe.md](observe.md). A pure
docs one-shot says `N/A: no multi-step run`.

**Review section.** Verdict (`pass` / `changes`), findings ranked 🔴 blocking /
🟡 should-fix / 🟢 nit, each with `file:line` and the spec clause or
change-body claim it contradicts. Check: does it do what the tracker item
asks, does the design fit the spec, correctness, do the tests actually cover
the criteria, security, scope creep.

**Validation section.** Per acceptance criterion: builder's claim → validator's
own evidence (command, output excerpt, artifact) → `agrees` / `disagrees` /
`unverified`. `pass` only if every criterion `agrees` (or has a justified N/A)
and no builder claim is contradicted. List what was **not** independently
checked.

## 4. Marker conventions

**Where bots write.** Bots never post plain conversation comments or inline
comments on a change
([on GitHub](backends/github.md#review-types-and-the-events-they-fire):
PR conversation comments and inline review comments); they would wake the
steering dispatcher for nothing. Bot output on changes goes in **post bodies** of two
kinds:

- A **[narrative post](concepts.md#narrative-post)**
  ([on GitHub](backends/github.md#review-types-and-the-events-they-fire),
  a COMMENT review) for ack, fix notes, merge-up, merge, cutover, escalation
  and steering acks. The author identity may post one on its own change.
- The **formal verdict post**
  ([on GitHub](backends/github.md#review-types-and-the-events-they-fire),
  a formal `APPROVE` / `REQUEST_CHANGES` review) for
  [verdicts](concepts.md#verdict) and steering signals. Cite `file:line` in
  the body instead of inline comments.
- **No bot text ever starts with `/crew`**, in any comment, post or commit
  message.

Which events each GitHub review type and comment fires, and so why bots
never post plain or inline comments: see the
[GitHub backend](backends/github.md#review-types-and-the-events-they-fire).

Every bot-authored post body starts with a visible signed header and has a
hidden machine line:

```text
[<BotName>/<pass>] <short status>
...
<!-- crew:v1 role=<role> pass=<pass> pr=<n> sha=<40-char head sha> round=<k> verdict=<pass|changes|n/a> -->
```

In **every** marker, `sha=` is the full 40-character change head SHA, never an
abbreviation. `<sha7>` is for human-readable names only (claim files, worktree
names, post headers such as `@ <sha7>`); markers always carry the full SHA.
Readers match markers on the full SHA, so a short SHA is treated as a missing
marker.

`pass` is one of:

- `ack`
- `review`
- `validate`
- `verdict` (the formal verdict post; its body holds the review and validation
  sections, each with its own marker line)
- `hold` (intentional reviewer wait for a user decision; `round=n/a verdict=n/a`)
- `watch` (adds `watch=b2 status=attached`; see below)
- `fix`
- `ci-fix`
- `merge-up`
- `merge`
- `escalation`
- `resume`
- `cutover`
- `steer` (adds `cmd=<command> cmd-id=<comment id>`)

A merge-up ack uses `round=n/a verdict=n/a`.

The builder's watch status marker (`pass=watch`) states that the builder's
per-change watch is attached (B2 on Grok Bot, see the
[runtime binding](runtimes/grok-bot.md#verified-hand-off)). It uses
`round=n/a verdict=n/a` and adds `watch=b2 status=attached`:

```text
<!-- crew:v1 role=builder pass=watch pr=<n> sha=<full-40-char-head-sha> round=n/a verdict=n/a watch=b2 status=attached -->
```

It is posted once per change by the builder, only after it has verified the
watch (see [builder duties](#6-duties-on-wake-all-roles)). On Grok Bot the
builder's parent turn alone posts it, after verifying B2, and the builder
routine run never posts it
([verified hand-off](runtimes/grok-bot.md#verified-hand-off)). It is not a
round and not a verdict. Because it is posted once, it is a per-change fact:
its `sha=` is the full SHA of the commit that was the head when it was posted,
and readers accept it for any commit on the change.

Parse **only** the hidden line (exception: to find a round's actual builder
engine, the fix note and commit trailers also count and win over the marker; see
[roles](roles.md#actual-builder-engine)). Markers are append-only; a newer SHA supersedes.
The per-pass meanings are tabulated in [architecture.md](architecture.md#pass-values).

**[State tags](concepts.md#state-tag)** (no wake event fires on a state tag,
so they are safe state; on GitHub each is a `crew:*` label): `crew:ready`,
`crew:in-review`, `crew:changes`, `crew:approved`, `crew:escalated`,
`crew:needs-md` (user decision needed; coordinator or its
[sweeper](runtimes/grok-bot.md#runtime-contract) adds it,
reviewer-validator adds it for an intentional verdict hold; coordinator clears
it under §6), `crew:hold` (work roles no-op), `crew:external`, `crew:spec`,
`crew:needs-mirror` (a change touching `docs/protocol.md` or `templates/`; blocks
the merge until the box skill is mirrored). See
[architecture.md](architecture.md#labels) for who sets and clears each, and the
[GitHub backend](backends/github.md#labels) for colours and label events. Never
touch state tags (labels) or comment commands that belong to the product under
development.

### Ownership record

The repo's `repo.control_item` holds append-only coordinator posts. On GitHub
this is a long-lived issue locked to collaborators: read all comments with
`gh api --paginate --slurp repos/<owner>/<repo>/issues/<n>/comments`; post with
`gh issue comment <n> --body-file <file>`. These are item-level marker reads
and writes; they never reset a PR's rounds. A post has this signed header
and marker (full default-branch SHA):

```text
[<CoordinatorBot>/handoff] <state> <from> → <to> (<handoff-id>)
<!-- crew:v1 role=coordinator pass=handoff handoff=<handoff-id> state=<state> from=<runtime-id> to=<runtime-id> cmd-id=chat sha=<default-branch-head-sha> round=n/a verdict=n/a -->
```

Handoff ids are `yyyymmdd-<6 hex>`. Runtime ids are
`runtime.name@runtime.instance`. Only well-formed markers
from a profile owner or role login count, in backend post order. The first
`claimed` (`from=none`) wins; later claims are ignored. On first configured
start the coordinator reads, posts `claimed` if no record exists, then
re-reads before dispatching. `cmd-id` is `chat` or `n/a`.
`draining` or `takeover` opens one handoff only if `from` is the current owner; a second
opener is ignored. A takeover may reuse the open id, from and to when its
outgoing runtime stopped answering. Subsequent states must match all three.

| State | Ownership / allowed action |
|---|---|
| `claimed` | `to` owns and may act |
| `draining` | `from` finishes in-flight writes; no new pass or land |
| `offered`, `takeover` | In transit: nobody acts; `to` reconciles by reading |
| `acked` | First matching ack closes the handoff; `to` owns |
| `aborted` | Matching abort closes the handoff; `from` owns |
| `stopped` | Ownership unchanged |

Every role reads at wake start and again before dispatch, push, post, tag
or land. A non-owner or unreadable record is read-only: reads and reports,
never starts work, pushes, posts pass markers, tags, creates watches or
lands. The coordinator may post only its handoff-side state. No control
item or no marker preserves legacy operation. Owner commands, manifests
and wake-source shutdown remain follow-ups ([handoff](handoff.md)).

## 5. Rounds and escalation

- **Round** = 1 + the number of reviewer-identity verdicts
  ([on GitHub](backends/github.md#review-types-and-the-events-they-fire),
  formal reviews) with marker `pass=verdict verdict=changes`, counted after
  the latest `cutover` or `resume` marker. Derived from the backend (GitHub today) each time, never
  from memory.
- Round 3 ends with a changes-requested verdict (`REQUEST_CHANGES`) (a failed
  validation pass counts as one, never as an `APPROVE`) → the
  reviewer-validator adds `crew:escalated`, posts a `[<ReviewerBot>/escalation]` narrative post (open
  blockers, what was tried, decision needed) and messages the coordinator, who
  brings it to the user over the [owner channel](concepts.md#owner-channel).
- A merge-up push uses no round. A merge-up re-approve keeps the round number
  of the approval it renews; a merge-up ack has `round=n/a`. See the
  merge-up rule in [Duties on wake](#6-duties-on-wake-all-roles).
- Builder: ≤3 CI-fix attempts per change, then the same escalation.
- Sweeper (the runtime's stuck-work check; on Grok Bot the stuck-PR sweeper,
  see the [runtime binding](runtimes/grok-bot.md#runtime-contract)): after the
  third nudge for the same key with no progress, report to the coordinator.
  The coordinator adds `crew:escalated` only for a crew change in a loop and
  escalates on the backend (GitHub today) and over the owner channel under §6.
- Work roles waking on a `crew:escalated` or `crew:hold` change do nothing. The
  coordinator and its sweeper still monitor and escalate waits under §6; they
  do not restart work. Restart via `/crew resume`
  ([Steering](#9-steering-crew-commands)), which resets the round count.

## 6. Duties on wake (all roles)

Every wake, in order:

1. **Ownership first:** check the [ownership record](#ownership-record).
   A non-owner reads/reports only; unreadable is read-only for this wake.
   Repeat before dispatch, push, post, tag and land. Then **re-read live state**: current [change head](concepts.md#change-head)
   SHA, [state tags](concepts.md#state-tag), posts (verdicts, steering
   signals, narrative posts), markers, not just the payload. If the event
   SHA ≠ head, or the change is
   closed, merged, `crew:hold` or `crew:escalated`, stop. The coordinator and
   its sweeper still perform the triage and owner-decision duties below on
   held/escalated items.
2. **Idempotency.** If a marker for *this pass at this head SHA* exists, stop.
   Otherwise take a claim file
   `<state-dir>/<owner>__<repo>/claims/<role>-pr<n>-<sha7>` atomically
   (`set -o noclobber` or `flock`). For the builder's tracker-item stage (from
   issue-assigned until the change opens) there is no change yet, so the claim
   is `builder-issue<n>`. If the claim exists and is under 2h old,
   stop. Delete the claim after posting.
3. **Sweep.** Also pick up other changes in the same state that missed a wake,
   up to the fan-out cap.
4. **Fan out.** One fresh worker per change or tracker item, max **5 in
   parallel per role**. Queue the rest. The role bot only briefs, collects
   results and posts markers; no coding in its own chat.
5. **Report.** Post the marker, set state tags, update the board item. Message
   the coordinator only on escalation or blockage.

**Worker heartbeat (builder).** While a builder worker is building, fixing or
fixing CI, it refreshes a `heartbeat: <UTC ISO-8601 timestamp>` line in the
claim file the role bot took in step 2 at least every **5 minutes**, and also
after each commit, push and post on the backend. The worker owns the write,
not the role bot; the worker brief must give it the absolute claim-file path
and write access to that file, since a sandboxed worker (e.g. Codex
`workspace-write`) cannot write outside its worktree by default. It is a file
write, not a backend post; its `[<BuilderBot>/<pass>]`
[narrative posts](concepts.md#narrative-post) and pushes already count as
visible activity, and no heartbeat marker is added to changes. **Silence** is
a heartbeat (or, if the line is missing, the claim file's mtime) older than
**15 minutes** while the claim still exists, for any builder claim on an open
crew change or tracker item that is not held, escalated, merged or closed
(including a ci-fix on a `crew:approved` change). The sweeper (on Grok Bot the
stuck-PR sweeper; [runtime binding](runtimes/grok-bot.md#runtime-contract))
flags it as `builder-silent` and messages `<BuilderBot>`, which checks worker
liveness, restarts the work in a fresh unique worktree and may take over a
silent claim despite the 2h rule in step 2. The sweeper's nudge cap and
escalation (§5) apply. Reviewer-validator workers are not covered here.

**Coordinator triage window.** The coordinator owns triage and runs a window
at least once per awake half-day (the user's awake hours in PT). Every open
tracker item leaves the window with exactly one disposition: `crew:ready`,
`crew:spec`, `crew:needs-md`, moved to the next milestone (deferred), or
closed with a reason. Resolve conflicting triage state tags. Include the
sweeper's report of open tracker items with no `crew:*` state tag older than
one awake day in the next window.

**Metrics gate.** When `scripts/metrics-decide.py` trips on the rollup, the
coordinator opens a `metrics-gate` tracker item in the control-plane repo and
holds new `M*` feature work (no `crew:ready`, `crew:hold` with
`hold-until-#<n>` on unstarted ready tracker items) until the harness fix
merges or the owner waives it. It is not a merge gate: open changes and the
fix merge as usual. Details, waiver and lift:
[metrics decisions](metrics/decisions.md).

**Soft-finding follow-up (after squash).** When the reviewer-validator's
pass [verdict](concepts.md#verdict) (`APPROVE`) carried soft 🟡 findings or
deferred non-blockers, the coordinator files a `crew:ready` follow-up in the
same awake window (the user's awake hours in PT), assigns it to the merged
change's author and kicks `<BuilderBot>` without waiting for a new user ask.
Respect the 5-builder ceiling and `crew:hold`. Skip if a follow-up tracker
item for that change already exists or the `APPROVE` had no 🟡/deferred
items. If the user said "defer softs" for a named
cut (for example, a milestone or release cut), park until that cut ends,
then file the follow-up and dispatch it. Soft findings never block §7 squash;
the merge gate is unchanged. Use this tracker item title and body (a GitHub
issue today):

```markdown
Title: Follow-up: soft findings from #<pr>

## Context
- Merged PR: <merged-pr-url>
- Verdict review: <verdict-review-url>
- Follow-up to #<pr> / Part of #<parent>

## Soft findings
- [ ] <file:line> — <finding>

## Out of scope
- <work excluded from this follow-up>

## Acceptance criteria
- [ ] Resolve each soft finding listed above.
```

**Self-improve intake.** Failures and near-misses become candidate cards, not
chat. The coordinator accepts or closes each card in the same triage window,
tags it `repo:` or `crew:`, and an accepted card is a normal builder tracker
item. The lesson (`docs/lessons/`, plus a findings-buffer one-liner) is the
memory; triage never edits a skill, and harness changes merge only through the
normal gate. Details in [self-improve.md](self-improve.md).

**Owner decisions: one channel and a 2h SLA.** Owner asks go only through the
coordinator, posted on the backend (on GitHub, a PR review body or issue
comment) and over the [owner channel](concepts.md#owner-channel) (the
coordinator's chat with the user). Builders and reviewer-validators never ask
the user only in their own chat. If that happens, the coordinator re-posts the
ask on the backend and over the owner channel; the originating role links the
backend post from its own chat.

The coordinator monitors any `crew:hold`, `crew:escalated`, or pending
`/crew merge-ok` waiting on the user. After more than **2h of the user's awake
hours, measured in Pacific Time (PT)**, it adds `crew:needs-md` and pings the
user through that channel with: the change/tracker-item link, a one-line
question, a **recommended default**, and an **auto-apply time** (explicit date
and time in PT). This coordinator duty still runs on held or escalated items;
work roles continue to no-op. The coordinator's sweeper (on Grok Bot the
stuck-PR sweeper) performs this routine promotion only for held/escalated
changes and tracker items whose latest hold/escalation asks the user for a
decision, adding `crew:needs-md` only if absent and naming them in its summary
for the coordinator to ping. Lane/dependency holds carry a coordinator note
naming the blocking change/tracker item and are not promoted. It leaves
existing hold/escalation state tags in place. An intentional reviewer verdict
hold gets `crew:needs-md` immediately; the coordinator routes that ask through
the same channel and SLA.

At the auto-apply time, if the user has not answered, the coordinator applies
the posted default and records it on the change/tracker item. Allowed defaults
are:

- **Merge:** only 🟢/🟡 doc-only changes with green CI that qualify for the
  standing grant below; the coordinator hands the merge to the synthesizer,
  which re-checks every §7 gate. Never auto-apply a merge to code, workflow,
  or `docs/protocol.md` changes.
- **Defer:** close as not planned, with a note explaining when to reopen.
- **Keep hold:** leave the item on hold and record that decision.

The coordinator clears `crew:needs-md` once the user answers or the default
is applied; it does not clear other holds merely because the SLA expired.

**Standing doc-only merge-ok (user grant, 2026-10-25).** The user grants standing
merge-ok for doc-only changes with no code, no `.github/`, no `templates/`, and
no `docs/protocol.md` changes, only 🟢/🟡 findings, and green CI. The
synthesizer may merge qualifying changes without a per-change `/crew merge-ok`.
This substitutes only for that per-change permission: all other §7 gates still
apply, including review and validation approval. The lighter-lane exemptions
below apply to the builder watch and mirror hold. Spec changes still require
the user's per-change merge-ok.

**Lighter lane.** A change qualifies if it touches only docs, with no code, no
`.github/`, no `templates/**`, and no `docs/protocol.md` changes. The builder
installs no per-change watch (B2 on Grok Bot) and posts no `pass=watch`
marker; `crew:needs-mirror` never applies. Green CI and the usual
reviewer/validator pass (a pass verdict, `APPROVE`) are still required, with
per-change or standing merge-ok as applicable. The standing grant supplies
permission only; the user's per-change merge-ok has its usual §7 override
semantics.

Grok Bot runtime: how fixes, red CI and cleanup reach the builder without B2
is in [lighter-lane routing](runtimes/grok-bot.md#lighter-lane-routing).

**Per-PR watches (routine limits).** Grok Bot runtime: see
[per-PR watches](runtimes/grok-bot.md#per-pr-watches).

**The hand-off is verified, not fire-and-forget.** Grok Bot runtime: see
[verified hand-off](runtimes/grok-bot.md#verified-hand-off).

**Comment reviews do wake comment listeners.** Grok Bot runtime: see
[comment-listener wakes](runtimes/grok-bot.md#comment-listener-wakes).

Further duties:

- **Label hygiene.** Whoever sets `crew:approved` or `crew:changes` (the
  reviewer's verdict pass) removes `crew:in-review` in the same step. The same
  verdict pass adds `crew:needs-mirror` to a change that touches
  `docs/protocol.md` or `templates/`, and does so **before** posting the
  verdict, because `review-approved` wakes the synthesizer at once and the hold
  must already exist. A re-review skips re-adding the state tag when the
  coordinator's mirror comment is already on the change and is newer than the
  last commit touching `docs/protocol.md` or `templates/` (nothing
  mirrored-relevant changed since the mirror); if a later commit changed those
  paths, it re-adds the state tag. Lighter-lane changes never get
  `crew:needs-mirror` ([mirror hold gate](runtimes/grok-bot.md#mirror-hold-gate)).
- **Box-skill mirror.** The coordinator deploys the rendered output for the
  live profile to the live dir (and, for a `docs/protocol.md` change, edits the
  `eng-pr-pipeline` box skill), then runs the drift check at the change head
  ([mirror hold gate](runtimes/grok-bot.md#mirror-hold-gate)). Only on a clean
  result does it post the box-skill mirror comment (for example
  `[Ash] box skill mirrored`) with the command and output inline, remove
  `crew:needs-mirror` and then ping `<SynthesizerBot>`, because state tag
  changes wake nobody.
  Re-confirm duty: if a later commit changes `docs/protocol.md` or `templates/`
  after the mirror comment, the state tag is re-added and the coordinator posts
  a fresh mirror comment and removes the state tag again. Lighter-lane changes
  have no box-skill mirror hold.
- **Unique worktrees.** Every worker run uses its own directory
  `<worktree-root>/<pr>-<sha7>-<role>-<pass>/` (see the roles doc). Never share
  `<worktree-root>/<branch>` across runs; a mid-pass delete of a shared tree is
  unsafe even if the review falls back to a code trace.
- **Worker toolchain.** Builder and fix workers pin the repo's required
  toolchain (e.g. Node version on `PATH`, `COREPACK_HOME`) before any commit or
  push, so pre-push hooks don't fail on the box's defaults.
- **Default-branch CI.** If the default branch runs CI on push, the
  coordinator also wakes on a red [CI signal](concepts.md#ci-signal) on the
  default branch (on Grok Bot, its after-merge routine listens for `ci-failed`
  with `ciBranch` set to the default branch), and files a `crew:ready` fix
  tracker item instead of touching the default branch.
- **Repo tracking.** Every crew repo requires milestones (M1, M2, …) and a
  board ([on GitHub](backends/github.md#tracking), GitHub Milestones and a
  GitHub Project board); the coordinator resolves missing setup using the
  onboarding runbook. Closed milestones are frozen: no new tracker items;
  follow-ups go to the next `M*`. Board and linkage mechanics:
  [GitHub backend: Tracking](backends/github.md#tracking).

Role specifics:

- **Builder / `issue-assigned`.** Needs `crew:ready` and no open change or
  branch for it already. Pick role, tier and engine per the roles doc. After
  the change opens: tag it, add it to the board, attach the per-change watch
  the runtime requires, verify it and post the full-SHA `pass=watch` marker.
  On Grok Bot that watch is B2 (`ci-failed`, `review-changes-requested`,
  `pr-merged`, `pr-closed`), and the parent turn alone verifies it, records the
  routine folder id and posts the marker
  ([verified hand-off](runtimes/grok-bot.md#verified-hand-off)).
  Lighter-lane changes skip watch attachment, verification and the marker;
  fixes and cleanup arrive by message as described in
  [lighter-lane routing](runtimes/grok-bot.md#lighter-lane-routing).
  - **`review-changes-requested`:** relaunch on the same branch, preferably the
    same engine; post `fix` after pushing.
  - **`ci-failed`:** ignore cancelled or superseded runs; fix real failures on
    head; post `ci-fix`.
  - **Conflicts** handed over by the synthesizer: merge `<default-branch>` in
    with a merge commit, resolve, push.
  - **`pr-merged` / `pr-closed`:** delete the worktree and build output.
- **Reviewer-validator / `pr-opened`.** Post an `ack` narrative post, attach
  the reviewer's per-change watch for `new-head`, `review-requested`,
  `pr-merged`, `pr-closed` (Grok Bot still uses `ci-passed` in place of
  `new-head` until mirrored; [declared gap](runtimes/grok-bot.md#review-start-gap)), tag external changes
  `crew:external`. Skip the ack on drafts. When posting its first verdict on a
  crew change outside the lighter lane, if no builder `pass=watch` marker (full
  40-char SHA of any commit on the change, not only the head) is on the
  change, the reviewer (on Grok Bot, its parent turn) pings `<BuilderBot>`
  with priority to attach the watch and post the marker, and tells
  `<CoordinatorBot>`. The reviewer never creates the builder's watch. The
  synthesizer also holds the merge until the marker is present
  ([builder watch gate](runtimes/grok-bot.md#builder-watch-gate)), unless
  exempt. Do not ping for a builder watch on lighter-lane changes.
  - **`new-head` (opened or pushed):** review engine ≠ the builder's (the
    engine that actually
    wrote the round under review; see [roles](roles.md#actual-builder-engine)).
    The [quota diversity waive](roles.md#quota-diversity-waive) permits a
    matching engine for one round's verdict; reviewer identity must still differ.
    Review, then validation, without waiting for CI. Both passes record the
    observed CI state as information only; CI state alone never fails an
    acceptance criterion or changes a verdict. Independently reproduced
    failures remain findings. CI green at head stays a §7 merge gate.
    - **Intentional verdict hold.** If the verdict must wait for a user
      decision, add `crew:needs-md` and post a narrative post headed
      `[<ReviewerBot>/hold] @ <sha7>` naming the open item and decision needed,
      with marker
      `<!-- crew:v1 role=reviewer-validator pass=hold pr=<n> sha=<full-40-char-head-sha> round=n/a verdict=n/a -->`.
      This is neither a verdict nor a round. Route the ask via the coordinator
      under the owner SLA above; do not leave the wait only in chat. A failed
      validation still requires `REQUEST_CHANGES`; a hold cannot override it.
      When the user answers, the coordinator clears `crew:needs-md` and posts
      the [rereview steer marker](#3-evidence-requirements), then
      [re-requests review](#9-steering-crew-commands). The marker plus the
      review request wakes the reviewer to review, validate and issue the verdict.
    - **CI fix after approval.** The pushed head starts a light re-check in
      fresh review and validation sessions: inspect the CI-fix hunks and rerun
      acceptance checks. Record CI as information only. If clean, post the
      normal pass verdict with both pass sections at the new head using the
      approval's round number. Broader behavioural edits require normal review;
      independently reproduced failures require a changes verdict as usual.
      This is no per-PR CI-only path: approval and all §7 gates still apply.
    - **Merge-up push.** A push whose only new commit is a merge of
      `<default-branch>` into the change's branch (the backend's update-branch,
      [on GitHub](backends/github.md#land-and-merge-up), or a builder merge-up)
      never uses up a review round. Do the light re-check: inspect the
      conflict-resolution hunks, rerun the acceptance checks at the new head,
      record the observed CI state as information only. Then:
      - *Clean, last verdict at the previous head was `APPROVE`
        (`verdict=pass`):* post a pass verdict (`APPROVE`) at the new head with
        the **same round number** as that approval (a **merge-up re-approve**).
        The header is `[<ReviewerBot>/verdict] round <k> (merge-up re-approve)`.
        The body is a normal verdict body: a review section (the hunk check) and
        a validation section (acceptance checks rerun at the new head), each
        with its own marker saying `verdict=pass`, and the final marker
        `<!-- crew:v1 role=reviewer-validator pass=verdict pr=<n> sha=<new-head-sha> round=<k> verdict=pass -->`.
        The re-approve is the single verdict at that head, posted once.
        An `APPROVE` never moves the round count, and it fires `review-approved`
        so the synthesizer wakes normally. State tags stay `crew:approved`.
      - *Clean, last verdict was `REQUEST_CHANGES` (`crew:changes`):* post one
        narrative post
        `[<ReviewerBot>/ack] merge-up @ <sha7>, verdict pending fix`
        with marker
        `<!-- crew:v1 role=reviewer-validator pass=ack pr=<n> sha=<head-sha> round=n/a verdict=n/a -->`.
        No round, no verdict, no state tag change. The ack is narrative only and
        never counts as an approval anywhere (merge gate, sweeper).
      - *Conflict resolution changes behavior or content (anything beyond a
        mechanical clean merge):* a normal review round: full review and
        validation, a normal verdict, round counted as usual.
  - **`review-requested`** for the reviewer identity with a `steer cmd=rereview`
    marker newer than the last verdict: fresh full review and validation at
    head, even if the head is a merge-up (the merge-up shortcut applies only to
    `new-head` wakes).
- **Synthesizer / `review-approved`, or `ci-passed` with approval at head.** Land rule, gate check and merge
  ([Merge gate](#7-merge-gate-synthesizer),
  [land rules](#land-rules-and-merge-trains)). After each lone land, and once
  a merge train ends (never between its members), sweep open crew
  changes: behind-but-mergeable ones get the backend's update-branch (post
  `merge-up`; [on GitHub](backends/github.md#land-and-merge-up));
  conflicting ones go to the builder by message. Dependent changes merge in
  `Depends on` order.
- **Coordinator / `pr-merged`.** Update the board, advance the parent
  sub-spec, tag and assign the next unblocked tracker item. Escalations from
  others arrive as messages.
- **Coordinator / steering dispatcher.** When evidence changes without a new
  head commit, post the rereview steer
  ([Evidence requirements](#3-evidence-requirements)).

## Protocol freeze

`docs/protocol.md` and `templates/` change only in milestone batches for the
open `M*`. A lesson found mid-milestone is filed as a tracker item on the next
milestone, rather than merged as a one-off protocol change. The exception is a
fix for a gate that is blocking merges right now; that fix must follow the gate
contract below.

The M2 success drill (issue #52) verifies this freeze, SLA and triage batch
end-to-end; it is not itself a protocol change.

## Gate contract

Any new or changed merge gate must state in the same change:

- What satisfies it: the exact marker, state tag (label) or check.
- Who can satisfy it and how fast.
- Its fail-open path if it cannot be satisfied. The default is the user's
  per-change `/crew merge-ok`, or the standing doc-only merge-ok from §6 where
  applicable.

A gate with no fail-open path is not merged. Fail-open must respect §7: it is
not a blanket waiver. Where no override exists, use the §6 owner-decision
path: the coordinator escalates, adds `crew:needs-md` after more than 2h of
awake hours PT, and posts a recommended default and auto-apply time. The user
can decide how to resolve the blocker, defer/close, or keep hold. An allowed
default may apply at that time; it never clears another gate or hold by itself.
CI is never waived by merge-ok: failed checks need a fix or a decision to
defer/close, not a merge through red CI.

### Gate registry

This table summarizes the §7 gates; their detailed conditions and exemptions
remain in §7, or, for a runtime gate, in the runtime binding §7 links. The
owner-decision path below means the §6 SLA above, not permission to merge with
an unsatisfied gate. **Binding** says where the gate's satisfaction rule is
stated: `core` (this protocol), `runtime` (the
[runtime binding](runtimes/README.md)) or `backend` (the backend binding). Every
gate applies whatever its binding.

| Gate | Satisfied by | Who / how fast | Fail-open | Binding |
|---|---|---|---|---|
| Owning runtime | Record names this instance with no open handoff, or no record exists; unreadable blocks | Coordinator posts the owner's command; synthesizer re-reads before land | Owner aborts or commands takeover; no merge-ok or standing-grant waiver | core |
| Formal approval at head | Reviewer-identity formal approval (`APPROVED`) at head: `pass=verdict verdict=pass sha=<head>` with review + validate pass markers, or `pass=steer cmd=merge-ok sha=<head>` | Reviewer-validator on `new-head`; coordinator dispatches the user's override under the §6 2h awake-hours PT SLA | User's per-change `/crew merge-ok`; standing permission alone never supplies approval | core |
| Merge permission | User's per-change `/crew merge-ok`, or qualifying standing doc-only merge-ok (§6); spec changes require per-change permission | User via coordinator; standing grant immediately if qualified, otherwise §6 SLA | Standing grant where applicable; otherwise owner-decision path | core |
| No later changes request or hold/escalation | No later reviewer-identity changes request (any `REQUEST_CHANGES`: a changes verdict or a steering signal such as `steer cmd=rework`); no `crew:hold` / `crew:escalated`, unless user's per-change merge-ok | Reviewer resolves findings; coordinator dispatches user steering under §6 SLA | User's per-change `/crew merge-ok`; `/crew resume` clears hold/escalated and re-kicks the stage, but supplies no approval | core |
| Engine disagreement resolved | Note/trailer wins; fresh review + validation verdict at head on an engine different from the actual builder, after `steer cmd=rereview`. An open rereview at the current head blocks squash until that verdict lands; `merge-ok` and a prior `APPROVE` do not satisfy it | Coordinator steers; reviewer-validator on `review-requested` | Owner-decision path; no `merge-ok` or standing-grant waiver of the re-check | core |
| No open coordinator hold | No explicit hold-until-X or crew hold command on the change or in the synthesizer inbox; it overrides standing doc-only merge-ok until the hold clears or dependency X lands | Coordinator posts and clears the hold; synthesizer re-reads the change and inbox right before merging | Coordinator releases the hold or the dependency lands; owner-decision path if neither; no standing-grant waiver | core |
| Required evidence | For a behaviour-changing change, each shape's artifact named in `## Acceptance Evidence` or a fix-round note exists on the change head and the validation section says `agrees`, or carries a reasoned N/A ([verification](verification.md)); docs-only and no-behaviour changes are N/A; lighter-lane changes are N/A unless they change behaviour | Builder when the change opens or in a fix round; reviewer-validator on `new-head` | User's per-change `/crew merge-ok` for evidence that cannot be produced (`unverified`); standing doc-only merge-ok never covers a behaviour-changing change; no waiver of CI | core |
| Builder watch | `role=builder pass=watch watch=b2 status=attached`, full SHA of any commit on the change; external, cutover, coordinator-opened spec and lighter-lane exemptions per the [builder watch gate](runtimes/grok-bot.md#builder-watch-gate) | Builder parent turn right after the change opens, after verifying B2 | Synthesizer pings builder with priority; builder attaches/posts, tells coordinator if unable; unresolved blocker goes through owner-decision path, with no new watch waiver | runtime ([Grok Bot](runtimes/grok-bot.md#builder-watch-gate)) |
| No mirror hold | Path-derived: for `docs/protocol.md` or `templates/`, no `crew:needs-mirror` and a coordinator mirror comment newer than the last touching commit, recording the rendered output deployed to the live dir and a clean drift check at that commit (`check-skill-drift.py` exit 0: no `DRIFT`, `MISSING` or `EXTRA`; `WORDING` allowed), command and output inline; or, on tmux only, a profile-named recorded owner standing mirror deferral whose source the synthesizer reads and whose scope covers this PR, with no live Grok Bot behaviour change, named in the merge record ([tmux](runtimes/tmux.md#crew-train)); lighter lane exempt ([mirror hold gate](runtimes/grok-bot.md#mirror-hold-gate)) | Reviewer tags before verdict; coordinator deploys, runs the check (seconds), posts the comment, removes state tag and pings synthesizer on its next turn after the verdict | Owner-decision path if the deploy or a clean check cannot be completed; tmux may use only the recorded scoped mirror deferral above, which supplies no merge permission; no standing merge-grant waiver | runtime ([Grok Bot](runtimes/grok-bot.md#mirror-hold-gate)) |
| Tested with `<default-branch>` | The head contains the current `<default-branch>` tip, or the change is the next member of a green merge train whose tested state is the current `<default-branch>` (the train base, then the commit the previous member's land made), at the head the train tested; that member's merge record cites the train branch, SHA and CI run ([land rules](#land-rules-and-merge-trains)) | Synthesizer at land time: update-branch, then CI (minutes) and every gate again at the new head; or one train CI run for all members | Update-branch always applies; a real conflict goes to the builder; owner-decision path if neither resolves it; no merge-ok or standing-grant waiver, since it guards CI on the landed result | core |
| CI and change state | All required checks green at head; not draft, mergeable, base = `<default-branch>` | CI normally minutes; builder fixes CI (≤3 attempts) and conflicts; author corrects draft/base | CI-fix cap then escalation → user decision (fix, defer/close); merge-ok never waives CI. Unresolved change state also uses owner-decision path | core |
| Linked issue | `Closes #n`; spec, external and cutover exemptions; never auto-close umbrella or TRD | Builder when the change opens; correct linkage before merge | Owner-decision path if linkage cannot be resolved; no new exemption | backend ([GitHub linkage](backends/github.md#linkage)) |
| Release approval (guards publishing, not merging; §7 does not check it; [design](release.md#release-gate)) | The owner's per-PR `pass=steer cmd=merge-ok sha=<head>` marker at the cut PR's head, verified by the [release workflow](../.github/workflows/release.yml) publish job on the merged cut PR, with its validate job green and the push actor matching the `RELEASE_OWNER` repository variable. Landing the cut PR triggers validation, tagging the merge commit and publishing in one run; the standing grant never covers a cut PR. Shared owner-level accounts ([merge enforcement](merge-enforcement.md)) mean the actor check alone cannot distinguish a bot from the owner: no role invents owner authorization. Dispatch remains for dry runs and owner-only manual fallback with the same approval and actor check | Owner on the cut PR before landing, on the coordinator's ask under the §6 owner SLA; publish job verifies before tagging | None for publishing: no standing grant or auto-applied default publishes a release. The §6 owner-decision path may only defer or cancel it | backend (GitHub release workflow) |

## Sensitive class

At triage and PR open (and after each push), the coordinator or builder runs
`python3 scripts/crew-config.py sensitive --project crew.toml` with the full
repo-relative diff paths on stdin, including both old and new rename paths.
At triage use the paths explicitly named by the issue; the PR check uses the
actual diff. Apply `crew:sensitive` to the item/change when a path matches,
recording the matched paths and rules on the tool of record. An issue already
labelled sensitive transfers that label to its PR. Defaults cover CI/release
workflows, auth, secrets, permissions/access control, migrations and deletions;
[profile additions](profile.md#sensitive) extend them.

Only the owner may override the classification: record their words and reason
on the item/change before clearing the label. Re-check new paths on every push;
a prior override covers only its recorded paths. The synthesizer reads the
current label and the owner record; it never reclassifies paths at merge time.

## 7. Merge gate (synthesizer)

All of these must hold **at the current head SHA**, re-checked right before
merging:

- The ownership record names this runtime with no open handoff, or no record
  exists. An unreadable record blocks land. Neither merge-ok nor a standing
  grant overrides this gate.

- A formal approval from the reviewer identity at head (a pass
  [verdict](concepts.md#verdict) or a merge-ok steering signal;
  [on GitHub](backends/github.md#review-types-and-the-events-they-fire), a
  formal `APPROVED` review) carrying
  **either** `pass=verdict verdict=pass sha=<head>` (with review + validate
  sections whose own markers both say `verdict=pass`; an `APPROVE` over a failed
  validate marker does **not** count) **or**
  `pass=steer cmd=merge-ok sha=<head>`. `merge-ok` is the user's override; it
  skips validation and escalation but never CI. Spec changes merge only on
  `merge-ok`. A [narrative post](concepts.md#narrative-post) (such as a
  merge-up ack; on GitHub a COMMENT review) never satisfies this gate; only the
  formal approval (`APPROVED`) does.
- The user's per-change `/crew merge-ok`, or the **standing doc-only merge-ok**
  grant in §6 for a qualifying change. The standing grant substitutes only for
  per-change permission; it never supplies a formal approval, skips
  validation, overrides a hold/escalation, or exempts a spec change from
  per-change merge-ok.
- A `crew:sensitive` change has the owner's per-change merge-ok at the current
  head. No standing grant (including doc-only or project grants) covers it.
  A recorded owner classification override may clear the label as above.
- No later changes request (`REQUEST_CHANGES`) from the reviewer identity,
  whether a changes verdict or a steering signal such as `steer cmd=rework`
  ([Steering](#9-steering-crew-commands)); on GitHub, no later
  `REQUEST_CHANGES` review from the reviewer identity. No `crew:hold` /
  `crew:escalated` (unless the user's per-change `merge-ok`).
- No open coordinator hold. An explicit coordinator hold-until-X (or a crew
  hold command) already on the change or in the synthesizer's inbox
  **overrides** the standing doc-only merge-ok. Do not squash until the hold
  clears or the named dependency X has landed on `<default-branch>`. Re-read the
  change and the inbox right before merging; a hold posted after the approval
  wake still counts.
- If the builder marker and the fix note or commit trailer disagree on the
  engine, the note or trailer wins, and before merge the reviewer re-checks at
  head (fresh review + validation) on an engine different from the actual
  builder engine. The coordinator posts the rereview steer
  (`steer cmd=rereview`) at head, with the same ack and re-request mechanics as
  the evidence-only rereview in §3 and [Steering](#9-steering-crew-commands).
  Do not merge until that re-check verdict is posted. An open
  `steer cmd=rereview` at the **current head** (engine diversity or a disputed
  engine) blocks the squash until a fresh reviewer-validator verdict
  (`pass=verdict`) lands at that SHA on an engine different from the actual
  builder engine. `merge-ok` does not override it, and a prior `APPROVE` from
  the same or another engine does not satisfy it.
- Required evidence is present. For a behaviour-changing change, the artifact
  for each shape named in `## Acceptance Evidence` or in the fix-round note is
  on the change head, and the verdict's validation section marks it `agrees`
  (or the N/A reason is accepted). `unverified` needs the user's per-change
  merge-ok; `disagrees` blocks. A missing
  artifact without a reasoned N/A blocks the squash. Docs-only and
  no-behaviour changes are N/A. The synthesizer checks presence at head and the
  verdict; it does not re-run the evidence. Fail-open is the user's per-change
  `merge-ok`, never a standing grant. Detail:
  [verification](verification.md).
- **Runtime gates.** Every runtime gate the runtime binding declares is
  satisfied at head. The binding states, for each one, what satisfies it, its
  exemptions and what the synthesizer does while it is unsatisfied; its
  registry row gives who satisfies it and its fail-open
  ([Gate registry](#gate-registry)). While a runtime gate is unsatisfied, do
  not merge. Today's Grok Bot binding declares two
  ([runtime gates](runtimes/grok-bot.md#runtime-gates)):
  - **Builder watch:** the builder's `pass=watch` marker
    (`role=builder pass=watch watch=b2 status=attached`) with `sha=` the full
    40-char SHA of **any** commit on the change. Exempt: external, cutover
    (until its builder posts after the cutover), coordinator-opened
    `crew:spec` and lighter-lane changes
    ([builder watch gate](runtimes/grok-bot.md#builder-watch-gate)).
  - **No mirror hold:** a change touching `docs/protocol.md` or `templates/`
    has no `crew:needs-mirror` and a coordinator box-skill mirror comment,
    newer than the last commit touching those paths, that carries a clean
    drift check at that commit, derived from the changed paths, not only the
    state tag. On tmux, a profile-named recorded owner standing mirror
    deferral may satisfy this gate for a PR within its verified scope that
    does not change live Grok Bot behaviour; the synthesizer reads the source
    decision and names the deferral in the merge record, without needing a
    per-PR coordinator comment or label removal. An uncovered PR or an
    unreadable source still needs a real mirror. This supplies no merge
    permission; gate changes still require the owner's per-PR merge-ok
    ([tmux](runtimes/tmux.md#crew-train)). Lighter-lane changes are exempt
    ([mirror hold gate](runtimes/grok-bot.md#mirror-hold-gate)).
- **Tested with `<default-branch>`.** The head contains the current
  `<default-branch>` tip, or the change is the next member of a green merge
  train whose tested state is the current `<default-branch>` (the train base,
  then the commit the previous member's land made), at the head the train
  tested ([land rules](#land-rules-and-merge-trains)). Otherwise update-branch
  it first; the new head then needs CI and every gate here again.
- The [CI signal](concepts.md#ci-signal) is green at head (all required
  checks). The change is not draft, is mergeable, and its base is
  `<default-branch>`.
- Tracker item linked (`Closes #n`) unless it is a spec, external or cutover
  change; never auto-close an umbrella or TRD tracker item
  ([linkage on GitHub](backends/github.md#linkage)).

Then take the repo merge lock, [land](concepts.md#land) the change bound to
the head the gate checked
([on GitHub](backends/github.md#land-and-merge-up):
`gh pr merge <n> --squash --match-head-commit <sha>`), post `merge`, and
release the lock. If head moved, stop.

Merge-only-by-synthesizer is **convention** until the backend enforces review +
checks (on GitHub, branch protection) and the synthesizer has its own identity
(e.g. a GitHub App) that alone may merge.
The M4 [merge-enforcement runbook](merge-enforcement.md) documents the target
ruleset; it is not live on this repo yet (2026-10-28: account-plan gap).
Its fail-open path keeps this §7 convention gate in place until application,
and uses the owner-decision path for a live ruleset blocker without waiving CI.

### Land rules and merge trains

Batching approved changes into a merge train is a standing synthesizer skill
in every runtime: a train tests them together once, then lands them with no
catch-up between them. A change is **ready** when every gate above holds at
its head except tested with `<default-branch>`. At each wake the synthesizer
surveys every open crew change and picks one land rule:

| Situation | Land rule |
|---|---|
| `train_min` or more changes ready at once | Train them all now |
| Fewer ready, none close (no other change in review or re-check that should pass within `train_window`) | Merge each alone now: directly if its head contains `<default-branch>`, else update-branch first |
| Fewer ready, another close within `train_window` | Wait for it, then train |
| A ready change is urgent: a release blocker, a security fix or an owner request | Merge it alone now, whatever the batch |
| A change has waited `train_window` | Stop waiting: train what is ready, or merge it alone |

`train_min` defaults to 2 and `train_window` to 600 seconds (10 minutes).
On tmux they are the [profile options](profile.md)
`runtime.options.train_min` and `runtime.options.train_window`. Nothing waits
past the window, so a runtime with no timer wake for the synthesizer does not wait (Grok Bot today). Each
`[<SynthesizerBot>/merge]` record names its rule in one line, for example
`Land rule: train of 3 (ready at once)`, `Land rule: alone, urgent (release
blocker)` or `Land rule: waited 6 min to batch with #A and #B`.

1. **Build.** Branch `crew/train-<n>` from the current `<default-branch>`
   (the train base) and merge each ready change's head into it with a merge
   commit, in `Depends on` order, then approval order. A change that
   conflicts is dropped and goes to its builder.
2. **Test once.** Push the branch and run CI on it through a draft change
   that is for CI only and never lands.
3. **Land.** Only on green CI, under the merge lock: land each member in
   order, bound to the head the train tested, re-checking every gate above
   right before its squash. No update-branch runs between members. At the
   first miss, stop; the rest go to a new train or land alone.
4. **Red.** On red CI nothing lands; land the members one at a time
   (bisecting a red train comes later).
5. **Record and close.** Each member's merge record cites the train branch,
   its SHA and the CI run as its tested-with-`<default-branch>` evidence.
   When the train ends, close the draft change and delete the branch.

On tmux, `crew train` runs these steps
([crew train](runtimes/tmux.md#crew-train)).

## 8. Safety

- Work roles listen only to state-transition events: `issue-assigned`,
  `pr-opened`, `new-head`, `ci-passed`, `ci-failed`, `review-requested`, `review-approved`,
  `review-changes-requested`, `pr-merged`, `pr-closed`. **Only the steering
  dispatcher** subscribes to `pr-comment` / `inline-review-comment`. Nobody
  subscribes to `review-commented`.
- Each event has exactly one consuming role, with one narrow exception:
  PR-scoped `pr-merged` / `pr-closed` are terminal events that may reach both
  the builder's per-PR watch (B2) and the reviewer-validator's per-PR watch (V2).
  A routine run cannot delete another routine, so each watch must receive the
  terminal event itself to clean up its own state (the builder's worktrees and
  build output) and then delete itself. Every other event, including the
  repo-wide `pr-merged` the coordinator consumes, keeps exactly one consumer.
  Loops are bounded by the round cap and the CI-fix cap.
- External (fork) PRs: validation runs the code in an isolated sandbox with
  **no tokens**. First-time contributors' workflows may need manual approval
  before CI fires: flag it to the coordinator. Builders never push to fork
  branches.
- Only one automation system may own a repo at a time, enforced by the
  [ownership record](#ownership-record) when configured.
- Product repos MUST ship a human-readable root `README.md` with the sections of
  [templates/product-readme.md](../templates/product-readme.md) (problem, what it
  is, how to run / use, how the crew works, status); a seed PR that skips it is
  red.
- Workers never post to GitHub; only role bots post.
- Every wake costs a full bot turn: keep listeners tight and end no-op wakes
  within a few tool calls.

## 9. Steering: `/crew` commands

The user steers a PR with a PR conversation comment or inline review comment
whose **first line** starts with `/crew`:

| Command | Owner | Effect | Dispatcher hands it off via |
|---|---|---|---|
| `/crew hold` | Coordinator | Add `crew:hold` | Acts itself |
| `/crew resume` | Coordinator | Remove hold / escalated, post `resume` marker (resets rounds), re-kick the current stage | No verdict at head → re-request the reviewer; last verdict changes → `REQUEST_CHANGES` steer review; approved at head → `APPROVE` steer review `cmd=resume` |
| `/crew rework: <note>` | Builder | Relaunch on the branch with the note (+ `file:line` if inline) | `REQUEST_CHANGES` as reviewer identity, `steer cmd=rework`; not a round |
| `/crew rereview` | Reviewer-validator | Fresh review + validation at head | `steer cmd=rereview` ack, then re-request the reviewer identity |
| `/crew merge-ok` | Synthesizer | User override: merge once CI is green; required for spec PRs | `APPROVE` as reviewer identity, `steer cmd=merge-ok sha=<head>` |
| `/crew escalate` | Coordinator | Add `crew:escalated`, post summary, bring to the user | Acts itself |

Rules:

- **Accepted only** from the user's own accounts (`<user-logins>`), checked
  against the **commenter** login (listener allowlists gate the PR author, not
  the commenter).
- Unknown command, wrong commenter, or non-command comment: no-op, no reply.
- **Ack.** The dispatcher posts a COMMENT review
  `[<CoordinatorBot>/steer] ack <cmd> @ <sha7>` with marker
  `pass=steer cmd=<cmd> cmd-id=<comment id>`. A `cmd-id` already acked is never
  re-run; edited comments are ignored.
- Commands respect `crew:hold` except `resume`, `escalate` and `merge-ok`.
- **Issues can't be steered by comment** (no issue-comment event): use
  assignment, labels (`crew:ready`, `crew:hold`), or chat with the coordinator
  ([steering limits on GitHub](backends/github.md#steering-limits)).

## Worked example / pilot notes

Grok Bot runtime: the agentconnect pilot notes are in
[runtimes/grok-bot.md](runtimes/grok-bot.md#pilot-notes).
