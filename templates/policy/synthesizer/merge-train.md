
- Pre-check: `$CREW_BIN train check <pr>... --project "$CREW_PROJECT"`
  reports gates per PR without a build or writes. Filter `blocked` members;
  resolve every `manual` gate with the step 2 check. Share blockers with
  the coordinator early. This snapshot never replaces the land-time check.
- Pipeline: build N with `--no-wait`, then N+1 with `--after <n> --no-wait`,
  excluding N's members. Prepare while N runs CI or lands; never another
  synthesizer or parallel lands. Collect CI with
  `$CREW_BIN train wait <n> --project "$CREW_PROJECT"`.
  Per crew train: a real predecessor
  stop/early close rebuilds N+1 with a new number and current main; read the
  new record, never land the old one. A transient pause preserves N+1/CI.
  Never build `--after` on a predecessor with `ci=fail`, even if still open.
  Land N+1 only after N finishes, under the same serial land lock.
- Build: `$CREW_BIN train build <pr>... --project "$CREW_PROJECT"`, in
  `Depends on` then approval order. Read `member`, `dropped`, `deferred`,
  `ci-link`, and `train n=<n>` (`local=` / `ci=`). Copy `train-report` to
  `$CREW_STATUS` with members, landed, dropped reasons and stop cause.
  PRs sharing paths stay together in input order; only a real merge conflict
  drops one (`reason=conflict`). Supply only ready candidates whose
  dependencies permit that order.
  `no-verified-base` / `status=reviewer`: coordinator requests a fresh `base=` verdict.
  Local checks default to `local=skipped`; `--local` or
  `train_local_checks = true` opts in. They are not a merge gate; green train
  CI remains required. The draft train PR is CI only: never merge it.
- Land only on `ci=pass`, holding the step 3 land lock across members.
  For each `member` line in order, immediately before landing, re-run the
  WHOLE step 2 §7 check at its
  tested head, including profile, manual and inbox gates. `train land` checks
  tested-with-default-branch against the train's tested state; it never
  substitutes for your full check. Then run
  `$CREW_BIN train land <n> <pr> --project "$CREW_PROJECT"`, adding
  `--mirror-deferred` only for a member covered by the verified profile deferral.
  It posts the merge record with `Land rule: train of <n>`; append
  `done: #<pr> <head-sha>` per `landed` line. UNKNOWN or transient API errors
