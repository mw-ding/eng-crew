---
type: added
issue: 931
pr: 1008
date: 2026-11-05
box-skill: deferred (standing owner mirror deferral, #985; protocol §7 and tmux template wording, no live Grok Bot behaviour change since Grok Bot refuses async)
---

Asynchronous land, persisted intent and restart (#873 slice B3). `crew land
request` records a land intent keyed by change and head before its first
status read, and `landed` prints the merge record's landed revision and a
`pass=merge` marker with `sha=` the checked head and `landed=` the landed
revision. New `crew land resume` reads the status of every recorded intent
on a wake and never requests: an in-flight land resumes polling, a landed
one prints its pending record, and a never-requested one is dropped. New
`crew land done` clears an intent only once it is marked landed. Protocol §7
states the asynchronous land record and restart rules. Asynchronous land,
rendered and gated (#873 slice B4). With `land.mode = "async"`, the tmux
synthesizer brief's step 3 renders `crew land request`, the merge record and
`crew land resume` from `<op:>` tokens, and the builder brief runs
`change.publish` after opening when the backend declares `land.opens_draft`.
`land.serializes` takes no land lock (C7) and `land.tests_against_tip` meets
tested-with-default-branch by the backend's land check; `crew train build`
and `bisect` then refuse, naming that key. A bare `async` changes no gate.
Protocol §7, its gate registry and the tmux C7 row name the backend
alternatives. Sync renders, GitHub included, stay byte-identical; Grok Bot
still refuses `async`.
