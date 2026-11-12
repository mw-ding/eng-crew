# Core memory: coordinator

What the coordinator has learned that should outlive any one session. Change this
file only through a reviewed memory PR (`docs/memory.md`).
One line per entry, each citing where it was decided.

- A relayed owner decision counts only once logged: verify, sign if
  unsigned, apply (#985 c6763466693).
- Post a signed `pass=flavor` record on each filed issue before
  dispatch, or workers use `thorough` (#1430, #1432).
- No worker or test tmux call may reach a server it doesn't own, e.g.
  the owner's default (session loss, #1474).
- An AC needing an unbuilt feature moves to the issue building it, with
  a lab-proof AC (#1472 steer).
- A builder can't run a real-engine proof (exit 71, #1465): its PR gives
  one copyable owner-shell command, run outside tmux (#1478).
- List open milestones before creating one (#985 c6757404578).
- A sandboxing launcher needs `runtime.options.sandbox_env` in all role
  windows: fix the profile, relaunch leads, respawn window 0 (#1544).
- A per-PR merge-ok overrides a changes verdict only if every open
  finding is an unverifiable proof; record scope at head, file a
  follow-up (#1613 → #1614).
- Merge up a PR editing the size-budgeted coordinator brief before
  landing: a lone land skips the combined size test (#1625, #1635).
- Until the live install has v7.8.0 (#1633), a builder idle after an
  API/capacity error gets no stale wake: check silent panes, send one.
- Open a cut PR only after the milestone's last fragment lands (#1661).
- A fix hitting a new edge case each round: fail closed early, measure
  fixture impact, split proven work from a follow-up (#1677 → #1684).
- Until #1682 ships, a conflict merge-up with no delta re-review in ~15 min:
  send the reviewer lead `review` refs at new head (#1656).
- After each land, delete that PR's review files (route reclaims the
  builder by lifecycle event); after a cut also check the release,
  close its milestone, capture, admit the next (#1559, #1719).
