# Routine and listener templates

One file per routine, each with a `json` trigger block and a prompt block.
Copy a template onto the bot, replace every placeholder, and keep the wiring
doc ([wiring.md](wiring.md)) in sync. These are templates only: nothing here
creates or changes a live routine. For the roles and markers they rely on, see
[../docs/architecture.md](../docs/architecture.md) and the
[docs index](../docs/README.md). A filled-in example is in
[../examples/agentconnect/](../examples/agentconnect/README.md).

## Files

| File | Routines | Owner |
|---|---|---|
| [coordinator-steering-dispatcher.md](coordinator-steering-dispatcher.md) | Steering dispatcher | `<CoordinatorBot>` |
| [coordinator-after-merge.md](coordinator-after-merge.md) | After merge (`pr-merged`, `ci-failed` on `<default-branch>`) | `<CoordinatorBot>` |
| [coordinator-stuck-pr-sweeper.md](coordinator-stuck-pr-sweeper.md) | Stuck-PR sweeper (schedule) | `<CoordinatorBot>` |
| [builder-b1.md](builder-b1.md) | B1 build intake (`issue-assigned`) | `<BuilderBot>` |
| [builder-b2.md](builder-b2.md) | B2 per-PR watch | `<BuilderBot>` |
| [reviewer-validator.md](reviewer-validator.md) | V1 PR intake (`pr-opened`) | `<ReviewerBot>` |
| [reviewer-v2-watch.md](reviewer-v2-watch.md) | V2 per-PR watch | `<ReviewerBot>` |
| [reviewer-engines.md](reviewer-engines.md) | Reviewer engine choice (state file) | `<ReviewerBot>` |
| [synthesizer.md](synthesizer.md) | S1 `review-approved` | `<SynthesizerBot>` |
| [metrics-regression-issue.md](metrics-regression-issue.md) | Issue body for the metrics gate (`harness: latency/quality regression`) | `<CoordinatorBot>` |
| [wiring.md](wiring.md) | Per-repo wiring doc template | all |
| [evidence/README.md](evidence/README.md) | Evidence adapters index: [cli-exit-stdout.md](evidence/cli-exit-stdout.md), [web-screenshot.md](evidence/web-screenshot.md) | `<BuilderBot>`, `<ReviewerBot>` |
| [step-summary.md](step-summary.md) | `summary.md` skeleton for a builder run (see [observe](../docs/observe.md)); not a routine | `<BuilderBot>` |

## Placeholders

| Placeholder | Meaning |
|---|---|
| `<owner>` | GitHub owner of the repo |
| `<repo>` | Repo name |
| `<default-branch>` | The repo's default branch (PR base, merge target, `ciBranch`) |
| `<author-login>` | Author identity: opens branches and PRs, merges. Shared by coordinator, builder, synthesizer |
| `<reviewer-login>` | Reviewer identity: posts formal verdicts and steering signals. Must differ from `<author-login>` |
| `<user-logins>` | The user's own GitHub logins, used as `userAllowlist` and as the accepted commenters for steering. Expands to one JSON string per login |
| `<state-dir>` | Shared state directory on the bot box; per-repo state is `<state-dir>/<owner>__<repo>/` (claims, locks, wiring, sweeper state) |
| `<CoordinatorBot>` | Name of the coordinator bot (also the steering dispatcher) |
| `<BuilderBot>` | Name of the builder bot |
| `<ReviewerBot>` | Name of the reviewer-validator bot |
| `<SynthesizerBot>` | Name of the synthesizer bot |
| `<n>` | A PR or issue number. In a trigger it is a JSON number once filled in |
| `<sha7>` / `<head-sha>` | Short or full 40-character head commit SHA |
| `<k>` | Verdict round number, starting at 1 |
| `<pass>` | Review pass name, used in worktree names (for example `review`, `validate`) |
| `<role>` | Role short name, used in worktree names |
| `<worktree-root>` | Directory holding per-run worktrees; each run uses its own `<worktree-root>/<n>-<sha7>-<role>-<pass>/` |
| `<pass\|changes>` | Verdict value in a marker: `pass` or `changes` |
| `<cmd>` | A steering command name |
| `<comment id>` | ID of the PR comment that carried a steering command (`cmd-id` in the marker) |
| `<note>` | Free-text note after a steering command such as `rework` |
| `<fallback-engine>` | Second allowed engine for the reviewer fallback (private repos: Claude Code or Codex only) |
| `<planned \| applied \| live>` | Status of a wiring step; pick one and add a date |
| `<timezone>` | IANA timezone for a schedule trigger |
| `<toolchain-bin>` | Directory of the repo's required toolchain, put on `PATH` before any commit or push |
| `<parent>` | Number of the parent spec issue |
| `<date>`, `<reason>` | Date and reason recorded in a state file (for example a quota steer) |

Quoted placeholders such as `"<n>"` in JSON blocks keep the template valid
JSON. Replace the whole quoted string with a number when filling it in.

## Event to consuming role

Each event has exactly one consuming role, with one narrow exception (stated in
[the protocol, section 8](../docs/protocol.md#8-safety)): PR-scoped `pr-merged`
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

Lighter-lane PRs touch only docs, with no code, no `.github/`, no `templates/`
and no `docs/protocol.md`, judged from the full diff at head. They install no
B2, post no `pass=watch` and never get `crew:needs-mirror`. The reviewer's
verdict-pass parent turn messages `<BuilderBot>` on `REQUEST_CHANGES` with PR,
head SHA and findings link; the sweeper's changes-requested row is a backstop.
The sweeper's CI-failed row or a direct coordinator message routes red CI
(no lighter-lane `ci-failed` listener fires). The coordinator messages the
builder for merge/close cleanup. If a fix leaves the lane, the builder attaches
B2 using the verified hand-off.

## Open items

None.

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

## Credentials

Templates refer to credentials only by mechanism, for example
`GH_TOKEN=$(gh auth token --user <author-login>)`. Never paste a token, key or
header into a template or a wiring doc.
