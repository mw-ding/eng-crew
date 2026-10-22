# Roles, tiers and engines

> **Source of truth note.** The box skill `eng-crew-roles` is the **live** copy
> the bots load. This file is the **reviewed** copy. Any change to one must be
> mirrored to the other in the same change (spec requirement R4). This file
> holds no secrets: engines authenticate through environment variables, and only
> the variable **names** appear here (R1).

This page covers the short-lived engineering workers: which role and tier a task
gets, which engine runs it, how workers are isolated, and what a worker brief
and PR look like. The stage protocol (events, rounds, merge gate) is out of
scope here. See the [architecture overview](architecture.md) and the
[docs index](README.md).

Placeholders used below: `<owner>/<repo>`, `<issue#>`, `<pr>`, `<sha7>`,
`<role>`, `<tier>`, `<engine>`, `<model>`, `<effort>`, `<default-branch>`,
`<author-login>`.

The lead (the coordinator or builder role bot) keeps the plan and the board.
Workers build. An independent reviewer bot judges, and a synthesizer bot merges.
Workers are fire-and-forget: one task, one branch, one PR, then they report back
and are done.

## Roles

Pick the role by the area the change lives in.

| Role | Area |
|---|---|
| `eng-backend` | Libraries, CLIs, services, APIs, databases, server-side logic, and their tests. Docs-only work also fits here. |
| `eng-web` | Frontends and apps, UI components, client state, and frontend tests (unit, integration, E2E). |
| `eng-infra` | CI/CD, Docker and containers, releases and packaging, dependency bumps, cloud, monitoring, access control, infrastructure-as-code. Infra work touching security or releases is **always deep tier**. |

**Cross-area work is split.** Create one sub-issue per role, and give each its
own worker and PR. A worker stays in its own area and flags cross-area needs in
its report instead of doing them.

## Tiers

Pick the tier by difficulty. The tier sets how much planning the worker does and
its reasoning effort.

| Tier | Work | Approach | Effort |
|---|---|---|---|
| trivial | Mechanical work: small patches, config, lint, docs, test fixes | No planning or exploration | low |
| default | Features, bug fixes, tests, moderate refactors | Brief plan, then execute | medium |
| deep | Root-cause investigations, complex refactors or migrations, performance, security | Understand the problem deeply before changing anything | high |

## Engines and fallback order

