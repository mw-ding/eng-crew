4. After a direct land under `lone_pr_land = "direct"`, read the PR's merge
   commit SHA and wait for the default-branch push CI run at that exact SHA;
   never use the PR-head run or another default-branch commit's run. Check all
   required jobs. On red report
   `$CREW_BIN action report --status blocked --reason 'main red after #<n> <run-url>'`
   for the
   coordinator's blocking fix issue; if CI is missing or pending, keep waiting
