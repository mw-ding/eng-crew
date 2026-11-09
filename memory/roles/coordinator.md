# Core memory: coordinator

What the coordinator has learned that should outlive any one session. Change this
file only through a reviewed memory PR (`docs/memory.md`).
One line per entry, each citing where it was decided.

- A researcher request must be a signed coordinator comment on the source
  issue; Riley stops on a request found only in the issue body (#1337
  c6718252033).
- While a cut PR is open, post `hold-until-#<cut issue>` on every PR that
  adds a `changes/unreleased/` fragment, not only next-milestone PRs: a
  fragment landing between the cut's base and its merge fails release
  `validate`. Re-read the PR state before posting a hold; a new PR does not
  wake the coordinator, so check for unheld PRs on every wake (#985
  c6725307534, #1432, #1433).
- Until #1339 ships, after each direct land watch `main` CI at the merge
  commit yourself; the synthesizer is reaped at `pr-merged` (#1339).
- A CI job that fails while downloading its own tool (for example lychee,
  curl exit 22) is a flake: re-run the failed job, never send it to a builder
  and never waive it (#1352).
- Post a signed `pass=flavor` record on every issue you file, before
  dispatch; without one the builder and reviewer fall back to `thorough`
  (#1430, #1432).
