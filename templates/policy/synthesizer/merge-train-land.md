  the command re-checks the tested default branch.
  Never close for a transient pause. On a real gate failure, run
  `$CREW_BIN train close <n> --project "$CREW_PROJECT"`; a real `stopped` or
  close ends the train. Append `blocked: #<pr>` with the reason; remaining
  PRs enter a new train or steps 1–4. Copy every `train-report` to `$CREW_STATUS`.
  After completion or a real stop, dropped/deferred PRs are automatically
