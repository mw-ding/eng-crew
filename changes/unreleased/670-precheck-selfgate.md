---
type: added
issue: 670
pr: 696
date: 2026-11-03
box-skill: none
---

Add `crew-precheck.py --pass selfgate` for express changes. It reads the latest signed builder `pass=selfgate` record at the full head SHA, rejects a malformed record (exact field set, full `base`, `round=n/a`, `pr` matching the PR, `reviews` from 1 to the express cap, `open` at most `findings`), and fails a `changes` verdict, a `pass` with open findings or failed checks, a `mode` other than the profile's effective `selfgate_engine`, and, under `different`, a reviewer engine that matches the record's builder engine or any commit's `Engine:` trailer. The precheck pass is unchanged.
