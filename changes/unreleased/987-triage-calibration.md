---
type: changed
issue: 987
pr: TBD
date: 2026-11-04
box-skill: deferred to #140
---

Triage calibration (`docs/triage.md`, researcher triage-sweep brief): the
learning lookup gains a "still applies?" step before classification
(implemented or changed since filing, cited as a PR, a commit on a named path
or a CHANGELOG line, with `Not checked:`), where a fully overtaken item gets a
proposed close (`overtaken: implemented` or `overtaken: changed`) and a partly
overtaken one is banded for its remaining gap only. Priority bands follow the
owner's criteria: P0 is mainly the owner's explicit call, otherwise only a
failure happening now on this crew or backend; P1 needs recurrence, a
measured throughput or cost hit or an owner report; P2 covers new features and
single unreproduced reports; each record names its criterion and the sweep
checks for under-rating. Similar open issues get a consolidation proposal
naming the survivor, with occurrences counted across them. The coordinator can
ask for an on-demand recalibration sweep with a signed `recalibrate` comment on
the day's triage log; it re-checks the unanswered proposals and draws a fresh
spot-check sample. Closes stay proposals in every mode.
