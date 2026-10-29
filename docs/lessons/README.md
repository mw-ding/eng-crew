# Lessons log

Dated record of what the crew learned from pilots, incidents and bottleneck
reviews. Each lesson is written down here first, then turned into an issue and a
PR (see [CONTRIBUTING.md](../../CONTRIBUTING.md)).

Repeated small smells go to the findings buffer, [docs/findings/](../findings/README.md),
first and are batched into one issue (the M5 batch), not one lesson each.
Lessons stay for incidents that have a written analysis.

Entries are sanitized per spec R1: no tokens, keys, email addresses, private chat
quotes or real box paths. Use placeholders (`<state-dir>`, `<owner>/<repo>`) and
bot role names (coordinator, builder, reviewer-validator, synthesizer).

## File naming

One file per analysis or incident: `YYYY-MM-DD-<slug>.md`, where the date is when
the analysis was done. A file holds one or more entries.

## Entry format

Every entry uses these fields, in this order. A file may group related entries
under a table or a list, but each entry still answers every field.

| Field | Meaning |
|---|---|
| Date | When the lesson was observed or written up (`YYYY-MM-DD`) |
| Source / evidence | Where the finding comes from: the pilot, PR, timeline or analysis. Sanitized; worked-example references are plain text, not links |
| Finding | What happened, in one or two sentences |
| Impact | The cost, in time, rounds or risk. Give a number only when the source gives one |
| Fix | The change that addresses it, or the proposed change |
| Status | `applied` (the fix is in effect: it is in the protocol, role docs, templates or scripts on `main`, or the source confirms it live), `superseded` (replaced by a different fix or entry; name it) or `open` (not applied, only proposed, an accepted limit, or the evidence does not settle it). Follow the status word with a short reason that names the evidence, such as a file, section or PR. Never guess |
| Linked issue/PR | The issue or PR in this repo that tracks the fix, or `none yet` |

Template:

```markdown
### <short title>

- **Date:** YYYY-MM-DD
- **Source / evidence:** <where it comes from>
- **Finding:** <what happened>
- **Impact:** <cost>
- **Fix:** <change>
- **Status:** open | applied | superseded
- **Linked issue/PR:** none yet | <owner>/<repo>#N
```

### Status vocabulary

One vocabulary: `applied`, `superseded`, `open`. It replaces the earlier
`shipped` and `documented`, which both map onto `applied`; the evidence after
the word says where the fix lives (for example "`docs/roles.md` Quota routing"
or "box configuration, per the source"). A fix the docs prescribe is `applied`
once it is on `main`. Whether a box skill copy matches is a separate question,
answered by the
[drift check](../../scripts/README.md#skill-drift-check-coordinator).

Hygiene pass: when a PR changes a protocol, role or template rule that a lesson
describes, re-check that lesson's status in the same PR. Verify against `main`
(`docs/`, `templates/`, `scripts/`, `CHANGELOG.md`, merged PRs); if the evidence
does not settle it, keep `open` and say why.

## Index

| File | Date | Summary |
|---|---|---|
| [2026-10-19-bottlenecks.md](2026-10-19-bottlenecks.md) | 2026-10-19 | Bottleneck analysis of 22 pilot PRs: headline timings, five ranked losses, other lessons |
| [2026-10-20-validation-gate.md](2026-10-20-validation-gate.md) | 2026-10-20 | A failed validation pass was overridden by an APPROVE on #16; the rule that a validation fail blocks APPROVE is now documented (#24) |
| [2026-10-20-evidence-on-pr-head.md](2026-10-20-evidence-on-pr-head.md) | 2026-10-20 | Evidence a verdict relies on goes on the PR head, never a side branch (PR #12 incident) |
| [2026-10-20-merge-up-rounds.md](2026-10-20-merge-up-rounds.md) | 2026-10-20 | Merge-ups must not burn review rounds; an ack cannot satisfy the merge gate, so a clean merge-up after an approval gets a formal re-approve (#20) |
| [2026-10-20-actual-builder-engine.md](2026-10-20-actual-builder-engine.md) | 2026-10-20 | A fix round was written by Codex while the builder marker said claude-code; the reviewer engine must differ from the engine that actually wrote the round (#21) |
| [2026-10-23-builder-watch-attach.md](2026-10-23-builder-watch-attach.md) | 2026-10-23 | The builder's per-PR watch B2 silently failed to attach on PR #35 and the PR stalled about 62 min; B2 attachment is now verified, recorded and swept (#36) |
| [2026-10-23-merge-gate-watch-race.md](2026-10-23-merge-gate-watch-race.md) | 2026-10-23 | PR #41 merged before the builder's B2 hand-off reached its parent turn, so no watch or marker existed; the merge gate now requires the `pass=watch` marker (#43) |
| [2026-10-23-watch-handoff-first-run.md](2026-10-23-watch-handoff-first-run.md) | 2026-10-23 | First live run of the verified B2 hand-off on PR #38: pin the routine folder id, parent-turn-only marker, full 40-char SHA in markers (#39) |
| [2026-10-25-lighter-lane-routing.md](2026-10-25-lighter-lane-routing.md) | 2026-10-25 | Lighter-lane templates skip B2/watch and mirror holds; explicit messages route changes requests, red CI and cleanup (#57) |
