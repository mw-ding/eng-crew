# Stage protocol

> **Two copies, kept in sync (spec R4).** The box skill `eng-pr-pipeline` is the
> **live** copy the bots load. This document is the **reviewed** copy. Any
> change to one must be mirrored to the other in the same change, through a PR
> in this repo plus a matching edit to the box copy. See
> [the spec](specs/framework.md).

One issue → one branch → one PR → one squash merge. Each stage is woken by a
GitHub event (a GitHub-triggered routine on that bot), does its job through
fresh workers, and leaves its result **on GitHub** (labels, markers, a formal
review) so the next stage can read it. Nothing important lives only in a bot's
chat. A per-repo wiring doc (trigger JSON per bot) lives in the shared state dir
at `<state-dir>/<owner>__<repo>/wiring.md`.

Engines, tiers, worker briefs, branch naming, PR body sections, worktree
isolation and cleanup are covered by the roles doc
([roles.md](roles.md), worktree isolation in
[Worker isolation](roles.md#worker-isolation-worktrees); the box skill is
`eng-crew-roles`). This document adds the stage
protocol on top of it. For a shorter overview with a diagram, see
[architecture.md](architecture.md).

**Hard rules, everywhere:**

- Reviewer engine ≠ builder engine (the engine that actually wrote the round).
- Never `--no-verify`.
- Never force-push a shared branch.
- Merge-up uses a merge commit or GitHub update-branch, never a rebase.
- Squash-merge only.
- Only the synthesizer merges.
- Eng workers never use Cursor CLI.
- One formal review per head SHA (a clean merge-up after changes gets a merge-up ack instead; see [Duties on wake](#6-duties-on-wake-all-roles)).
- Max 3 verdict rounds and ≤3 CI-fix attempts per PR.
- Workers never post to GitHub; only role bots post.

Placeholders: `<owner>/<repo>`, `<state-dir>`, `<default-branch>`,
`<author-login>`, `<reviewer-login>`, `<user-logins>`, `<CoordinatorBot>`,
`<BuilderBot>`, `<ReviewerBot>`, `<SynthesizerBot>`.

## 1. Roles and GitHub identities

See [architecture.md](architecture.md) for the identity model.

| Role | Woken by | Owns | GitHub identity |
|---|---|---|---|
| Coordinator (also **steering dispatcher**) | The user (chat), escalations, `pr-merged`, `pr-comment` / `inline-review-comment` | Spec, issues, Project board, escalations, next assignment, `/crew` commands | Author identity (`<author-login>`); reviewer identity (`<reviewer-login>`) for steering signals |
| Researcher | The coordinator's message | Research notes for specs; no PRs unless asked | Author identity |
| Builder | `issue-assigned`, `review-changes-requested`, `ci-failed` | Branches, commits, PRs, fix rounds, conflict resolution | Author identity |
| Reviewer-validator | `pr-opened`, `ci-passed`, `review-requested` | Review pass, validation pass, the one formal verdict | **Reviewer identity** (`<reviewer-login>`), which must differ from the PR author, or GitHub refuses `APPROVE` / `REQUEST_CHANGES` |
| Synthesizer | `review-approved` | Merge gate check, serial squash merge, update-branch of PRs that are behind | Author identity (later: its own App identity) |

The bots share accounts, so **GitHub actor filters cannot tell bots apart**. A
bot action's identity comes from its **signed marker**, not the account (see
[Marker conventions](#4-marker-conventions)).

## 2. Stages

1. **Spec (coordinator + user, researcher on demand).** The coordinator writes
   `docs/specs/<topic>.md` plus incremental sub-specs (one per buildable
   slice), lands them through a `crew:spec` PR (review pass only, merges on
   `/crew merge-ok`), then opens one issue per slice. Each issue body: goal,
   numbered testable acceptance criteria, out-of-scope, spec link, role + tier
   hint, dependencies (`Depends on #n`). Add each issue to the Project. Heavy
   research goes to the researcher in the background so the coordinator keeps
   talking with the user.
2. **Handoff.** The coordinator adds `crew:ready` and assigns the issue to the
   author identity. `issue-assigned` wakes the builder.
3. **Build.** The builder fans out one worker per issue (see
   [Duties on wake](#6-duties-on-wake-all-roles)). The worker builds, runs
   tests and build, and opens a **non-draft** PR with `Closes #n` and the
   evidence body ([Evidence requirements](#3-evidence-requirements)). The
   builder labels it `crew:in-review`; its parent turn attaches the per-PR watch B2
   and verifies it ([stage 6](#6-duties-on-wake-all-roles)).
4. **CI.** Checks must settle green. `ci-failed` wakes the builder (fix on the
   same branch, ≤3 CI-fix attempts, then escalate). `ci-passed` wakes the
   reviewer-validator.
5. **Review pass.** A fresh worker reviews code, design and implementation
   against the PR body **and** the issue/spec.
6. **Validation pass.** Only if review passed. A *separate* fresh worker that
   has **not** seen the review gathers its own evidence (checks out head,
   reruns acceptance tests, exercises each criterion, re-derives numbers) and
   judges whether the builder's evidence matches the spec.
7. **Verdict.** The reviewer-validator submits **one formal review per head
   SHA**: `APPROVE` iff review = pass and validate = pass, else
   `REQUEST_CHANGES` (a clean merge-up after changes gets a merge-up ack
   instead; see [§6](#6-duties-on-wake-all-roles)). **A failed validation pass can never become an APPROVE**:
   the reviewer may not override it, and if the fail looks wrong, it posts
   `REQUEST_CHANGES`, followed by the escalation on round 3, and flags it to the
   coordinator. The body carries the review section, the validation section (or
   "skipped: review failed") and the verdict marker with the round number.
   Label → `crew:approved` or `crew:changes`.
8. **Iterate.** `review-changes-requested` wakes the builder, which relaunches a
   worker on the same branch with the findings. Push → CI → back to step 5. Max
   **3 verdict rounds**; the 3rd `REQUEST_CHANGES` escalates
   ([Rounds and escalation](#5-rounds-and-escalation)).
9. **Merge.** `review-approved` wakes the synthesizer, which checks the gate
   ([Merge gate](#7-merge-gate-synthesizer)) and squash-merges, serially. Then
   it update-branches any other crew PR that is behind but mergeable; PRs with
   real conflicts go to the builder.
10. **Close-out.** `pr-merged` wakes the builder (clean worktree) and the
    coordinator (tick the Project item, unblock dependents, assign the next
    `crew:ready` issue).

## 3. Evidence requirements

**PR body (builder).** Sections from the roles doc: `## Context` with
`Closes #n`, `## Changes Made`, `## Testing Done`, `## Test Output`, signature
last. Plus:

- `## Acceptance Evidence`: one row per acceptance criterion: criterion → how it
  is met → proof (test name + result, command + output excerpt, artifact path,
  or link). "N/A" needs a reason.
- `## Risks / Not Done`: known gaps, follow-ups, deliberate scope cuts.
- A hidden line right before the signature:
  `<!-- crew:v1 role=builder issue=<n> tier=<tier> engine=<engine> model=<model> -->`.
- Write the body once at PR creation. **Never edit it afterwards**: body edits
  rerun some CI workflows and re-wake the reviewer. Later evidence goes in a
  fix-round note.

**Evidence on the PR head.** Any evidence a reviewer's verdict relies on
(screenshots, crops, logs, other artifacts) is committed **on the PR branch**,
so it is in the head commit.

- Never put it on a side branch. Side branches are deleted after merge, which
  broke images in a merged PR body (PR #12 in this repo).
- An evidence-only change committed on the PR branch is a new commit: the head
  moves and CI → `ci-passed` re-wakes review. Only evidence outside the branch
  (a PR-body image, an external link) leaves the head unchanged and wakes
  nobody. In that case the coordinator posts a rereview steer (the
  `steer cmd=rereview` marker); the ack and re-request mechanics are in
  [Steering](#9-steering-crew-commands).
- Lesson record:
  [2026-10-20-evidence-on-pr-head.md](lessons/2026-10-20-evidence-on-pr-head.md).

**Fix-round note (builder, after each push).** A COMMENT review headed
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

**Review section.** Verdict (`pass` / `changes`), findings ranked 🔴 blocking /
🟡 should-fix / 🟢 nit, each with `file:line` and the spec clause or PR claim it
contradicts. Check: does it do what the issue asks, does the design fit the
spec, correctness, do the tests actually cover the criteria, security, scope
creep.

**Validation section.** Per acceptance criterion: builder's claim → validator's
own evidence (command, output excerpt, artifact) → `agrees` / `disagrees` /
`unverified`. `pass` only if every criterion `agrees` (or has a justified N/A)
and no builder claim is contradicted. List what was **not** independently
checked.

## 4. Marker conventions

**Where bots write.** Bots never post plain PR conversation comments or inline
comments (those fire `pr-comment` / `inline-review-comment` and wake the
steering dispatcher for nothing). All bot output goes in **review bodies**:

- A **COMMENT** review for narrative (ack, fix notes, merge-up, merge, cutover,
  escalation, steering acks). The author identity may comment-review its own
  PR. It fires `review-commented` (nobody subscribes) and also `pr-comment`
  (the steering dispatcher no-ops it cheaply).
- The **formal APPROVE / REQUEST_CHANGES** review for verdicts and steering
  signals. Cite `file:line` in the body instead of inline comments.
- **No bot text ever starts with `/crew`**, in any comment, review or commit
  message.

Every bot-authored review body starts with a visible signed header and has a
hidden machine line:

```text
[<BotName>/<pass>] <short status>
...
<!-- crew:v1 role=<role> pass=<pass> pr=<n> sha=<40-char head sha> round=<k> verdict=<pass|changes|n/a> -->
```

In **every** marker, `sha=` is the full 40-character head SHA, never an
abbreviation. `<sha7>` is for human-readable names only (claim files, worktree
names, review headers such as `@ <sha7>`); markers always carry the full SHA.
Readers match markers on the full SHA, so a short SHA is treated as a missing
marker.

`pass` is one of:

- `ack`
- `review`
- `validate`
- `verdict` (the formal review; its body holds the review and validation
  sections, each with its own marker line)
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

The builder's watch status marker (`pass=watch`) states that the per-PR watch B2
is attached. It uses `round=n/a verdict=n/a` and adds `watch=b2
status=attached`:

```text
<!-- crew:v1 role=builder pass=watch pr=<n> sha=<full-40-char-head-sha> round=n/a verdict=n/a watch=b2 status=attached -->
```

It is posted once per PR by the builder's parent turn only, after it has
verified B2 (see [builder duties](#6-duties-on-wake-all-roles)). The builder
routine run never posts it. It is not a round and not a verdict. Because it is
posted once, it is a per-PR fact: its `sha=` is the full SHA of the commit that
was the head when it was posted, and readers accept it for any commit on the PR.

Parse **only** the hidden line (exception: to find a round's actual builder
engine, the fix note and commit trailers also count and win over the marker; see
[roles](roles.md#actual-builder-engine)). Markers are append-only; a newer SHA supersedes.
The per-pass meanings are tabulated in [architecture.md](architecture.md#pass-values).

**Labels** (no listener fires on labels, so they are safe state): `crew:ready`,
`crew:in-review`, `crew:changes`, `crew:approved`, `crew:escalated`, `crew:hold`
(every bot no-ops), `crew:external`, `crew:spec`, `crew:needs-mirror` (a PR
changing `docs/protocol.md` or `templates/`; blocks the merge until the box skill
is mirrored). See
[architecture.md](architecture.md#labels) for who sets and clears each. Never
touch labels or comment commands that belong to the product under development.

## 5. Rounds and escalation

- **Round** = 1 + the number of reviewer-identity formal reviews with marker
  `pass=verdict verdict=changes`, counted after the latest `cutover` or
  `resume` marker. Derived from GitHub each time, never from memory.
- Round 3 ends with `REQUEST_CHANGES` (a failed validation pass counts as one,
  never as an `APPROVE`) → the reviewer-validator adds
  `crew:escalated`, posts a `[<ReviewerBot>/escalation]` COMMENT review (open
  blockers, what was tried, decision needed) and messages the coordinator, who
  brings it to the user.
- A merge-up push uses no round. A merge-up re-approve keeps the round number
  of the approval it renews; a merge-up ack has `round=n/a`. See the
  merge-up rule in [Duties on wake](#6-duties-on-wake-all-roles).
- Builder: ≤3 CI-fix attempts per PR, then the same escalation.
- Any bot waking on a `crew:escalated` or `crew:hold` PR does nothing. Restart
  via `/crew resume` ([Steering](#9-steering-crew-commands)), which resets the
  round count.

## 6. Duties on wake (all roles)

Every wake, in order:

1. **Re-read live state**: current head SHA, labels, reviews, markers, not just
   the payload. If the event SHA ≠ head, or the PR is closed, merged,
   `crew:hold` or `crew:escalated`, stop.
2. **Idempotency.** If a marker for *this pass at this head SHA* exists, stop.
   Otherwise take a claim file
   `<state-dir>/<owner>__<repo>/claims/<role>-pr<n>-<sha7>` atomically
   (`set -o noclobber` or `flock`). If the claim exists and is under 2h old,
   stop. Delete the claim after posting.
3. **Sweep.** Also pick up other PRs in the same state that missed a wake, up
   to the fan-out cap.
4. **Fan out.** One fresh worker per PR or issue, max **5 in parallel per
   role**. Queue the rest. The role bot only briefs, collects results and posts
   markers; no coding in its own chat.
5. **Report.** Post the marker, set labels, update the Project item. Message
   the coordinator only on escalation or blockage.

**Per-PR watches (routine limits).** A routine run cannot create or delete
routines. A listener wake that needs a per-PR watch hands the request off to its
parent bot turn, which creates it. PR-scoped watches that include
`pr-merged` / `pr-closed` delete themselves after that terminal wake, so no
delete handoff is needed.

**The hand-off is verified, not fire-and-forget.** After the builder's parent
turn creates B2 for PR `<n>`, it lists its routines and confirms a watch exists
for PR `<n>` with exactly `ci-failed`, `review-changes-requested`, `pr-merged`
and `pr-closed`. It records the **routine folder id** in the marker file
`<state-dir>/<owner>__<repo>/watches/pr-<n>.b2`, then posts the `pass=watch`
marker on the PR. The folder id is the one identifier both a routine run and
the parent turn can see; a platform watch UUID is not recorded, because the
parent turn's routine `get` returns only the folder id. The builder routine run
(B1) only requests the hand-off; verifying, writing the marker file and posting
the marker belong to the parent turn alone. If it cannot confirm the watch, it
messages `<CoordinatorBot>`. The stuck-PR sweeper also flags a crew PR with no watch
marker (`no-builder-watch`). The reviewer-validator never creates B2.

**Comment reviews do wake comment listeners.** A COMMENT review with a body
fires `pr-comment` for the steering dispatcher (see the
[pilot notes](#worked-example--pilot-notes)). The dispatcher must end such wakes
in one cheap check; keep bot posts few (one per pass).

Further duties:

- **Label hygiene.** Whoever sets `crew:approved` or `crew:changes` (the
  reviewer's verdict pass) removes `crew:in-review` in the same step. The same
  verdict pass adds `crew:needs-mirror` to a PR that changes `docs/protocol.md`
  or `templates/`, and does so **before** posting the formal review, because
  `review-approved` wakes the synthesizer at once and the hold must already
  exist. A re-review skips re-adding the label when the coordinator's mirror
  comment is already on the PR and is newer than the last commit touching
  `docs/protocol.md` or `templates/` (nothing mirrored-relevant changed since the
  mirror); if a later commit changed those paths, it re-adds the label.
- **Box-skill mirror.** When the coordinator posts the box-skill mirror comment
  (for example `[Ash] box skill mirrored`), it removes `crew:needs-mirror` and
  then pings `<SynthesizerBot>`, because label changes don't wake listeners.
  Re-confirm duty: if a later commit changes `docs/protocol.md` or `templates/`
  after the mirror comment, the label is re-added and the coordinator posts a
  fresh mirror comment and removes the label again.
- **Unique worktrees.** Every worker run uses its own directory
  `<worktree-root>/<pr>-<sha7>-<role>-<pass>/` (see the roles doc). Never share
  `<worktree-root>/<branch>` across runs; a mid-pass delete of a shared tree is
  unsafe even if the review falls back to a code trace.
- **Worker toolchain.** Builder and fix workers pin the repo's required
  toolchain (e.g. Node version on `PATH`, `COREPACK_HOME`) before any commit or
  push, so pre-push hooks don't fail on the box's defaults.
- **Default-branch CI.** If the default branch runs CI on push, the
  coordinator's after-merge routine also listens for `ci-failed` with
  `ciBranch` set to the default branch, and files a `crew:ready` fix issue
  instead of touching the default branch.
- **No GitHub Project yet:** skip Project steps rather than blocking.

Role specifics:

- **Builder / `issue-assigned`.** Needs `crew:ready` and no open PR or branch for
  it already. Pick role, tier and engine per the roles doc. After the PR opens:
  label, add to the Project, attach the per-PR watch B2 (`ci-failed`,
  `review-changes-requested`, `pr-merged`, `pr-closed`), verify it, record the
  routine folder id and post the full-SHA `pass=watch` marker (parent turn only).
  - **`review-changes-requested`:** relaunch on the same branch, preferably the
    same engine; post `fix` after pushing.
  - **`ci-failed`:** ignore cancelled or superseded runs; fix real failures on
    head; post `ci-fix`.
  - **Conflicts** handed over by the synthesizer: merge `<default-branch>` in
    with a merge commit, resolve, push.
  - **`pr-merged` / `pr-closed`:** delete the worktree and build output.
- **Reviewer-validator / `pr-opened`.** Post an `ack` COMMENT review, attach the
  per-PR watch (`ci-passed`, `review-requested`, `pr-merged`, `pr-closed`),
  label external PRs `crew:external`. Skip the ack on drafts. When posting its
  first verdict on a crew PR, if no builder `pass=watch` marker (full 40-char SHA of
  any commit on the PR, not only the head) is on the PR, the
  reviewer's parent turn pings `<BuilderBot>` with priority to attach the
  watch and post the marker, and tells `<CoordinatorBot>`. The reviewer never
  creates the builder's watch. The synthesizer also holds the merge until the
  marker is present ([Merge gate](#7-merge-gate-synthesizer)).
  - **`ci-passed`:** review engine ≠ the builder's (the engine that actually
    wrote the round under review; see [roles](roles.md#actual-builder-engine)).
    Review, then validation.
    - **Merge-up push.** A push whose only new commit is a merge of
      `<default-branch>` into the PR branch (GitHub update-branch or a builder
      merge-up) never uses up a review round. Do the light re-check: inspect the
      conflict-resolution hunks, rerun the acceptance checks at the new head,
      confirm CI green. Then:
      - *Clean, last verdict at the previous head was `APPROVE`
        (`verdict=pass`):* post a formal `APPROVE` at the new head with the
        **same round number** as that approval (a **merge-up re-approve**). The
        header is `[<ReviewerBot>/verdict] round <k> (merge-up re-approve)`. The
        body is a normal verdict body: a review section (the hunk check) and a
        validation section (acceptance checks rerun at the new head), each with
        its own marker saying `verdict=pass`, and the final marker
        `<!-- crew:v1 role=reviewer-validator pass=verdict pr=<n> sha=<new-head-sha> round=<k> verdict=pass -->`.
        The re-approve is the single formal review at that head, posted once.
        An `APPROVE` never moves the round count, and it fires `review-approved`
        so the synthesizer wakes normally. Labels stay `crew:approved`.
      - *Clean, last verdict was `REQUEST_CHANGES` (`crew:changes`):* post one
        COMMENT review `[<ReviewerBot>/ack] merge-up @ <sha7>, verdict pending fix`
        with marker
        `<!-- crew:v1 role=reviewer-validator pass=ack pr=<n> sha=<head-sha> round=n/a verdict=n/a -->`.
        No round, no verdict, no label change. The ack is narrative only and
        never counts as an approval anywhere (merge gate, sweeper).
      - *Conflict resolution changes behavior or content (anything beyond a
        mechanical clean merge):* a normal review round: full review and
        validation, a normal verdict, round counted as usual.
  - **`review-requested`** for the reviewer identity with a `steer cmd=rereview`
    marker newer than the last verdict: fresh full review and validation at
    head, even if the head is a merge-up (the merge-up shortcut applies only to
    `ci-passed` wakes).
- **Synthesizer / `review-approved`.** Gate check and merge
  ([Merge gate](#7-merge-gate-synthesizer)). After each merge, sweep open crew
  PRs: behind-but-mergeable ones get GitHub update-branch (post `merge-up`);
  conflicting ones go to the builder by message. Dependent PRs merge in
  `Depends on` order.
- **Coordinator / `pr-merged`.** Update the Project, advance the parent
  sub-spec, label and assign the next unblocked issue. Escalations from others
  arrive as messages.
- **Coordinator / steering dispatcher.** When evidence changes without a new
  head commit, post the rereview steer
  ([Evidence requirements](#3-evidence-requirements)).

## 7. Merge gate (synthesizer)

All of these must hold **at the current head SHA**, re-checked right before
merging:

- A formal `APPROVED` review from the reviewer identity at head carrying
  **either** `pass=verdict verdict=pass sha=<head>` (with review + validate
  sections whose own markers both say `verdict=pass`; an `APPROVE` over a failed
  validate marker does **not** count) **or**
  `pass=steer cmd=merge-ok sha=<head>`. `merge-ok` is the user's override; it
  skips validation and escalation but never CI. Spec PRs merge only on
  `merge-ok`. A COMMENT review (such as a merge-up ack) never satisfies this
  gate; only the formal `APPROVED` review does.
- No later `REQUEST_CHANGES` from the reviewer identity. No `crew:hold` /
  `crew:escalated` (unless `merge-ok`).
- If the builder marker and the fix note or commit trailer disagree on the
  engine, the note or trailer wins, and before merge the reviewer re-checks at
  head (fresh review + validation) on an engine different from the actual
  builder engine. The coordinator posts the rereview steer
  (`steer cmd=rereview`) at head, with the same ack and re-request mechanics as
  the evidence-only rereview in §3 and [Steering](#9-steering-crew-commands).
  Do not merge until that re-check verdict is posted.
- The builder's `pass=watch` marker (`role=builder pass=watch watch=b2
  status=attached`) is on the PR, with `sha=` the full 40-char SHA of **any**
  commit on the PR, not only the head (match on the full SHA, not a prefix; same
  rule as the reviewer cross-check). Three exemptions: external PRs, which have
  no crew builder and so no B2 watch to require; cutover PRs, which predate
  the watch protocol; and coordinator-opened `crew:spec` PRs, which have no crew
  builder and no B2 watch and merge on the user's `/crew merge-ok`. A cutover PR is
  subject to the gate again as soon as its builder posts its
  `[<Builder>/watch]` review or any builder `crew:v1` marker after the cutover
  (by post time), whatever commit it sits on. This includes attaching B2 at the
  unchanged cutover SHA, which needs no new commit. That trigger does not depend
  on the `pass=watch` marker. From then on a valid full-SHA marker (any PR commit) is
  required as usual. If it is missing or malformed, hold the PR: do not merge,
  and ping the builder with priority to attach B2 and post the marker (the
  synthesizer never creates the watch). The merge re-checks once the marker
  appears.
- No `crew:needs-mirror` hold. A PR that changes `docs/protocol.md` or
  `templates/` carries the label from the reviewer's verdict pass (added before
  the formal review) until the coordinator posts the box-skill mirror comment
  and removes it. The synthesizer derives the hold from the changed paths, not
  only the label: if the PR's diff touches `docs/protocol.md` or `templates/`,
  hold the PR unless the label is absent **and** the coordinator's box-skill
  mirror comment exists on the PR and is newer than the last commit touching
  `docs/protocol.md` or `templates/`. While held, do not merge; wait for the
  coordinator's ping (label changes don't wake listeners), then re-check the
  gate.
- All required checks green on head. PR not draft, mergeable, base =
  `<default-branch>`.
- Issue linked (`Closes #n`) unless it is a spec, external or cutover PR; never
  auto-close an umbrella or TRD issue.

Then take the repo merge lock, run
`gh pr merge <n> --squash --match-head-commit <sha>`, post `merge`, and release
the lock. If head moved, stop.

Merge-only-by-synthesizer is **convention** until branch protection requires
review + checks and the synthesizer has its own identity (e.g. a GitHub App)
that alone may merge.

## 8. Safety

- Work roles listen only to state-transition events: `issue-assigned`,
  `pr-opened`, `ci-passed`, `ci-failed`, `review-requested`, `review-approved`,
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
- Only one automation system may own a repo at a time.
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
  assignment, labels (`crew:ready`, `crew:hold`), or chat with the coordinator.

## Worked example / pilot notes

Facts from the agentconnect pilot (`mw-ding/agentconnect`), kept out of the
generic rules above. They illustrate the protocol and do not change it.

- **Comment reviews wake comment listeners (pilot finding, Oct 18, 2026).** A
  COMMENT review with a body fires `pr-comment` for the steering dispatcher.
  This is why the dispatcher ends such wakes in one cheap check and why bots keep
  their posts to one per pass.
- In the pilot, the per-repo wiring doc lived under the shared state dir as
  `mw-ding__agentconnect/wiring.md`, following the
  `<state-dir>/<owner>__<repo>/wiring.md` convention.
