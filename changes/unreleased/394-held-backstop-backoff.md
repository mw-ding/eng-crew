---
type: fixed
issue: 394
pr: 1628
date: 2026-11-10
box-skill: none
---

The watcher's backstop no longer wakes the coordinator every 30 minutes while only held or owner-blocked work is open. `mdstack poll` records `held` in `poll-state.json` (open crew PRs and `crew:ready` issues labelled `crew:hold`, `crew:escalated` or `crew:needs-md`, and the issues such a PR closes). When every recorded run's item is in that list or has an open `asks/<n>.json`, and no lead has pending work, `mdstack watch` waits its idle cap (16 × the stale-sweep period, at least 4 h) instead of the short backstop. A run that is live, unrelated or unclassified, or a pending lead message, keeps the 30-minute backstop, and the watcher restores it on the next scan once live work reappears. Ask-deadline and poll wakes are unchanged.
