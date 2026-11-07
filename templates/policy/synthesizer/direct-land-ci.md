4. After a direct land under `lone_pr_land = "direct"`, read the merge commit
   SHA and wait for the default-branch push CI run at that exact SHA; never
   the PR-head run or another commit's run. Check all required jobs. On red,
   for the coordinator's blocking fix issue, run
   `$CREW_BIN action report --status blocked --reason 'main red after #<n> <run-url>'`;
   if CI is missing or pending, keep waiting
