# Core memory: coordinator

What the coordinator has learned that should outlive any one session. Change this
file only through a reviewed memory PR (`docs/memory.md`).
One line per entry, each citing where it was decided.

- A logged relayed owner decision counts: verify, sign if unsigned, apply
  (#985 c6763466693).
- Sign each issue's `pass=flavor` before dispatch or workers use
  `thorough` (#1430, #1432).
- No worker or test tmux call may touch an unowned server (#1474).
- An AC needing an unbuilt feature moves to its issue as a lab proof
  (#1472).
- A builder can't run a real-engine proof (exit 71, #1465): its PR gives
  an owner-shell command, outside tmux (#1478).
- Owner-shell captures count only in a builder-signed fix review at
  head, not a coordinator comment; builder reposts them (#1766).
- List open milestones before creating one (#985 c6757404578).
- Sandboxing launchers need `runtime.options.sandbox_env` everywhere: fix
  profile, relaunch leads, window 0 (#1544).
- PATH `codex`/`claude` may be sandboxing launchers (exit 71): check before
  asking for sandbox proof (#1707, #985 c6816385952).
- A merge-ok beats a changes verdict only if all open findings are
  unverifiable proofs; record scope at head, file follow-up (#1613, #1614).
- Merge up a PR editing the budgeted coordinator brief before land;
  lone lands skip the combined size test (#1625, #1635).
- Until v7.8.0 is live, wake builders idle after API/capacity errors
  (#1633).
- Open a cut PR only once the milestone's last fragment lands (#1661); it
  freezes fragment PRs; to hold a cut, close it unmerged (#985
  c6814551260).
- A fix hitting new edge cases each round: fail closed, split off proven
  work (#1677, #1684).
- Until #1682 ships, a conflict merge-up unreviewed ~15 min: send
  reviewer lead `review` refs at head (#1656).
- After a land, delete its PR's review files: route reclaims the builder.
  After a cut: check release, close milestone, capture, admit next (#1559,
  #1719).
