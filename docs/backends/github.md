# GitHub backend

How the GitHub backend expresses the core rules in
[protocol.md](../protocol.md) (portable eng-crew, roadmap 13.3,
[#115](https://github.com/mw-ding/eng-crew/issues/115), and 13.4,
[#116](https://github.com/mw-ding/eng-crew/issues/116)). GitHub is today's
backend for every concern ([concepts: backend](../concepts.md#backend)). The
core states each rule; this page states the GitHub mechanics for it. Neither
page changes a rule, gate, cap, marker field or label.

## Reviews, markers and identities

### Identities

The crew uses two GitHub accounts
([architecture: Identities](../architecture.md#identities)):

- **Author identity** (`<author-login>`): coordinator, researcher, builder and
  synthesizer. It opens branches and PRs, posts narrative and lands.
- **Reviewer identity** (`<reviewer-login>`): the reviewer-validator's verdicts,
  and the coordinator's steering signals.

**Why the reviewer identity must differ from the PR author.** GitHub refuses
`APPROVE` and `REQUEST_CHANGES` reviews from a PR's author. A separate reviewer
account keeps the formal verdict accepted and from a different party than the
author (invariant I1, [portable spec §3](../specs/portable.md#3-invariants)).
Roadmap PRs under the single-identity rule post verdicts as COMMENT reviews
instead ([portable spec §6](../specs/portable.md#6-decisions)).

**Selecting the identity.** Each `gh` call picks its account through the
token, for example `GH_TOKEN=$(gh auth token --user <author-login>)`, or
`--user <reviewer-login>` for verdicts and steering signals. Never switch the
machine's logged-in account.

**Shared accounts.** Several bots share each account, so GitHub actor filters
cannot tell bots apart. The core rule applies: a bot action's identity comes
from its signed marker ([protocol §4](../protocol.md#4-marker-conventions)).

### Review types and the events they fire

Bots never post plain PR conversation comments or inline comments. Those fire
`pr-comment` / `inline-review-comment` and wake the steering dispatcher for
nothing. All bot output goes in review bodies:

| Core post | GitHub form | Events it fires |
|---|---|---|
| Narrative post (ack, fix notes, merge-up, merge, cutover, escalation, steering acks) | **COMMENT** review. The author identity may comment-review its own PR | `review-commented` (nobody subscribes) and also `pr-comment` (the steering dispatcher no-ops it cheaply) |
| Verdict or steering signal | **Formal** `APPROVE` / `REQUEST_CHANGES` review. Cite `file:line` in the body instead of inline comments | `review-approved` / `review-changes-requested` |
| Never by a bot | Plain PR conversation comment or inline comment | `pr-comment` / `inline-review-comment` |

### Markers

The signed header is the first line of the review body, and the hidden
`crew:v1` line is an HTML comment in the same body, so it does not render. The
marker format itself is core ([protocol §4](../protocol.md#4-marker-conventions)).

### Land and merge-up

- **Land:** `gh pr merge <n> --squash --match-head-commit <sha>` with the
  author identity. `--match-head-commit` makes GitHub refuse the merge if the
  head moved after the gate check
  ([protocol §7](../protocol.md#7-merge-gate-synthesizer)).
- **Merge-up:** GitHub update-branch (a merge commit, never a rebase) for a PR
  that is behind but mergeable, or a builder merge commit.

## Tracking

### Labels

Each state tag is a GitHub label in the `crew:*` namespace. These are the ten
labels. What each means and who sets and clears it is the role view in
[architecture: Labels](../architecture.md#labels); the commands that create
them are in [runbook Step 1](../runbook-new-repo.md#step-1-create-the-crew-labels).

| Label | Colour | GitHub description |
|---|---|---|
| `crew:ready` | `0E8A16` | Released to the builder; issue may be assigned and built |
| `crew:in-review` | `1D76DB` | PR open, awaiting CI + review/validation |
| `crew:changes` | `D93F0B` | Reviewer requested changes; builder fix round due |
| `crew:approved` | `5319E7` | Reviewer approved at head; synthesizer may merge |
| `crew:escalated` | `B60205` | Round/CI-fix cap hit or escalated; bots no-op until /crew resume |
| `crew:hold` | `FBCA04` | Paused: every bot no-ops on this item |
| `crew:external` | `C5DEF5` | External/fork PR: sandboxed validation, no tokens |
| `crew:spec` | `0052CC` | Spec PR: review pass only, merges on /crew merge-ok |
| `crew:needs-md` | `F9D0C4` | Blocked on an owner decision (recommended default + deadline) |
| `crew:needs-mirror` | `E99695` | Protocol/template change: merge blocked until the box skill is mirrored |

**No listener fires on labels.** No crew routine subscribes to a label
event, so labels are safe state: setting or clearing one wakes nobody. A role
that clears a label another role waits on pings that role by message, for
example the coordinator pings `<SynthesizerBot>` after removing
`crew:needs-mirror` ([protocol §6](../protocol.md#6-duties-on-wake-all-roles)).
Roles read labels when they re-read live state on a wake.

### Milestones and board

The tracker is GitHub issues, Milestones and a Project (v2) board
([protocol §6](../protocol.md#6-duties-on-wake-all-roles), Repo tracking).
Setup commands are in
[runbook Step 3](../runbook-new-repo.md#step-3-create-milestones-and-link-a-github-project-v2).

- **Milestones** are named `M1`, `M2`, …. Each issue goes to an open `M*`. A
  closed milestone is frozen: no new issues; follow-ups go to the next `M*`.
- **Project (v2) board** with a Status field of exactly Todo, In Progress, In
  Review and Done. The coordinator adds issues and keeps item status current
  (Todo for new issues, In Progress while a PR is built, In Review while it is
  under review, Done after merge). The builder adds its PR by hand. Board
  auto-add and status workflows must not conflict with that; a built-in "item
  closed" → Done workflow is fine.

### Linkage

- **PR to issue.** The PR body's `## Context` carries `Closes #<n>`, so the
  squash merge closes the issue. If the repo forbids closing keywords, the
  builder writes `Refs #<n>`; that satisfies the linked-issue gate and the
  coordinator closes the issue after merge
  ([protocol §7](../protocol.md#7-merge-gate-synthesizer),
  [runbook Step 5](../runbook-new-repo.md#step-5-product-safety-checks)).
  Spec, external and cutover PRs are exempt.
- **Umbrella and TRD issues are never auto-closed.** A child issue says
  `Part of #<n>` for its umbrella, never a closing keyword.
- **Dependencies.** An issue body lists `Depends on #<n>`; dependent PRs merge
  in that order ([protocol §6](../protocol.md#6-duties-on-wake-all-roles)).

### Steering limits

`/crew` commands arrive as PR conversation comments or inline review comments,
which fire `pr-comment` / `inline-review-comment` for the steering dispatcher
([protocol §9](../protocol.md#9-steering-crew-commands)). There is no
issue-comment event, so **issues cannot be steered by comment**. Steer an issue
with assignment (`issue-assigned` wakes the builder), labels (`crew:ready`,
`crew:hold`), or chat with the coordinator.

## Interface mapping

How GitHub implements each operation of the
[backend interfaces](../interfaces.md) (roadmap 13.9,
[#121](https://github.com/mw-ding/eng-crew/issues/121)). `<o>/<r>` is
`<owner>/<repo>`. Every call runs under the identity named in
[Identities](#identities): the reviewer identity for verdicts and steering
signals, the author identity for everything else.

| Concern | Operation | `gh` command or API call |
|---|---|---|
| change | Open, linked to an item | `gh pr create --base <default-branch> --head <branch> --title <t> --body-file <f>`, body with `Closes #<n>` ([Linkage](#linkage)) |
| change | Push | `git push origin <branch>` (never `--force`) |
| change | Read head | `gh pr view <n> --json headRefOid -q .headRefOid` |
| change | Read diff paths | `gh pr diff <n> --name-only` |
| change | Update from base | `gh pr update-branch <n>` (merge; never `--rebase`), or `git merge origin/<default-branch>` and push |
| change | Land | `gh pr merge <n> --squash --match-head-commit <sha>` |
| change | Close | `gh pr close <n>` |
| review | Post verdict pinned to head | `gh api repos/<o>/<r>/pulls/<n>/reviews -f commit_id=<sha> -f event=APPROVE` (or `REQUEST_CHANGES`) `-F body=@<f>` |
| review | Post narrative | `gh pr review <n> --comment --body-file <f>` |
| review | List verdicts | `gh api --paginate repos/<o>/<r>/pulls/<n>/reviews`: `user.login`, `state`, `commit_id`, `body`, `submitted_at` |
| review | Request re-review | `gh pr edit <n> --add-reviewer <reviewer-login>` |
| tracker | Create item | `gh issue create --title <t> --body-file <f> --milestone <M>` |
| tracker | Assign | `gh issue edit <n> --add-assignee <login>` |
| tracker | Link change ↔ item | `Closes #<n>` in the PR body; read with `gh pr view <n> --json closingIssuesReferences` |
| tracker | Milestone | `gh issue edit <n> --milestone <M>`; read with `gh issue view <n> --json milestone` |
| tracker | Board status | `gh project item-add <project> --owner <owner> --url <url>`, then `gh project item-edit --project-id <id> --id <item> --field-id <status-field> --single-select-option-id <option>` |
| state tags | Set / clear / read | `gh issue edit <n>` or `gh pr edit <n>` with `--add-label` / `--remove-label crew:<tag>`; read with `gh pr view <n> --json labels` ([Labels](#labels)) |
| markers | Write | In the body of a narrative post or verdict (rows above); the `crew:v1` line is an HTML comment ([Markers](#markers)). Never edit a posted review |
| markers | Read | List verdicts (above) and parse each `body`; the builder marker from `gh pr view <n> --json body` |
| CI | Required-check status at head | `gh pr checks <n> --required --json name,state,link`, after confirming the head SHA |
| CI | Failing job names | `gh pr checks <n> --json name,state,link`, then `gh run view <run-id> --log-failed` |
| events | Subscribe or poll | Webhooks: `issues` assigned, `pull_request` opened / review_requested / closed (merged or not), `check_suite` completed, `pull_request_review` submitted, `issue_comment` and `pull_request_review_comment` for steering; on Grok Bot, routine triggers ([wake wiring](../runtimes/grok-bot.md#wake-wiring-event-to-consuming-role)). Poll: `gh api repos/<o>/<r>/issues/events` plus the reads above |
| owner channel | Ask with default and deadline | Asked over the runtime's owner channel ([C8](../runtimes/README.md#c8-owner-channel-and-sla)), recorded with `gh issue edit <n> --add-label crew:needs-md` and `gh pr review <n> --comment --body-file <f>` (default and deadline); the answer is recorded as a `steer` post the same way |
| owner channel | Notify | Sent over the runtime's owner channel; recorded with `gh pr review <n> --comment --body-file <f>` (or `gh issue comment <n> --body-file <f>` on an issue) |

**Capability declaration.** With two identities, every operation is
`supported`. With one account for all roles, GitHub refuses formal verdicts
from the PR author, so `review.post verdict` is
`emulated (COMMENT-review verdict + recorded owner merge-ok)`, posted with
`gh pr review <n> --comment`; see
[interfaces: Single-identity profile](../interfaces.md#single-identity-profile).
