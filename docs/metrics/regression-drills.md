# Replayable regression drills

## Purpose and scope

The M2 drills (parent issue #52) exercised the harness end to end with two
tiny doc PRs: Drill A (issue #58, PR #61, lighter lane) and Drill B
(issue #59, PR #62, full lane). This page turns them into a recipe that
can be replayed by hand, with a checklist and a metrics record per run.

Design and checklist only. See [Not in scope](#not-in-scope).

Related: [protocol](../protocol.md), [roles](../roles.md),
[architecture](../architecture.md). Metrics fields are defined in
`docs/metrics/README.md` (issue #63; it may land separately).

## When to run

- After a protocol batch lands (changes to the protocol, gate contract,
  lighter lane, or templates).
- After a framework change to builder, reviewer, merger, or watch behavior.
- Before declaring a milestone's success criteria met.

## Roles

| Role | Who | Job in the drill |
| --- | --- | --- |
| Coordinator | lead | Files drill issues, keeps the clock, scores |
| Builder | Ben | Builds the PR from the issue text alone |
| Reviewer-validator | Vera | Formal review (different engine), validates |
| Merger | Sam | Merges once gates are satisfied |

## Timing capture

Record each timestamp in both PT and UTC:

- `clock_start`: when the drill issue is marked `crew:ready` (or the drill
  clock is restarted; note restarts).
- `opened_at`: PR creation time.
- `merged_at`: merge time.

Open-to-merge is `merged_at - opened_at`. Also note `merged_at -
clock_start` for context.

## Generic drill issue template

Keep the body to the task. Do not add bands, caps, or pass criteria.

```markdown
## Drill <A|B>: <one-line change>

Edit `<file>` in `<owner>/<repo>`: <exact, small wording change>.

Parent: #<parent-n>
```

Pick `<file>` by lane:

- Drill A (lighter lane): a docs-only file that is not under `.github/`,
  `templates/**`, or the protocol doc, for example `docs/architecture.md`.
- Drill B (full lane): the protocol doc, so the full lane applies.

## Drill A: lighter lane

1. Coordinator files a one-sentence docs-only issue (template above).
2. Builder (tier trivial) opens the PR. No per-PR B2 watch, no `pass=watch`
   marker, no `crew:needs-mirror`.
3. Standing doc-only merge-ok applies; no per-PR owner grant.
4. Vera reviews on a different engine than the builder; Sam merges after
   green CI and formal APPROVE.
5. Coordinator records timings and fills the metrics record.

M2 baseline: opened to merged about 5 minutes (PR #61).

## Drill B: full lane

1. Coordinator files a two-line docs issue touching the protocol doc.
2. Builder (tier default) opens the PR. B2 watch attached and verified,
   `pass=watch` marker posted, `crew:needs-mirror` until the coordinator
   mirrors the box skill.
3. Vera reviews on a different engine and APPROVEs at head.
4. Per-PR merge-ok from the owner (the standing doc-only grant is N/A).
5. Sam merges after gates clear.
6. Coordinator records timings and fills the metrics record.

M2 baseline: opened to merged about 1h 54m (PR #62).

## Coordinator / reviewer-validator only: pass/fail criteria

> **Warning: do not show these to the builder.** Keep bands and caps out of
> the builder's brief and out of any drill issue body the builder reads. A
> builder that optimizes for a visible check is reward hacking, as flagged in
> ACE and Darwin Gödel Machine (DGM) self-improving agent work. The brief is
> the task itself.

| Check | Drill A (lighter lane) | Drill B (full lane) |
| --- | --- | --- |
| Open to merge | 10-30 min band; a run outside the band needs its cause named | Gated on owner merge-ok; no PR stuck over 24h on an unsatisfiable gate |
| CI-fix attempts | 3 or fewer, else escalate | 3 or fewer, else escalate |
| Verdict rounds | 3 or fewer; 3rd REQUEST_CHANGES escalates | same |
| Formal review | one per head SHA, reviewer engine differs | same |
| `pass=watch` marker | absent | present, B2 verified |
| `crew:needs-mirror` | never applied | applied, cleared after mirror |
| Merge-ok | standing doc-only | per-PR from owner |
| Escalation | none expected | none expected |

Fail the drill if any row fails. Record which row and why.

## Checklist

Copy into the drill tracking issue per run.

- [ ] Open to merge meets the lane's timing criterion (see criteria table)
- [ ] CI-fix attempts at most 3
- [ ] Verdict rounds at most 3, no `crew:escalated` unless a cap was hit
- [ ] Every `crew:v1` marker that carries `sha=` uses the full 40-char head SHA (builder PR-body marker has no `sha=`; `pass=watch` may use any PR commit)
- [ ] Builder marker present, right before the signature
- [ ] Engine named in the marker matches the commit trailer `Engine:`
- [ ] Reviewer engine differs from the builder engine
- [ ] No plain PR conversation or inline comments from bots (review bodies
      only)
- [ ] PR body written once, never edited; markers append-only
- [ ] `pass=watch` present on the full lane only
- [ ] Lighter-lane exemptions held (Drill A): no B2 watch, no `pass=watch`,
      no `crew:needs-mirror`; still green CI and formal APPROVE
- [ ] A fix round touching code, `.github/`, `templates/**`, or the protocol
      doc moved the PR out of the lane and B2 was attached
- [ ] No owner ask lived only in a bot's own chat
- [ ] Metrics record filled

## Metrics record

Each run populates one record using the fields in `docs/metrics/README.md`.

| Field | Drill A example | Drill B example |
| --- | --- | --- |
| PR number | `<n>` | `<n>` |
| repo | `<owner>/<repo>` | `<owner>/<repo>` |
| opened_at | `<ISO UTC>` | `<ISO UTC>` |
| merged_at | `<ISO UTC>` | `<ISO UTC>` |
| open-to-merge minutes | `<m>` | `<m>` |
| CI-fix rounds | `<0-3>` | `<0-3>` |
| builder fix rounds | `<k>` | `<k>` |
| Vera verdict count | `<k>` | `<k>` |
| reopen/follow-up flag | `<yes/no>` | `<yes/no>` |

## Baseline from M2

| Drill | PR | Open to merge |
| --- | --- | --- |
| A (lighter lane) | #61 | about 5 min |
| B (full lane) | #62 | 1h 53m 52s |

## Not in scope

Executing the drill in this issue (execution is a follow-up once metrics
land), automating it as CI, and autopilot merge changes.
