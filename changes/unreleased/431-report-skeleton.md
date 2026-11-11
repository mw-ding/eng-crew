---
type: added
issue: 431
pr: 1709
date: 2026-11-11
box-skill: none
---

Every role's human-facing reports share one outcome-first skeleton, documented once in the roles doc (Report skeleton): a headline that ends with one status from a fixed set (pass, changes, landed, escalated, blocked), then TL;DR, numbered changes or findings, evidence and the next actor. A new optional `[report]` profile table sets each status emoji (neutral defaults) and turns every emoji off install-wide (`emoji = false`). Signatures now carry the crew team (#1291): a team file's resolved `team.name`, else its file name, else `identities.team`; legacy single-repo installs omit it. Briefs render them through the new `<RoleSignature>` and `<report-status>` placeholders; every role brief, researcher and synthesizer included, carries the resolved status set. Builder signature readers (precheck and merge-up delta routing) accept a signature with no emoji, a custom emoji or a team. No marker, gate or label changes.
