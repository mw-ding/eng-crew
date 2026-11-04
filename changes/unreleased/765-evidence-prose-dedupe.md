---
type: changed
issue: 765
pr: 834
date: 2026-11-04
box-skill: pending coordinator mirror (Grok Bot `eng-crew-roles` renders `docs/roles.md`)
---

`docs/verification.md` and `docs/roles.md` no longer restate evidence
placement. Protocol §3 owns placement (inline only, body written once, late
evidence in a signed fix or ci-fix review, rereview); `docs/verification.md`
owns shape, N/A, reproduction and each role's evidence duty. The verification
intro, its builder placement and late-evidence bullets, and the roles.md
evidence-duty and handoff copies now link to those owners. Every removed
qualifier already lives there. The rendered `## PR conventions` copy and the
`templates/evidence/*.md` adapters are unchanged. Structural only; no rule,
gate or marker change.
