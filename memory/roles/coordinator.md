# Core memory: coordinator

What the coordinator has learned that should outlive any one session. Change this
file only through a reviewed memory PR (`docs/memory.md`).
One line per entry, each citing where it was decided.

- A relayed owner decision counts once logged: verify, sign if
  unsigned, apply (#985 c6763466693).
- Sign a `pass=flavor` record per issue before dispatch, or
  workers use `thorough` (#1430, #1432).
- No worker or test tmux call may reach an unowned server (#1474).
- An AC needing an unbuilt feature moves to its building issue, with a
  lab-proof AC (#1472).
- A builder can't run a real-engine proof (exit 71, #1465): its PR gives
  an owner-shell command, outside tmux (#1478).
- List open milestones before creating one (#985 c6757404578).
- A sandboxing launcher needs `runtime.options.sandbox_env` in all
  windows: fix profile, relaunch leads, respawn window 0 (#1544).
- PATH `codex`/`claude` may be sandboxing launchers (inner sandbox exits
  71): check before asking for a sandbox proof (#1707, #985 c6816385952).
- A per-PR merge-ok beats a changes verdict only if all open findings
  are unverifiable proofs; record scope at head, file follow-up
  (#1613 → #1614).
- Merge up a PR editing the size-budgeted coordinator brief before
  land: lone lands skip the combined size test (#1625, #1635).
- Until v7.8.0 is live (#1633), wake builders idle after an
  API/capacity error.
- Open a cut PR only once the milestone's last fragment lands (#1661).
- An open cut PR freezes all fragment PRs: to hold a cut, close it
  unmerged; re-cut on `main` later (#985 c6814551260).
- A fix hitting a new edge case per round: fail closed early, split
  off proven work (#1677 → #1684).
- Until #1682 ships, a conflict merge-up unreviewed in ~15 min: send
  reviewer lead `review` refs at head (#1656).
- After a land, delete its PR's review files (route reclaims the
  builder); after a cut check the release, close the milestone, capture,
  admit next (#1559, #1719).
