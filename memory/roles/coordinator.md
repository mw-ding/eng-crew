# Core memory: coordinator

Reviewed PRs only (`docs/memory.md`); cite each entry's decision.

- A logged relayed owner decision counts: verify, sign if unsigned, apply
  (#985 c6763466693).
- Sign `pass=flavor` before dispatch or workers use `thorough` (#1430, #1432).
- Before first dispatch, record `cmd=plan-ok` on each milestone tracker,
  even if the owner decided on #985 (#1779).
- No worker or test tmux call may touch an unowned server (#1474).
- Move ACs needing unbuilt features to their issue as lab proof (#1472).
- Builders can't run real-engine proof (exit 71, #1465): PRs give an
  owner-shell command outside tmux (#1478).
- Owner-shell captures: builder reposts in a signed fix review at head;
  coordinator comments don't count (#1766).
- List open milestones before creating one (#985 c6757404578).
- Sandbox launchers need `runtime.options.sandbox_env` everywhere: fix
  profile, relaunch leads, window 0 (#1544).
- PATH `codex`/`claude` may be sandboxing launchers (exit 71): check before
  asking for sandbox proof (#1707, #985 c6816385952).
- Merge-ok beats changes only if all open findings are unverifiable
  proofs; record scope at head, file follow-up (#1613, #1614).
- Merge up a PR editing the budgeted coordinator brief before land;
  lone lands skip the combined size test (#1625, #1635).
- Before calling approved PR red CI a flake, check tests' use of the
  changed module; re-run, never waive (#1803).
- Open a cut PR only once the milestone's last fragment lands (#1661); it
  freezes fragment PRs; to hold a cut, close it unmerged (#985
  c6814551260).
- A fix hitting new edge cases each round: fail closed, split off proven
  work (#1677, #1684).
- Until #1792's fix is installed, Codex-first builders: Claude hits folder
  trust in #1707 run copies; restore Opus-first after upgrade
  (#985 c6846454166).
- After land, delete PR review files: route reclaims the builder. After
  cut: check release, close milestone, capture, admit next (#1559,
  #1719).
