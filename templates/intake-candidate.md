# Intake candidate card

Use this as the body of an eng-crew issue titled `intake: <failure class> on
<owner>/<repo>#<n>`. The coordinator files it from a trigger (see
[self-improve](../docs/self-improve.md)); the helper
[`scripts/intake-sweep.py`](../scripts/README.md#intake-sweep-weekly-stuck-pass)
prints drafts in this shape. Keep it short: one card, one failure class, no
pasted logs. Replace every placeholder; delete this paragraph when filing.

```markdown
**Source:** <owner>/<repo>#<n> (<url>)
**Trigger:** reviewer-changes | ci-red-after-done | tripwire | weekly-sweep
**Failure class:** <short slug, e.g. merge-gate-race, missing-evidence, flake>
**Proposed fix:** <one line: what to change and where>
**Scope:** repo: | crew: - <reason> (triage: confirm or promote)
**Lesson:** none yet | <docs/lessons/YYYY-MM-DD-slug.md>
**Findings entry:** none yet | <docs/findings/buffer.md heading>
**Decision:** pending | accept (repo:) | accept (crew:) | close - <reason>
**Decided by:** <CoordinatorBot> on <date>
```

## Fields

| Field | Meaning |
|---|---|
| Source | The PR or issue the failure came from, as `<owner>/<repo>#<n>` plus its URL |
| Trigger | Which of the four triggers fired |
| Failure class | A short slug the coordinator searches for to catch duplicate cards |
| Proposed fix | One line. A hint for the builder, not a design |
| Scope | `repo:` (product-local) or `crew:` (generalizes), with a one-line reason. The default is `repo:` |
| Lesson | Link to the lesson file once written; `none yet` is allowed on a pending card only |
| Findings entry | Link to the one-liner in `docs/findings/buffer.md` while it is not promoted |
| Decision | Set by the coordinator only. `accept` makes it a normal builder issue; `close` records the reason |

Never paste tokens, keys, emails, private chat quotes or real box paths into a
card (spec R1). Link to the evidence instead.
