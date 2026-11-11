# Core memory: coordinator

What the coordinator has learned that should outlive any one session. Change this
file only through a reviewed memory PR (`docs/memory.md`).
One line per entry, each citing where it was decided.

- A researcher request must be a signed coordinator comment on the source
  issue, not its body (#1337 c6718252033).
- After every land, check open crew PRs for `CONFLICTING`: GitHub runs no
  CI on them, so hand the builder lead a merge-up at once (#1398).
- A relayed owner decision (inbox, another session) counts only once it's
  on the decision log: verify it, sign it in if unsigned, then apply it
  (#985 c6763466693).
- Post a signed `pass=flavor` record on every issue you file before
  dispatch, or builders and reviewers use `thorough` (#1430, #1432).
- Fix session loss on the owner's default tmux server, not a private
  socket: no worker or test tmux call may reach a server it doesn't own
  (#985 c6731966111, #1474, #1475).
- An AC needing an unbuilt feature moves to the issue that builds it, with
  a lab-proof AC there (#1472 steer).
- A builder can't run a real-engine proof (exit 71, #1465): it puts one
  copyable owner-shell command, run outside tmux, in the PR up front
  (#1478, #1442).
- List open milestones before creating one (#985 c6757404578).
- A sandboxing launcher needs `runtime.options.sandbox_env` in every role
  window at launch: fix the profile, relaunch leads, respawn window 0 in
  place (#1544 c6757280891).
- An owner's per-PR merge-ok can override a changes verdict only when
  every remaining finding is an unverifiable proof. Record the override's
  scope at head and file a verification follow-up (#1613 → #1614).
- Merge up a PR editing the size-budgeted tmux coordinator brief onto
  `main` before it lands: a lone land skips the combined size test (#1625,
  #1629, #1635).
- Until #1633 ships, a builder idle at its prompt after an API/capacity
  error gets no stale wake: check silent panes, send the lead a stale event.
