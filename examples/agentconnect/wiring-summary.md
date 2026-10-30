# agentconnect wiring summary (worked example)

Worked example: a summary of the pilot wiring for `mw-ding/agentconnect`
(public repo, default branch `main`). The pilot went live Oct 18, 2026. The
template is [../../templates/runtimes/grok-bot/wiring.md](../../templates/runtimes/grok-bot/wiring.md); the routine
list is [routines.md](routines.md).

## Facts found in the repo (Oct 18, 2026)

- Two GitHub identities: PRs were authored and merged as `mw-ding`, and the
  reviewer's verdicts were posted as `md-mt`. GitHub does not let an account
  approve its own PR, so the reviewer must use the second account. `md-mt` was
  made a write collaborator on Oct 18, 11:15 PM PDT so its reviews are binding.
- The repo is a fork. Upstream syncs have to go through a PR, because the sync
  button and direct pushes to `main` were blocked.
- The product's live E2E opens and merges `[kanban-e2e]` PRs into scratch
  bases. They wake V1, which ignores them.
- CI: an aggregate `CI OK` check and a `Conventional PR` check ran on pull
  requests; `Conventional PR` also reran on PR body or title edits and could
  re-fire `ci-passed`. Neither ran on `ready_for_review`, so a draft turned
  ready got no new CI and no wake. PRs with merge conflicts got no CI.
- The product uses its own `ac/*` labels and `/kanban` comment commands on the
  same repo. The crew uses only `crew:*`.

## Identities

| Bot | Role | GitHub identity |
|---|---|---|
| Ash | Coordinator | `mw-ding`; `md-mt` for project operations and steering signals |
| Ben | Builder | `mw-ding` |
| Vera | Reviewer-validator | `md-mt` for all reviews |
| Sam | Synthesizer | `mw-ding` |
| Riley | Researcher | `mw-ding`, read-only, no listeners |

## Enforcement (applied Oct 18, 2026)

1. `md-mt` added as a write collaborator, about 11:15 PM PDT.
2. `main` protected, about 11:18 PM PDT: required checks `CI OK` and
   `Conventional PR`, one approving review, administrators included, no force
   pushes or deletions. Stale approvals are not dismissed; the synthesizer's
   SHA-bound marker check keeps approvals current.
3. Squash-only merges and delete-branch-on-merge, about 11:28 PM PDT.
4. "Only the synthesizer merges" stayed convention, since `mw-ding` is shared.

## State flow

`issue-assigned` -> build -> `pr-opened` -> V2 watch -> `ci-passed` -> one
formal review -> `review-changes-requested` (builder fix, next round) or
`review-approved` (gate and merge) -> `pr-merged` (cleanup, next issue).

## Steering

Ash's dispatcher fired on every comment on PRs authored by the allowlisted
logins and checked the commenter itself. Rejected alternative: each owner bot
listening per PR, which would wake four bots on every comment. The cost of the
chosen design was one cheap Ash wake per bot post.

## Cutover (Oct 18-19, 2026)

Five open PRs predated the listeners. Watches were backfilled, each PR got a
`cutover` marker, and PRs were kicked in dependency order. One stacked draft
stayed on `crew:hold`.

## Pilot findings

- Oct 18, 2026: a routine run cannot create or delete routines; per-PR watch
  creation is handed to the parent turn. PR-scoped watches self-delete.
- Oct 18, 2026: a bot COMMENT review fired Ash's dispatcher, which no-op'd.
- Oct 18, 2026: the pre-push hook needed the repo's Node version on `PATH`;
  workers now set it first.
- Pilot merged Oct 19, 00:29 PT after 2 rounds with no manual nudges.
- Oct 19, 00:33 PT: `main` has push CI, so A1 also listens for `ci-failed` on
  `main`. Its first wake was a release workflow failing for lack of release
  credentials, a known-noise failure tracked by an issue. That was resolved
  later on Oct 19 by making release workflows manual-only, after which any
  `ci-failed` on `main` is real signal.
- Oct 19, 2026: this repo forbids closing keywords, so `Refs #n` satisfies the
  merge gate and the coordinator closes the issue after merge.
- Oct 19, 2026: label hygiene rule added; the reviewer removes `crew:in-review`
  when adding `crew:approved` or `crew:changes`.
- Oct 19, 2026: the stuck-PR sweeper was added after the bottleneck analysis.

## Open risks recorded

Unverified listener semantics; PR body edits re-waking the reviewer; bot
comment discipline; steering trust (the user's accounts are shared with bots,
so safety rests on bots never writing the steering prefix); draft-to-ready CI
gap; silent conflict stalls; external PRs needing sandboxed validation and
manual workflow approval.
