# Synthesizer routine: merge on approval

Owner: `<SynthesizerBot>`. One standing routine per repo, no per-PR watch.

## Trigger

```json
{
  "type": "github",
  "repo": "<owner>/<repo>",
  "events": ["review-approved"]
}
```

No allowlist, so external PRs are covered. Any approval wakes the synthesizer,
but it acts only if the merge gate holds at the current head.

A clean merge-up of an approved PR gets only a COMMENT ack, which fires no
`review-approved`. No new listener is defined for it. The synthesizer re-checks
that PR on its next wake (its sweep step below also picks up PRs whose gate
holds) and when the stuck-PR sweeper nudges it
([coordinator-stuck-pr-sweeper.md](coordinator-stuck-pr-sweeper.md)).

## Prompt

```text
Guard first: re-read live PR state. Follow eng-pr-pipeline section 7.

Merge gate, all at the CURRENT head SHA, re-checked right before merging:
- A formal APPROVED review from <reviewer-login> at head carrying either
  "pass=verdict verdict=pass sha=<head-sha>" (with review and validate sections
  whose own markers both say verdict=pass; an APPROVE over a failed validate
  marker does not count) or "pass=steer cmd=merge-ok sha=<head-sha>". merge-ok
  never bypasses CI. Spec PRs (crew:spec) merge only on merge-ok.
- Merge-up exception: if the head is a merge commit (a clean merge-up of
  <default-branch>, for example from the update-branch sweep below), the gate
  also passes with a "<ReviewerBot>/ack" review at <head-sha> (marker
  "pass=ack sha=<head-sha>") saying "verdict stands", provided the merge
  commit's first parent carries an APPROVED "pass=verdict verdict=pass" marker
  whose review and validate section markers both say verdict=pass (an APPROVE
  over a failed validate marker does not count), and nothing else changed: no other commits on top, CI
  green at head, labels OK. An ack saying "verdict pending fix" never passes.
- No later REQUEST_CHANGES from <reviewer-login>. No crew:hold or
  crew:escalated, unless merge-ok is present.
- All required checks green. PR not a draft, mergeable, base <default-branch>.
- Issue linked ("Closes #<n>", or "Refs #<n>" where the repo forbids closing
  keywords), unless the PR is a spec, external or cutover PR. Never auto-close
  an umbrella issue.

If the gate holds: take <state-dir>/<owner>__<repo>/locks/merge.lock (flock,
serial merges) and run
  gh pr merge <n> --squash --match-head-commit <head-sha>
with GH_TOKEN=$(gh auth token --user <author-login>). If the head moved, stop.
Post "[<SynthesizerBot>/merge]" as a COMMENT review, release the lock.

Then sweep open crew PRs: behind but mergeable ones get GitHub update-branch
(merge commit, never rebase) and a "[<SynthesizerBot>/merge-up]" COMMENT
review. PRs with real conflicts go to <BuilderBot> by message. Also pick up any
other PR whose gate holds but whose approval wake was missed, including a PR
whose merge-up ack has landed since its update-branch.

Never post plain PR comments. Never write a line that starts with the steering
prefix. Only this role merges.
Result goes to: no one; failures go to <CoordinatorBot>.
```
