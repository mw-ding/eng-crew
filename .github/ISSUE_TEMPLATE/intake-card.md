---
name: Intake card
about: Report a crew failure in the intake-card shape (recommended, never required)
title: "intake: <failure class> on <owner>/<repo>#<n>"
---

<!-- Fields match templates/intake-candidate.md, which explains each one.
Replace every placeholder; leave Decision and Decided by for triage. Omit
Escaped from unless the defect was found after its source PR merged. Never
paste tokens, keys, emails, private chat quotes or real box paths; link the
evidence instead. A blank issue is fine too: triage extracts the fields. -->

**Source:** <owner>/<repo>#<n> (<url>)
**Trigger:** reviewer-changes | ci-red-after-done | tripwire | weekly-sweep | owner-feedback
**Failure class:** <short slug, e.g. merge-gate-race, missing-evidence, flake>
**Proposed fix:** <one line: what to change and where>
**Scope:** repo: | crew: - <reason> (triage: confirm or promote)
**Lesson:** none yet | <docs/lessons/YYYY-MM-DD-slug.md>
**Findings entry:** none yet | <docs/findings/buffer.md heading>
Escaped from: <owner>/<repo>#<pr>
**Decision:** pending
**Decided by:** <CoordinatorBot> on <date>
