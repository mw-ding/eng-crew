# Lessons log

Dated record of what the crew learned from pilots, incidents and bottleneck
reviews. Each lesson is written down here first, then turned into an issue and a
PR (see [CONTRIBUTING.md](../../CONTRIBUTING.md)).

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
| Status | `shipped` (the fix is live), `documented` (the protocol or role docs prescribe it, but the source does not confirm the live rollout) or `open` (not shipped or documented, or the source does not say). Never guess |
| Linked issue/PR | The issue or PR in this repo that tracks the fix, or `none yet` |

Template:

```markdown
### <short title>

- **Date:** YYYY-MM-DD
- **Source / evidence:** <where it comes from>
- **Finding:** <what happened>
- **Impact:** <cost>
- **Fix:** <change>
- **Status:** open | documented | shipped
- **Linked issue/PR:** none yet | <owner>/<repo>#N
```

## Index

| File | Date | Summary |
|---|---|---|
| [2026-10-19-bottlenecks.md](2026-10-19-bottlenecks.md) | 2026-10-19 | Bottleneck analysis of 22 pilot PRs: headline timings, five ranked losses, other lessons |
