# Core memory: coordinator

Reviewed PRs only (`docs/memory.md`).

- Relayed owner decisions: verify, sign if unsigned, apply (#985
  c6763466693).
- Sign `pass=flavor` before dispatch; else `thorough` (#1430, #1432).
- Pre-dispatch `cmd=plan-ok` on each milestone tracker, even after #985
  (#1779).
- Worker/test tmux: no unowned servers (#1474).
- Unbuilt-feature ACs: lab proof on their issue (#1472).
- No builder real-engine proof (exit 71, #1465): PR gives owner-shell
  command outside tmux (#1478).
- Owner-shell captures: builder-signed fix review at head, not coordinator
  comments (#1766).
- List open milestones before adding (#985 c6757404578).
- Sandbox launchers need `runtime.options.sandbox_env`: fix profile,
  relaunch leads and window 0 (#1544).
- PATH `codex`/`claude` may sandbox (exit 71): check before proof asks
  (#1707, #985 c6816385952).
- Merge-ok beats changes only if all open findings are unverifiable
  proofs; log scope at head, file follow-up (#1613, #1614).
- Merge up budgeted coordinator brief PRs before land; lone lands skip
  combined size test (#1625, #1635).
- Approved PR red CI: check tests' module use before calling flaky;
  re-run, never waive (#1803).
- Cut PR waits for milestone's last fragment (#1661), freezes fragment
  PRs; hold by closing unmerged (#985 c6814551260).
- New edge cases per fix: fail closed, split proven work (#1677, #1684).
- Until #1792 installed: Codex-first (Claude folder trust in #1707);
  restore Opus-first after upgrade (#985 c6846454166).
- Post-land remove PR review files: route reclaims builder. Post-cut:
  check release, close milestone, capture, admit next (#1559, #1719).
- Until #1830/#1835/#1836 ship: deep tier via builder-lead note ref;
  hand synthesizer land after merge-ok on already-green CI; lead settles
  owner-blocked held id, re-sends on owner answer (#1774, #1832, #1833).
- Pre-land simulated-cut run: new tests reading release state
  (version, `changes/`, CHANGELOG; #1821, #1828).
