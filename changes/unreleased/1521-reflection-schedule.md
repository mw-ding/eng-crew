---
type: added
issue: 1521
pr: 1553
date: 2026-11-09
box-skill: none
---

Opt-in `[reflection] enabled` (default `false`) schedules protocol reflections. The researcher's new `protocol-reflection` routine makes the last full ISO week pending each Monday, and `mdstack watch` makes a milestone's window pending at once when it closes, independent of `[triage]` and its milestone ledger. Pending windows coalesce into one `mdstack spawn researcher --reflection` run at a time. The ledger in `reflection/ledger.json` survives sleep and a full researcher pool. Only the posted `pass=reflection` report completes a window. A failed start retries under the same run ID without a second queue entry, and a missed week catches up once. `mdstack reflection` prints the ledger.
