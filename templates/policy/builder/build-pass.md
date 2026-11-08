   that closes #<n>:
   `<op:change.list-open>`.
   If one exists, adopt it and never open a second PR: check out its branch
   in your worktree, handle it as a fix round (below) for its latest verdict
   findings or red CI, then go to step 5.
2. Read the repo's `AGENTS.md` and the worker brief rules in
   `<mdstack>/docs/roles.md`.
   Pin the toolchain: `export PATH=<toolchain-bin>:$PATH`. Work only in your
   worktree, on a branch `builder/<n>-` plus a short slug.
   Local checks: a build or fix round runs a targeted set before pushing, not
   the full suite: `scripts/check-repo.py` and `scripts/check-changelog-pr.py`
   always (check-repo's `markdown` check is local markdownlint parity); the
   `dev/tests/*/test-*.py` named for each changed script;
   `test-crew-render.py`, `test-render-parity.py`, `test-tmux-briefs.py` and
   `test-crew-bootstrap.py` when templates or fixtures change;
   `test-changelog-cut.py`, `test-check-changelog-pr.py` and
   `test-release-*.py` for a release cut. With a forge-less host in the
   profile, `$CREW_BIN runner run --head <head-sha> -- check-repo test-*.py...`
   may run that set there; it falls back to a local run by itself. A diff
   touching shared plumbing (`environments/terminal/crew.d/_shared.py`,
   `cli/mdstack`, `core/crew-config.py` or `core/crew-render.py`) runs every
   `dev/tests/*/test-*.py` locally, with the parallel runner once it exists. The PR
   Testing section lists the set, why it covers the diff, and that PR CI runs
   the full suite. Red CI still comes back as a ci-red round; CI is never
   waived. A merge-up (a push whose only new commit merges the default branch)
   runs `check-repo.py` and only the tests covering the conflicted files (the
   test named for a changed script; render and parity tests when templates or
   fixtures conflicted); PR CI and the recheck pass cover the rest. The
   merge-up note lists the tests run and why that set covers the conflict.
3. Every commit ends with `Engine: <engine> <model> <effort>`, naming what
   actually ran. Run `$CREW_BIN action heartbeat` (it refreshes the claim
   file's `heartbeat:` line; where it answers `unsupported`, as in a session
   run, edit that line yourself) at least every 5 min and after each commit,
   push and post (§6).
4. Classify full diff paths with `<op:classify.sensitive> --project "$CREW_PROJECT"`
   per protocol `Sensitive class`; with `[[sensitive.content]]` rules, pipe
   `git diff --no-color --no-renames origin/<default-branch>...HEAD` to
   `sensitive --diff` instead. Apply `crew:sensitive` and record matches,
   carrying the issue label too. Re-check after pushes; only an owner's recorded
   classification override may clear it. Open a non-draft PR: `<op:change.open>`, body per §3, written once, never
   edited; label it `crew:in-review`. Evidence is inline in the body.<land-publish>
   A CLI change that only runs against test fakes may use a named test
   command that invokes it and asserts exit, stdout and stderr as its repro
   pair (verification Q2).
