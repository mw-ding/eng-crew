---
type: added
issue: 792
pr: TBD
date: 2026-11-06
box-skill: none (internal campaign fixture and doc; no template or box-skill changes)
---

The M25 campaign gains the A13 (merge-up portability and conflict chain) scenario spec in `scripts/fixtures/campaign/` (25.10). It runs at level a on sandbox tmux with the fake forge. A clean tool merge-up pins all four SHAs, and identical content with green CI carries the passing verdict from H with no new round. The owner's merge-ok at H does not carry to the updated head. Whitespace, path and mode changes and an unavailable base never carry. A train over three PRs editing one shared line keeps the clean member and drops the two conflicts. `crew train close` routes them to builders with no update-branch call and no synthesizer edit. Each builder resolves the conflict and records the four SHAs in a signed fix note, and the differing patch needs a new head-pinned delta verdict. A verdict without a base drops as `no-verified-base` and routes to the reviewer.
