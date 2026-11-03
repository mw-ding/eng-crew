---
type: fixed
issue: 657
pr: 666
date: 2026-11-03
box-skill: none
---

`crew train check` no longer blocks on prefixed paths such as `templates/evidence/cli-exit-stdout.md` or `.crew/evidence/<file>`: only a repo-root `evidence/<path>` counts as a required artifact. The evidence gate reads only the PR body's `## Acceptance Evidence` section and signed builder fix or ci-fix reviews at head, so another role's mention creates no requirement, and it accepts inline reproductions in those reviews and in `~~~` fences.
