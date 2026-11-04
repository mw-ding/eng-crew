---
type: added
issue: 749
pr: TBD
date: 2026-11-04
box-skill: deferred to #140
---

Add the researcher's triage-sweep brief (M24 T3, `docs/triage.md`): a `## Triage sweep` section in the tmux researcher template with the skip rules, rules-first learning lookup with `used:` citations, P0–P3 bands and the in-band score, the auto-apply / propose / never split (shadow mode proposes everything), the noise cap of 10 proposals per day, reason-specific cooldowns, owner replies recorded as decisions, and one `Triage log YYYY-MM-DD` issue per day labelled `triage:log`, one comment per sweep, closing the previous log. Protocol §4 defines the `pass=triage` record and the `pass=triage-log` line (notes, never gate inputs) and the triage labels (`triage:proposed`, `triage:duplicate`, `triage:card-extracted`, `triage:log`, `P0`–`P3`); `docs/interfaces.md` declares the tracker operations `list-items`, `label`, `comment` and `close-item`, mapped to `gh` in the GitHub backend and pack manifest.
