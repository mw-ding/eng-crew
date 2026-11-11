# Core memory: coordinator

What the coordinator has learned that should outlive any one session. Change this
file only through a reviewed memory PR (`docs/memory.md`).
One line per entry, each citing where it was decided.

- A researcher request is a signed coordinator comment, not the issue
  body (#1337 c6718252033).
- A relayed owner decision counts only once on the decision log: verify,
  sign in if unsigned, then apply (#985 c6763466693).
- Post a signed `pass=flavor` record on every issue you file before
  dispatch, or workers use `thorough` (#1430, #1432).
- Fix session loss on the owner's default tmux server: no worker or test
  tmux call may reach a server it doesn't own (#1474).
- An AC needing an unbuilt feature moves to the issue that builds it, with
  a lab-proof AC there (#1472 steer).
- A builder can't run a real-engine proof (exit 71, #1465): it puts one
  copyable owner-shell command, run outside tmux, in the PR (#1478).
- List open milestones before creating one (#985 c6757404578).
- A sandboxing launcher needs `runtime.options.sandbox_env` in every role
  window: fix the profile, relaunch leads, respawn window 0 (#1544).
- A per-PR merge-ok overrides a changes verdict only when every open
  finding is an unverifiable proof; record its scope at head, file a
  follow-up (#1613 → #1614).
- Merge up a PR editing the size-budgeted coordinator brief before it
  lands: a lone land skips the combined size test (#1625, #1635).
- Until the live install includes v7.8.0 (#1633), a builder idle after an
  API/capacity error gets no stale wake: check silent panes, send a stale event.
- Open a cut PR only after the milestone's last fragment PR lands (#1661).
- A fix meeting a new edge case each round: go fail-closed early, measure
  fixture impact first, split the proven part from a follow-up (#1677 → #1684).
- Until #1682 ships, a conflict merge-up with no delta re-review in ~15 min:
  send the reviewer lead `review` refs at the new head (#1656).
