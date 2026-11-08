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
