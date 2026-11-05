---
type: added
issue: 937
pr: 1009
date: 2026-11-05
box-skill: none (scripts and reference docs; no rendered template change)
---

The ownership guard, every `crew handoff` action and `crew doctor` read
and post a tracker-native control item, such as `OPS-1042`, only through
the markers backend's `read-item` and `write-item` (F2–F4 of the
tracker-native control item design). `crew up` records `write-item`
beside `read-item`. A string id fills `<control-item>`, never `<n>`.
`read-item` may print native posts (`author`, `body`, `created`, optional
`id`) or the GitHub comment shape; a mixed or incomplete output is
unreadable. A failed post is uncertain, so the core re-reads before
posting again. With a non-GitHub tracker or change backend, the manifest,
reconcile, ack, stopped and lift read open items, changes, heads, the
default-branch head and in-transit markers through declared operations
(new conditional `change.read-branch-head` and `tracker.unlabel`) and
make no `gh` call. Manifest items, run records, claims and `holds_added`
carry native ids as strings, and the doctor row prints the id as
written. GitHub calls and output are unchanged.
