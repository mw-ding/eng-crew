---
type: added
issue: 345
pr: TBD
date: 2026-11-08
box-skill: none
---

A run placed on a role host now starts there (multi-device remote run lifecycle). `mdstack spawn` sends the rendered brief, and for a validate pass the PR's review files, to the host's new `spawn` verb, which fetches the head into its mirror without moving mirror refs, adds the worktree and starts the harness in the runner's tmux session, so the run outlives the SSH call. `mdstack kill`, `restart` and `down` act through the host's `kill` and `probe` verbs and keep the worktree guards there: unlanded work is kept and listed unless the owner's discard reason is posted, a restart with unlanded work relaunches in its own worktree, and an unreachable host keeps the run's records. Lifecycle verbs refuse another primary's run. Remote runs count toward the role's pool cap and show their host's liveness in `mdstack status`; remote wakes, messages, partition handling and attach remain #346–#348.
