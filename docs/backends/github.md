# GitHub backend

How the GitHub backend expresses the core rules in
[protocol.md](../protocol.md) (portable eng-crew, roadmap 13.3,
[#115](https://github.com/mw-ding/eng-crew/issues/115)). GitHub is today's
backend for every concern ([concepts: backend](../concepts.md#backend)). The
core states each rule; this page states the GitHub mechanics for it. Neither
page changes a rule, gate, cap, marker field or label. Tracking, labels and
issue linkage move here in 13.4
([#116](https://github.com/mw-ding/eng-crew/issues/116)).

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
