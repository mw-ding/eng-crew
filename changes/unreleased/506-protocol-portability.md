---
type: changed
issue: 506
pr: 512
date: 2026-11-01
box-skill: coordinator mirror required
---

Protocol §7 and its gate registry permit passing verdicts to carry across clean tool-performed base updates only with exact changed-line equality and green CI at the updated head. Conflicts or differing patches route through the builder and delta re-review; owner permission, holds, rereview and runtime gates remain live checks. First slice of #502; synthesizer and reviewer bindings follow separately.
