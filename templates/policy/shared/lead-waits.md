Waits: when an acknowledged inbox id can move only on the owner, a hold
or CI, append `waiting: #<n> owner|hold|ci id=<id>` to `$CREW_STATUS`
(`#<n>` the PR or issue it waits on). The token-free watcher then stops
re-typing that id until the PR's polled state, its hold or its owner ask
changes, or a new handoff arrives; it wakes you on that scan. After a wake,
re-read live state; write the line again if the wait is unchanged. Other
pending ids keep their own retries (60, 120, 240, 480, then 900 seconds);
a line without a listed kind or an acknowledged `id=` silences nothing.
