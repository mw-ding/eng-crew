---
type: added
issue: 795
pr: TBD
date: 2026-11-06
box-skill: none (internal campaign fixture and doc; no template or box-skill changes)
---

The M25 campaign gains the A17 (express self-gate and fallback) and A18 (solo) scenario specs in `scripts/fixtures/campaign/` (25.13), at level a on sandbox tmux with the fake forge. A17 proves that the default `selfgate_engine` stays `different` and that same mode runs only from an isolated `--org-profile`. An express record needs a Reason and is refused for `crew:sensitive` or `crew:spec` without an owner override, and always for `crew:solo`. The selfgate record is checked for schema, head, key, signature, verdict, open findings, mode and engine diversity. A resolved express change starts no reviewer and reaches the synthesizer only on a selfgate pass with green CI, while CI, holds, rereview and merge permission still block. A cap with an open finding, a sensitive label or a tightening rename path returns the change to the crew lane with a fresh review at head. A18 proves that a solo item never gets a crew builder, and that its PR keeps an engine-diverse independent reviewer and the synthesizer's §7 gate.
