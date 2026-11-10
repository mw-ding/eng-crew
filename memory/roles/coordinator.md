# Core memory: coordinator

What the coordinator has learned that should outlive any one session. Change this
file only through a reviewed memory PR (`docs/memory.md`).
One line per entry, each citing where it was decided.

- A researcher request must be a signed coordinator comment on the source
  issue; Riley stops on one found only in the issue body (#1337
  c6718252033).
- While a cut PR is open, post `hold-until-#<cut issue>` on every PR adding
  a `changes/unreleased/` fragment: one landing between the cut's base and
  its merge fails release `validate`. A new PR does not wake you, so check for
  unheld PRs on every wake (#985 c6725307534, #1432, #1433).
- Until #1559 ships, after a cut lands, check the release, close its
  milestone, run the capture and admit the next one: route consumes the
  cut's `pr-merged` without waking you (#1559).
- Post a signed `pass=flavor` record on every issue you file, before
  dispatch; without one, builder and reviewer fall back to `thorough`
  (#1430, #1432).
- A session-loss fix must hold on the owner's default tmux server, not a
  private socket: fix the root cause so worker and test tmux calls can't
  reach a server they don't own (#985 c6731966111, #1474, #1475).
- An AC that needs an unbuilt feature moves to the issue that builds it, with
  a lab-proof AC there; don't spend review rounds on it (#1472 steer).
- A real-engine proof can't run in a builder session (exit 71 under the
  seatbelt, #1465): the builder puts one copyable owner-shell command, run
  outside tmux, in the PR up front, so one owner run closes the AC (#1478,
  #1442).
- List open milestones before creating one; the owner's name may already
  exist from another session (duplicate M40, #985 c6757404578).
- When the launcher sandboxes sessions, every role window needs
  `runtime.options.sandbox_env` at launch, or leads can't spawn and window 0
  can't start a synthesizer: fix the profile, relaunch leads, respawn
  window 0 in place (#1544 c6757280891).
