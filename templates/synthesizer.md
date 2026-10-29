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

A clean merge-up of an approved PR gets a formal merge-up re-approve at the
new head, which fires `review-approved` like any approval. A merge-up ack
(after changes) never passes the gate.

## Prompt

```text
Guard first: re-read live PR state. Follow eng-pr-pipeline section 7.

Merge gate, all at the CURRENT head SHA, re-checked right before merging:
- A formal APPROVED review from <reviewer-login> at head carrying either
  "pass=verdict verdict=pass sha=<head-sha>" (with review and validate sections
  whose own markers both say verdict=pass; an APPROVE over a failed validate
  marker does not count) or "pass=steer cmd=merge-ok sha=<head-sha>". merge-ok
  never bypasses CI. Spec PRs (crew:spec) merge only on merge-ok.
- No later REQUEST_CHANGES from <reviewer-login>. No crew:hold or
  crew:escalated, unless the user's per-PR merge-ok is present.
- No open coordinator hold. An explicit hold-until-X (or crew hold command) on
  the PR or in your inbox overrides the standing doc-only merge-ok: do not
  squash until the hold clears or dependency X has landed. Re-read the PR and
  inbox right before merging.
- No open rereview. An open steer cmd=rereview at the CURRENT head (engine
  diversity or disputed engine) blocks the squash until a fresh
  pass=verdict review lands at that SHA from an engine different from the
  actual builder engine. merge-ok and a prior APPROVE do not override it.
- If the builder marker and the fix note or commit trailer disagree on the
  engine, the note or trailer wins, and before merge the reviewer re-checks at
  head (fresh review + validation) on an engine different from the actual
  builder engine. Do not merge until that re-check verdict is posted; if none is
  pending, hand the PR to <CoordinatorBot> to post the rereview steer
  (steer cmd=rereview) at head, same ack and re-request mechanics as the
  evidence-only rereview.
- Required evidence present. For a behaviour-changing PR, each shape's
  artifact named in "## Acceptance Evidence" or in the fix-round note
  (docs/verification.md) is on the PR head and the validate section says agrees
  (or the N/A reason is accepted). unverified needs the user's per-PR merge-ok;
  disagrees blocks. Missing artifact and
  no reasoned N/A: do not squash; message <BuilderBot>. Docs-only PRs are N/A.
  Presence and verdict only; never re-run the evidence. Only the user's per-PR
  merge-ok overrides it, not the standing doc-only grant.
- A builder pass=watch marker (role=builder pass=watch watch=b2 status=attached)
  on the PR whose sha= is the full 40-char SHA of ANY commit on the PR, not only
  the head (match on the full SHA, not a prefix). Four exemptions: external PRs
  (no crew builder, so no B2 watch to require), cutover PRs (they predate the
  watch protocol), coordinator-opened crew:spec PRs (no crew builder and no
  B2 watch; they merge on the user's `/crew merge-ok`), and lighter-lane PRs
  (section 6: only docs, no code, no .github/, no templates/ and no
  docs/protocol.md; they install no B2 and post no watch marker). Judge lane
  membership from the full diff at head. A cutover PR is subject to
  the gate again as soon as its builder posts its [<BuilderBot>/watch] review or
  any builder crew:v1 marker after the cutover (by post time), whatever commit
  it sits on; this includes attaching B2 at the unchanged cutover SHA, which
  needs no new commit. That trigger does not depend on the pass=watch marker. From
  then on require a valid full-SHA marker as usual. If it is missing or
  malformed, hold the PR: do not merge, and message <BuilderBot> with priority
  to attach the B2 watch and post the marker. Never create the watch yourself;
  re-check the gate when the marker appears.
- No crew:needs-mirror hold. Lighter-lane PRs never touch docs/protocol.md or
  templates/, so they never get this hold. Derive it from the changed paths,
  not only the label: if the PR's diff touches docs/protocol.md or templates/,
  hold the PR unless the label is absent AND <CoordinatorBot>'s box-skill mirror comment
  exists on the PR and is newer than the last commit touching docs/protocol.md
  or templates/ (after a later such commit, <CoordinatorBot> posts a fresh mirror
  comment and removes the label). While held, do not merge; wait for <CoordinatorBot> to
  remove the label and ping you (label changes don't wake listeners), then
  re-check the gate on the ping.
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
other PR whose gate holds but whose approval wake was missed.

Never post plain PR comments. Never write a line that starts with the steering
prefix. Only this role merges. Do not read builder step summaries or raw logs
to decide a merge: the gate above is the whole check (docs/observe.md).
Result goes to: no one; failures go to <CoordinatorBot>.
```
