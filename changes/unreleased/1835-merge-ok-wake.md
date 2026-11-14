---
type: fixed
issue: 1835
pr: 1867
date: 2026-11-13
box-skill: none
---

A coordinator merge-ok recorded after CI is already green now wakes the synthesizer lead. `mdstack poll` keeps an authenticated permission identity per open crew PR (this runtime's coordinator `pass=steer cmd=merge-ok` record at the current full head SHA, scoped by repository, PR, head and command) and emits one new `merge-ok-recorded` event to the synthesizer when it appears, whatever CI shows. Duplicate copies, unchanged polls, prose, other authors or runtimes, other heads or PRs and malformed markers emit nothing, and a poll state written before this change seeds the identity quietly. `mdstack route` forwards the event to the synthesizer lead as durable `work` while the merge-ok is still at the live head; a superseded head, a closed PR or a merge-ok no longer at head consumes it, and a held PR stays queued for the coordinator. The event only prompts a fresh gate check: it is never approval, hold clearance or a CI waiver. The #1832 release cut sat idle about 25 minutes waiting for this wake.
