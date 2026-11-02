---
type: changed
issue: 507
pr: 516
date: 2026-11-01
box-skill: coordinator mirror required
---

The content helper compares verified and tool-updated patches without ignoring whitespace, paths, modes or binary changes. With a recorded review base, trains check each applied patch before inclusion and again at land, route differing patches to the builder and record content=identical with the full carried-from SHA. Both synthesizer bindings carry only a passing verdict with green live CI and recheck every other gate. Unchanged-head legacy train approvals remain eligible without claiming content portability. Second slice of #502.
