---
type: added
issue: 211
pr: 633
date: 2026-11-02
box-skill: none
---

Add `crew handoff manifest` and `crew handoff reconcile` with the `templates/handoff-manifest.md` template. The outgoing coordinator's manifest lists open crew items as dependency-closed sets, by reference only, secret-scanned and within one post. Posting re-reads the control item first and posts `offered` only once per handoff id, so a retry never makes a second handoff and nothing is posted after the ack. The incoming side's read-only plan adopts each set, holds a set whose PR head moved, and skips sets it already claims. Tests cover retry, partial and duplicate-ack cases.
