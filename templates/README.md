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
| [intake-candidate.md](intake-candidate.md) | Self-improve intake candidate card (issue body) | `<CoordinatorBot>` |
| [builder-b1.md](builder-b1.md) | B1 build intake (`issue-assigned`) | `<BuilderBot>` |
| [builder-b2.md](builder-b2.md) | B2 per-PR watch | `<BuilderBot>` |
| [reviewer-validator.md](reviewer-validator.md) | V1 PR intake (`pr-opened`) | `<ReviewerBot>` |
| [reviewer-v2-watch.md](reviewer-v2-watch.md) | V2 per-PR watch | `<ReviewerBot>` |
| [reviewer-engines.md](reviewer-engines.md) | Reviewer engine choice (state file) | `<ReviewerBot>` |
| [synthesizer.md](synthesizer.md) | S1 `review-approved` | `<SynthesizerBot>` |
| [metrics-regression-issue.md](metrics-regression-issue.md) | Issue body for the metrics gate (`harness: latency/quality regression`) | `<CoordinatorBot>` |
| [product-readme.md](product-readme.md) | Seed `README.md` for a product or prove-it repo (problem, what it is, how to run, how the crew works, status); not a routine | `<CoordinatorBot>`, `<BuilderBot>` |
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

Grok Bot runtime: see
[wake wiring](../docs/runtimes/grok-bot.md#wake-wiring-event-to-consuming-role)
and [lighter-lane routing](../docs/runtimes/grok-bot.md#lighter-lane-routing).

## Open items

None.

## Routine limits

Grok Bot runtime: see [routine limits](../docs/runtimes/grok-bot.md#routine-limits).

## Credentials

Templates refer to credentials only by mechanism, for example
`GH_TOKEN=$(gh auth token --user <author-login>)`. Never paste a token, key or
header into a template or a wiring doc.
