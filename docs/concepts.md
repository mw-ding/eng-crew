# Concepts

Shared vocabulary for the abstract protocol (portable eng-crew, roadmap 13.1,
[#113](https://github.com/mw-ding/eng-crew/issues/113)). Later M13 changes use
these terms when they split the core from its bindings. Each entry gives the
definition, the invariant it touches, and today's mapping to GitHub and Grok
Bot.

This page defines terms only. It changes no rule, gate, cap, marker field or
label. Where a term and an existing doc disagree, the existing doc wins until
a later roadmap PR moves the rule. Invariants are numbered as in
[portable spec §3](specs/portable.md#3-invariants): I1 author ≠ reviewer, I2
reviewer engine ≠ writing engine, I3 evidence on the change record, validated at head, I4 only the
synthesizer lands, I5 the tool of record holds the audit trail.

## Terms

### change

- **Definition:** one reviewable unit of work that builds one tracker item and
  lands as one commit on the default branch.
- **Invariants:** I4, I5.
- **Today:** a PR. One issue → one branch → one PR → one squash.

### change head

- **Definition:** the exact revision of a change that evidence, verdicts and
  the land refer to. A new commit makes a new head.
- **Invariants:** I3.
- **Today:** the PR head SHA. Markers carry it as the full 40-character `sha=`.

### verdict

- **Definition:** the reviewer's binding decision on a change head: pass or
  changes requested.
- **Invariants:** I1, I2, I3.
- **Today:** a formal `APPROVE` / `REQUEST_CHANGES` review carrying a
  `pass=verdict` marker. Roadmap PRs under the single-identity rule use a
  COMMENT review with a `pass=verdict` marker instead
  ([portable spec §6](specs/portable.md#6-decisions)).

### narrative post

- **Definition:** a non-binding bot post on a change: ack, fix note, merge-up,
  merge, escalation, steering ack.
- **Invariants:** I5.
- **Today:** a COMMENT review. Never a plain PR comment or inline comment.

### state tag

- **Definition:** a durable flag on a tracker item or change that records
  pipeline state without waking any role.
- **Invariants:** I5.
- **Today:** a `crew:*` label ([architecture: Labels](architecture.md#labels),
  [GitHub backend: Labels](backends/github.md#labels)).

### marker

- **Definition:** the machine-readable identity of a bot post: who wrote it,
  which pass, which change, which head, which round, which verdict.
- **Invariants:** I1, I3, I5.
- **Today:** a visible signed header `[<BotName>/<pass>]` plus a hidden
  `crew:v1` line ([protocol §4](protocol.md#4-marker-conventions)).

### CI signal

- **Definition:** the pass or fail result of the required automated checks at
  a change head.
- **Invariants:** I3.
- **Today:** the required GitHub Actions checks at head, surfaced to routines
  as `ci-passed` / `ci-failed`.

### wake event

- **Definition:** an external event that starts a role's turn.
- **Invariants:** none directly; it only decides who acts next.
- **Today:** a Grok Bot routine trigger on a GitHub event (`issue-assigned`,
  `pr-opened`, ...; see [templates](../templates/README.md)).

### tracker item / milestone / board

- **Definition:** the unit of planned work, a group of items with a shared
  goal, and the view of their status.
- **Invariants:** I5.
- **Today:** a GitHub issue, Milestone and Project (v2)
  ([GitHub backend: Tracking](backends/github.md#tracking)).

### owner channel

- **Definition:** where the owner steers the crew and is asked for decisions.
- **Invariants:** I5 (a decision only counts once recorded on the tool of
  record).
- **Today:** chat with the coordinator, plus the matching GitHub post
  (`/crew` command or recorded steer).

### land

- **Definition:** integrating a change into the default branch, bound to the
  change head the gate checked.
- **Invariants:** I3, I4.
- **Today:** `gh pr merge --squash --match-head-commit <sha>` by the
  synthesizer ([protocol §7](protocol.md#7-merge-gate-synthesizer)).

### researcher

- **Definition:** a read-only role that answers one research request from
  the coordinator (question, scope, deliverable, source issue) with a written
  finding; it never builds, reviews or lands and holds no gate
  ([roles](roles.md#researcher-riley)).
- **Invariants:** none held; a design-doc PR it opens is a change like any
  other (I1–I4).
- **Today:** Riley, an optional identity; a signed issue comment, or a
  design-doc PR on request.

### runtime

- **Definition:** where roles run and how they wake, start, stop and pass
  state.
- **Invariants:** must keep I1–I5.
- **Today:** Grok Bot (routines, per-PR watches, parent turns and workers).

### backend

- **Definition:** the tool implementing one concern (change, review, tracker,
  state tags, comments and markers, CI, events, owner channel).
- **Invariants:** must keep I1–I5, or the profile is unsupported.
- **Today:** GitHub, for every concern.

### profile / pack

- **Definition:** a profile is the install-time selection of one runtime and
  one backend per concern; a pack is a bundle of backends that a profile can
  pick from.
- **Invariants:** a profile that cannot keep I1–I5 is unsupported.
- **Today:** one implicit profile: Grok Bot + GitHub. No pack files yet
  (planned in [portable spec §4](specs/portable.md#4-target-layout)).
