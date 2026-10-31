# Lessons: tmux crew local dry runs

Two local dry runs of the tmux crew before the live sandbox run of #139. Each
used an isolated tmux server, a fake `gh` and a local bare origin, with real
Claude Code and Codex windows. Finding IDs (B1, B2, F1–F21) are the ones in
the first run's evidence comment on mw-ding/eng-crew#139.

- **First run (2026-10-30, main fe0a70b):** issue → PR → round 1 `changes` →
  fix → round 2 `pass` → merge-ok → land completed, but needed 6 manual
  unblocks: 2 blockers, 12 bugs, 4 doc gaps, 5 nits. The fixes are the
  M14.1 PRs #241, #240, #247 and #244.
- **Second run (#234):** the same setup on `main` after those PRs, aiming
  for zero manual unblocks. Its result is added here with the #139 live-run
  evidence.

## Entries

### The watcher wedged and the wake queue lost or doubled records (B1, F10, F11, F12)

- **Date:** 2026-10-30
- **Source / evidence:** first dry run, mw-ding/eng-crew#139. The watcher ran
  `crew poll` (no `--once`) as a blocking `--source` and never read
  `queue.jsonl`: the queue held `ci-passed` while the coordinator slept. Poll
  events were queued twice (F10); the coordinator truncated the queue by hand
  (F11); a killed watcher left `watcher.pid` and replayed an old `done:` (F12).
- **Finding:** The one wake path into the coordinator could block forever,
  and the queue had no safe reader.
- **Impact:** Blocker; one manual unblock (re-arm with `--once`).
- **Fix:** Architecture: each source runs under a timeout and a timed-out
  source becomes a `source-timeout` wake; the watcher wakes on queue growth;
  a source that grew the queue has its stdout ignored; state saved after
  every scan and on SIGTERM/SIGINT; new `crew drain` under `wake/queue.lock`.
  Regression tests in `scripts/test-crew.py`. The brief's one-shot source is
  in #244.
- **Status:** applied. `docs/runtimes/tmux.md` crew watch and crew drain, in
  #241.
- **Linked issue/PR:** mw-ding/eng-crew#230, mw-ding/eng-crew#241

### An evidence-only fix round deadlocked round 2 (B2, F3, F18, F21)

- **Date:** 2026-10-30
- **Source / evidence:** first dry run, mw-ding/eng-crew#139. `crew poll`
  emitted `ci-passed` only on a head or CI change, so a fix with no commit
  woke no reviewer, and the round-2 reviewer stopped as `stale`. Review and
  validate claims collided (F3); the reviewer worktree and the `ci-passed`
  record had no round (F18, F21).
- **Finding:** Multi-round review at an unchanged head could not proceed
  without the owner.
- **Impact:** Blocker; one manual unblock (the owner chose to push a commit).
- **Fix:** Architecture: poll derives the round and emits `fix-at-head` for a
  builder `pass=fix` at the verdict head; claims and worktrees carry round and
  pass; `ci-passed` carries `round` (#247). Brief side: the coordinator
  spawns the next round on that `done:`, and the reviewer's idempotency check
  is keyed per round (#244). Tests in `scripts/test-crew.py`.
- **Status:** applied. `docs/runtimes/tmux.md` crew poll table and spawn
  claims, in #247; tmux briefs in #244.
- **Linked issue/PR:** mw-ding/eng-crew#232, mw-ding/eng-crew#247,
  mw-ding/eng-crew#244

### Processes, hooks and env leaked across windows (F2, F5, F6, F8, F19)

- **Date:** 2026-10-30
- **Source / evidence:** first dry run, mw-ding/eng-crew#139. 7 Codex
  processes survived `crew down` and `kill-server` (Codex ignores SIGHUP,
  F2). The coordinator's Stop hook fired in a builder window (F5). The
  coordinator's trust dialog defaulted to `No, exit` (F6). The sandbox
  variable reached Codex role windows only, so both harnesses first exited 71
  (F8). `crew up` printed render chatter (F19).
- **Finding:** Window isolation held for worktrees but not for processes,
  hooks or environment.
- **Impact:** Two manual unblocks (sandbox env, trust dialog) and orphaned
  processes after teardown.
- **Fix:** Architecture: `crew kill` / `crew down` stop the pane's process
  group and verify it is gone; `crew guard` is a no-op unless
  `CREW_ROLE=coordinator`; `CREW_SANDBOX_ENV` goes to every window; Codex
  coordinator pre-trusted; render output only on failure. Claude Code has no
  per-project trust option, so its dialog now probes `ambiguous` and the
  operator accepts it once ([runbook: tmux runtime](../runbook-new-repo.md#tmux-runtime)).
  Tests in `scripts/test-crew.py`.
- **Status:** applied. `docs/runtimes/tmux.md` crew up, crew kill, crew guard
  and crew status, in #240.
- **Linked issue/PR:** mw-ding/eng-crew#231, mw-ding/eng-crew#240

### Probes and restart misread runs (F4, F7, F17, F20)

- **Date:** 2026-10-30
- **Source / evidence:** first dry run, mw-ding/eng-crew#139. A builder that
  died after a normal `done:` could not be restarted or flagged (F4). Codex's
  `Hooks need review` dialog stalled every Codex window while status said
  `alive`, losing about 5 minutes on one review (F7). The synthesizer used
  the reviewer's avoid-the-builder-engine rule (F17). A dead pane's command
  read `export` (F20).
- **Finding:** Liveness and restart rules treated a waiting builder as
  finished and a stalled window as alive.
- **Impact:** One manual unblock per Codex window (F7) and one refused
  restart (F4).
- **Fix:** Architecture: `done:` is terminal only for reviewer and
  synthesizer runs; the hooks dialog probes `ambiguous`; only the reviewer
  avoids builder engines; a dead pane reads `dead`. Tests in
  `scripts/test-crew.py`. Dismissing the Codex dialog is still an operator
  step (runbook troubleshooting).
- **Status:** applied. `docs/runtimes/tmux.md` Q7, crew status and crew
  restart, in #247.
- **Linked issue/PR:** mw-ding/eng-crew#232, mw-ding/eng-crew#247

### The briefs did not work outside eng-crew (F1, F9, F13, F14, F16)

- **Date:** 2026-10-30
- **Source / evidence:** first dry run, mw-ding/eng-crew#139. The briefs never
  said where `crew` is (F1); the synthesizer took a raw `flock` on a missing
  `locks/` dir and hand-rolled a lock (F9); they cited eng-crew `docs/` paths
  absent in the target repo, copied in by hand (F13); no role wrote a step
  summary, so `crew logs` was empty (F14); `gh` commands lacked `-R` (F16).
- **Finding:** The rendered briefs assumed they ran inside the eng-crew repo.
- **Impact:** One manual unblock (docs copied in); one improvised land lock.
- **Fix:** `CREW_BIN` in every window env (#240), and in the briefs with
  `<eng-crew>/docs/` paths from `paths.eng_crew`, `crew land-lock`, a
  concrete `step-summary.py` call and a `-R <owner>/<repo>` rule (#244).
  Prose only for the brief text, because whether a role follows its brief
  depends on agent behaviour at run time; the renderer's golden files only
  pin the text.
- **Status:** applied. `templates/runtimes/tmux/*.md`, in #244.
- **Linked issue/PR:** mw-ding/eng-crew#233, mw-ding/eng-crew#244,
  mw-ding/eng-crew#240

### Codex read-only sandbox and status writes (F15)

- **Date:** 2026-10-30
- **Source / evidence:** first dry run, mw-ding/eng-crew#139, suspected only:
  the inherited outer sandbox masked it.
- **Finding:** Codex `-s read-only` may block writes to `$CREW_STATUS` and
  `verdicts/`, which sit outside the worktree.
- **Impact:** Unknown; a reviewer that cannot write `done:` would look silent
  and trip the stale timer.
- **Fix:** Exercise it in the second dry run (#234) before choosing a fix.
- **Status:** open. Not verified; #234 AC 2 covers it.
- **Linked issue/PR:** mw-ding/eng-crew#234
