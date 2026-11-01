---
type: fixed
issue: 303
pr: TBD
date: 2026-11-01
box-skill: deferred to #140
---

Under the tmux runtime the reviewer now posts the protocol §6 intake ack (#303, part of #110). Before this, no
reviewer posted it: `crew poll` has no `pr-opened` event and the reviewer brief had no ack duty, so the first
thing on a PR was the final verdict. The rendered tmux `reviewer.md` brief has a new step 3: the round-1 `review`
pass, after its live re-read and engine check, posts one COMMENT review `[<ReviewerBot>/ack] intake @ <sha7>` with
a `pass=ack` marker (`round=n/a verdict=n/a`). It skips a draft and a head that already has one, so a respawned
pass adds none, and the `validate` pass and later rounds never post it. The ack is narrative only: it wakes
nobody, counts no round and is never an approval. `docs/runtimes/tmux.md` records the choice over a `pr-opened`
poll event. `test-tmux-briefs.py` checks the rendered brief's ack step and `test-crew-poll.py` proves a
`pass=ack` marker emits no event.