Use the first engine in the row that has quota (see [Quota routing](#quota-routing))
and fall through in order. A worker that falls back records the engine it
actually used in its signature, commit trailer and builder marker.

### Current routing

*Dated table, current as of Oct 17, 2026.* Engine and model names change often.
Update this table in place without rewriting the rules around it.

| Tier | 1st | 2nd | 3rd | Last resort (pay-per-use) |
|---|---|---|---|---|
| trivial | Muse Code (`muse exec`), low effort (**skip on private repos**) | Claude Code `sonnet` (Sonnet 5.5), low effort | Codex `gpt-6.1-sol`, low | OpenCode + DeepSeek `deepseek/deepseek-v4-pro`, then Codex `-p openrouter` |
| default | Codex `gpt-6.1-sol`, medium | Claude Code `sonnet`, medium | Muse Code, medium (public repos only) | OpenCode + DeepSeek `deepseek/deepseek-v4-pro` (or Codex `-p deepseek`), then Codex `-p openrouter` |
| deep / risky | Codex `gpt-6.1-sol`, **high** | Claude Code `sonnet`, high | Muse Code, high (public repos only) | OpenCode + DeepSeek `deepseek/deepseek-v4-pro` (or Codex `-p deepseek`), then Codex `-p openrouter` |

Policy behind the table (owner rule, Oct 17, 2026): Codex `gpt-6.1-sol` is
primary for all major build work, Claude Code `sonnet` is the first fallback,
and Muse Code is the second. Trivial work starts on Muse Code only because it is
cheap and public-only.

Research and coding experiments: Codex `gpt-6.1-sol` high, then Claude Code
`opus` high, then OpenCode + DeepSeek `deepseek/deepseek-v4-pro`.

### Hard rules

- **Eng workers never use Cursor CLI**, at any tier, even when every other
  subscription is exhausted. This covers builders, reviewers, validators and
  researchers' coding runs. Cursor quota is reserved for another bot's own use
  (Oct 16–17, 2026). Queue the work and tell the lead instead.
- **Contributor-tier and free-credit engines never run on private repos.** Muse
  Code runs on free credits that the vendor may use for training and product
  improvement, so keep it off private repos entirely. Trivial private-repo work
  goes straight to Claude Code `sonnet`. Keep any contributor-tier model off
  private repos too.
- **Pay-per-use only as a last resort.** Muse Code via API key, DeepSeek, and
  OpenRouter via Codex profile files spend real money. DeepSeek and OpenRouter
  via Codex also carry about 70k tokens of overhead per run. Use them only after
  every subscription ahead of them is exhausted, and **say so in the report**.
- **Cursor models only.** Cursor's included usage covers only Cursor models
  (Composer, Grok, Auto). Claude or GPT inside Cursor needs paid credits, so
  never pick them without the owner's OK.

### How to run each engine

| Engine | Command shape | Auth (env var name only) |
|---|---|---|
| Codex | `codex exec -m <model> -c model_reasoning_effort=<level> ... </dev/null` (or `-p <profile>`; add `-s read-only` for review runs) | Codex login or profile file |
| Claude Code | `claude -p --model <alias>` | Claude Code login |
| Muse Code | `muse exec --reasoning-effort <low\|medium\|high\|ultra> "<prompt>" </dev/null` | `META_API_KEY` |
| OpenCode | `cd <repo> && OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER=1 opencode run -m deepseek/deepseek-v4-pro "<prompt>" </dev/null` (built-in `deepseek` provider) | `DEEPSEEK_API_KEY` (without it the run hangs) |

Always close stdin with `</dev/null` for non-interactive runs.

## Reviewer engine selection

**The reviewer engine must differ from the builder engine.** The builder engine
is the engine that actually wrote the round under review (see
[Actual builder engine](#actual-builder-engine)). If it is unknown, treat it as
non-Claude.

| Builder engine | Reviewer engine |
|---|---|
| Codex | Muse Code `muse exec "<prompt>" </dev/null --reasoning-effort ultra` (public repos only), or Claude Code when it has room (`opus` high, else `sonnet` high). |
| Claude Code or Muse Code | Codex `gpt-6.1-sol`, high. |
| Any, private repo | Never Muse. Codex-built PRs get Claude Code, and the rest get Codex. |
| Any, nothing else available | OpenCode + DeepSeek `deepseek/deepseek-v4-pro` (last resort). Cursor is never an option. |

### Actual builder engine

A round's builder engine is the engine that **actually wrote that round's
commits**, not the engine that was planned, briefed or named in the PR body.
The round under review is every builder commit pushed since the previous verdict
(before the first verdict: everything in the PR). A fix or ci-fix note's
`round=<k>` is the number of the verdict round the fix answers, so the first fix
after a round-1 `REQUEST_CHANGES` is `[<BuilderBot>/fix] round 1`. A ci-fix pushed before any verdict uses `round=1`,
the round its commits will be reviewed in. A rereview at
the same head keeps the commit range and engine attribution of the verdict it
re-checks.

Three places name it, each with engine, model and effort (for example
`codex gpt-6.1-sol medium` or `claude-code sonnet medium`):

1. **The fix note.** The `[<BuilderBot>/fix] round <k> @ <sha7>` COMMENT review
   (for round 1, the PR body signature).
2. **The commit trailer** on every commit of that round:
   `Engine: <engine> <model> <effort>`. A pure merge-up commit says
   `Engine: none (pure merge-up, plain git)` and does not count as a round's
   builder engine.
3. **The `crew:v1` builder marker.** Round 1: the PR-body line
   `<!-- crew:v1 role=builder issue=<n> tier=<tier> engine=<engine> model=<model> -->`.
   A fix round: the fix note's hidden line, which also carries the engine:
   `<!-- crew:v1 role=builder pass=fix pr=<n> sha=<head-sha> round=<k> verdict=n/a engine=<engine> model=<model> effort=<effort> -->`
   (same for `pass=ci-fix`).

The round-1 PR-body marker keeps its existing format (engine and model only);
effort for round 1 is in the signature and the trailers.

Rules:

- If a worker falls back mid-round (for example Claude Code hits a limit and
  Codex finishes), the round names the engine that wrote the commits. If two
  engines wrote commits in one round, name both. The reviewer must then differ
  from both.
- The reviewer-validator picks the reviewer engine from the actual builder
  engine of the round under review, read from that round's fix note, commit
  trailers or marker.
- **Precedence and re-check:** If the builder marker and the fix note or commit
  trailer disagree on the engine, the note or trailer wins, and before merge the
  reviewer re-checks at head (fresh review + validation) on an engine different
  from the actual builder engine. The coordinator posts the rereview steer
  (`steer cmd=rereview`) at head, with the same ack and re-request mechanics as
  the evidence-only rereview in
  [protocol §3](protocol.md#3-evidence-requirements) and
  [Steering](protocol.md#9-steering-crew-commands). The synthesizer must not
  merge until that re-check verdict is posted.

### Related rules

- The validation pass uses the same engine family as the review pass but a
  **fresh session** that has not seen the review output.
- Small merge-up or docs-only re-checks: keep to one light pass to save quota.
- The reviewer's current choice lives in a per-repo file edited only by the
  reviewer's main chat. See the example in the next section.

## Quota routing

Check quota **before each launch**.

- **Skip a subscription** when it is under **15%** of its short window (session
  or 5-hour) or under **10%** of its weekly or monthly limit.
- **Mid-task limit:** if a worker hits a limit part-way through, relaunch the
  next engine in the row **on the same branch**. The new worker continues from
  the pushed commits.
- Quota can also be steered by a person. A steer re-orders the engines for a
  period, but it never overrides the hard rules above.

### Example: a quota steer on the reviewer side

On Oct 19, 2026 the Codex weekly quota was at 38% until Oct 24 while Claude Code
was about 99% free. The reviewer's engine file was updated to prefer Claude Code
as the first choice:

- Builder = Codex (or unknown or other non-Claude): Claude Code Opus (high).
  Fallback: Muse Code with `--reasoning-effort ultra` (`xhigh` if ultra is
  gated). Public repos only.
- Builder = Claude Code (any model): Codex `codex exec -s read-only`
  (`gpt-6.1-sol`, high). Fallback when Codex is rate-limited: Muse Code as
  above. **Do not wait** for the limit to reset.
- Never Cursor or Grok. Skip OpenRouter and DeepSeek.

Lesson (Oct 19, 2026): route by quota. Claude-first while Codex weekly is low
kept reviews moving without breaking the different-engine rule.

## Worker isolation (worktrees)

- **Unique worktree per run:** `/workspace/wt/<pr>-<sha7>-<role>-<pass>/`, for
  example `414-fc778cd-reviewer-review`. Use your own clone or worktree, never a
  shared checkout.
- **Never a branch-named shared path** such as `/workspace/wt/<branch>`. Reusing
  one lets a stale or concurrent run delete the tree mid-pass. This happened
  once: a shared worktree was deleted during a run.
- **Cleanup:** delete **that run's** worktree and its build output (for example
  Rust `target/`) when the pass finishes. Delete leftovers again on
  `pr-merged` and `pr-closed`. Never delete another run's directory. Disk on the
  shared machine is limited.
- **Toolchain pinning:** before any commit or push, pin the toolchain the repo
  expects (for example set `PATH` to the pinned Node and `COREPACK_HOME`) and
  select the credential for the author identity with
  `GH_TOKEN=$(gh auth token --user <author-login>)`. Do not switch the machine's
  logged-in account.

## Worker brief template

Give each worker the complete brief. Copy, then fill every placeholder.

````markdown
# Worker brief: <repo> issue #<issue#>

- Role: <role>. Tier: <tier> (<effort> effort).
- Engine and model: <engine> / <model>. Name the engine, model and effort you
  actually ran as (including any fallback) in the PR signature or fix note, in
  an `Engine: <engine> <model> <effort>` trailer on every commit, and in the
  `crew:v1` builder marker.
- Repo: <owner>/<repo>. Base branch: <default-branch>.
- Your worktree: /workspace/wt/<pr>-<sha7>-<role>-<pass>/ (unique to this run).
  Work only there. Delete it and its build output when you finish.
- Branch: <role>/<issue#>-<short-slug>. For review feedback on an existing PR,
  push to that PR's branch.
- Issue: <issue URL>

## Issue body

<paste the full issue body>

## Review feedback to address (if any)

<paste the review, or write "none">

## Acceptance criteria

<numbered, testable criteria from the issue>

## Rules

- Stay in your role's area. Flag cross-area needs in the report.
- Follow the repo's commit-message convention (check `git log`).
- Run the relevant tests and build before declaring done.
- Open a non-draft PR with `gh pr create`, never `--fill`, using the PR
  conventions below.
- Never merge, never approve your own work, never force-push a shared branch.
- Do not scope-creep. Note deeper problems in the report and stop. If the task is
  ambiguous, flag it instead of guessing.

## Report (final message)

PR URL and number, head SHA, summary of changes, test results, the engine and
model and effort actually used (including any fallback), and follow-ups or ambiguities. Then exit.
````

## PR conventions

- **Branch:** `<role>/<issue#>-<short-slug>`, for example
  `infra/187-align-rust-base-images`. Lead and synthesizer tooling route
  follow-ups by this prefix.
- **Commits:** follow the repo's existing commit-message convention. End every
  commit with the trailer `Engine: <engine> <model> <effort>` naming the engine
  that actually wrote it (see [Actual builder engine](#actual-builder-engine)).
- **Tests first:** run the relevant tests and build before declaring done. For
  infra changes, confirm they are safe before anything is applied.
- **PR:** `gh pr create` with a detailed body, never `--fill`. Add the PR to the
  project board if there is one, and link the issue.
- **Never** merge, approve your own work, or force-push a shared branch.

### PR body template

The signature must be the last thing in the body, with nothing after it. Use the
real values actually used, including any fallback, never placeholders.

```markdown
## Context

<why this change is needed>

Closes #<issue#>

## Changes Made

- `<path>`: <what changed and why>

## Testing Done

- <each test, and the scenario it confirms>

## Test Output

<relevant run output>

---
*Built by <role>-<tier> (<engine>, <model>, <effort>)*
```

Crew PRs must carry the hidden `crew:v1` builder marker line right before the
signature, as described in the [architecture overview](architecture.md). See the
[stage protocol](protocol.md) for the other crew additions: `## Acceptance Evidence`
and `## Risks / Not Done`.

## Parallelism

Soft ceilings (set Oct 15, 2026). Queue work past them.

| Activity | Limit | Notes |
|---|---|---|
| Builders | up to **5** concurrent sessions | Each has its own worktree, branch and PR. |
| Reviews | up to **5** concurrent sessions | **Fan out by default:** one review session per waiting PR, each with one engine, one PR and one verdict. |
| Merge | **serial only** | The synthesizer takes one approved PR at a time, so branch races, squash order and board updates stay clean. |

After the PR opens, the reviewer reviews automatically. If it requests changes,
the lead relaunches the same role on the same branch with the review attached.
If it approves, the synthesizer merges under the merge policy. Event-driven
detail belongs to the stage protocol.
