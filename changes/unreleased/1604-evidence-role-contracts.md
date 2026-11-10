---
type: changed
issue: 1604
pr: TBD
date: 2026-11-10
box-skill: none
---

Evidence and role contracts (M42 B1). Typed evidence now asks for a negative control for each new or changed guard: the guard fails on a mutated copy or the nearest wrong input, then passes at head, as a fail-then-pass pair in the CLI adapter. Missing, it is `disagrees` under `evidence = typed` and a soft finding under `inline`; a test-only guard change is no longer exempt, and a change with no guard keeps a reasoned N/A (#1604). A new Claim scope section in `docs/verification.md` bounds a claim to the read behind it (#423), asks for schema/code equivalence cases on a changed validator (#424) and proves a changed fail-closed tool through its shipped entry point with a nonzero exit on rejection (#373). Protocol §6 names the backend read head as a change's one authoritative revision: the builder reads it back after each push for markers and evidence, and each review, validate, gate or land pass pins its reads to one head (#377, #376). Worker briefs must cite framework docs readable on the worker's host at the pin, or block with `spec-unreadable` (#375), keep required reporting writes apart from commands under test (#378), and take rigor only from flavor records and path classes; the coordinator raises rigor through an item record, never a hand-written brief floor (#745). The builder, reviewer, synthesizer and coordinator briefs carry short pointers to these rules; no marker format, cap or label changes.
