- Red: on `ci=fail`, the train closes without landing. Run
  `$CREW_BIN train bisect <n> --project "$CREW_PROJECT"`: it tests both halves
  on main, recurses on red halves and reports `culprit pr=<pr>`. It records
  culprits as `ci-culprit` drops and rebuilds survivors together on main with
  fresh CI. Copy the original `train-report` to `$CREW_STATUS`; read the
  `remaining=<n>` record and land only on `ci=pass`, using the same §7
  checks and head-bound `train land` calls above. Diagnostic trains never land.
  A green combined retry reports `culprit=none green-on-retry`; a red retry,
  changed head/base or incomplete CI remains blocked. Report isolated culprits
  and unresolved failures to the coordinator; do not compose around them by hand.
  On `ci=timeout` or `local=fail`, collect/fix that failure before bisection.

Do not read step summaries or raw logs to decide a merge. Asks go in
`blocked:` lines, never to the owner here. Never start a line with the
steering prefix.
