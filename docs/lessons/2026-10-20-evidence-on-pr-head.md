# Evidence on the PR head, 2026-10-20

Entry format: see [README.md](README.md).

## Evidence a verdict relies on must be on the PR head

- **Date:** 2026-10-20
- **Source / evidence:** PR #12 in this repo: images in the merged PR body broke
  after the side branch holding the evidence was deleted. Requested by the
  reviewer-validator. Related: the off-head evidence stall in
  [2026-10-19-bottlenecks.md](2026-10-19-bottlenecks.md#evidence-that-lives-off-the-pr-head-can-stall-the-review-loop).
- **Finding:** Evidence kept on a side branch is lost when that branch is
  deleted after merge, so images in the merged PR body no longer render.
- **Impact:** broken evidence in a merged PR; no figure given.
- **Fix:** commit any evidence a verdict relies on (screenshots, crops, logs,
  other artifacts) on the PR branch so it is in the head commit; never use a
  side branch. If evidence changes without the code changing, the coordinator
  posts a rereview steer (`steer cmd=rereview`). See
  [protocol.md](../protocol.md#3-evidence-requirements).
- **Status:** documented. The protocol prescribes it; the source does not say
  whether the live box skill carries it yet.
- **Linked issue/PR:** mw-ding/eng-crew#19
