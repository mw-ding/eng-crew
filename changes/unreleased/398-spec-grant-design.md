---
type: added
issue: 398
pr: 948
date: 2026-11-04
box-skill: deferred to #140
---

Design note (proposed, not in effect) for a deterministic spec change
definition and an opt-in spec scope for the standing merge grant. Protocol
§7 gains a proposal section: a change is a spec change when it carries
`crew:spec` or any path, rename sides included, matches a spec glob
(default `docs/specs/**`), and an optional `merge_grant_scope` (default
`["approved"]`) may add `spec` only when the recorded owner grant authorizes
it. Sensitive, gate-contract and release-approval changes, `unverified`
evidence and open rereviews stay excluded. The runtime options reference
lists the proposed key. No gate, key or behaviour changes until the B1 and
B2 slices land.
