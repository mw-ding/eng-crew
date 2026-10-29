# Verification protocol

Typed runtime evidence as a merge gate. A PR that changes behaviour attaches
evidence that matches the kind of software it changes, the reviewer-validator
checks that evidence against the claim, and the synthesizer does not squash
when required evidence is missing. This closes the "prove it" gap: a verdict
on diff and CI alone does not show the change works.

This doc extends [protocol §3](protocol.md#3-evidence-requirements). The
evidence rules there still apply: evidence is committed **on the PR branch**,
never a side branch, and the PR body is written once and never edited.

## Shapes

Pick the shape from what the PR changes, not from the repo. A PR that touches
several shapes attaches evidence for each. Evidence for a shape is **required**
when the PR changes behaviour a user or caller of that shape can observe, and
**N/A** otherwise (with a reason in the PR body or a fix-round note).

| Shape | Required when | Builder attaches | Verifier checks | Merge when | Adapter |
|---|---|---|---|---|---|
| Web | The PR changes a rendered view, route, component or client behaviour | A screenshot (PNG) of the changed view at the head commit, plus the URL or route and viewport, under `evidence/<pr>/` | The image shows the claimed change at the head commit, reproduces on a fresh checkout, and nothing else in the view regressed | Artifact is on the PR head, named in `## Acceptance Evidence` or a fix-round note, and the verifier's validation section says `agrees` | [web-screenshot.md](../templates/evidence/web-screenshot.md) |
| CLI | The PR changes a command's flags, output, exit code or side effects | A fixture with the command, exit code and stdout/stderr, under `evidence/<pr>/` | Re-runs the recorded command at head and diffs stdout, stderr and exit code against the fixture | Fixture is on the PR head and the re-run diff is empty (or the differences are named and justified) | [cli-exit-stdout.md](../templates/evidence/cli-exit-stdout.md) |
| Service | The PR changes a long-running process: startup, config, jobs, queues, health or logs | A fixture with the start command, a health or readiness probe result and the relevant log excerpt, under `evidence/<pr>/` | Starts the service at head, repeats the probe, and checks the log excerpt for the claimed behaviour and for new errors | Fixture is on the PR head and the verifier's own run agrees; an unreachable dependency is stated as `unverified` | none yet (use the CLI adapter for the commands) |
| API | The PR changes a request or response contract, status code, auth rule or error body | A fixture with the request (method, path, headers without secrets, body) and the response (status, body), under `evidence/<pr>/` | Replays the request against head and diffs status and body, ignoring volatile fields it names | Fixture is on the PR head and the replay agrees | none yet (use the CLI adapter with `curl`) |
| Mobile | The PR changes app UI, navigation, permissions or device behaviour | A screenshot or screen recording from a named device or simulator build of the head commit, plus the build id, under `evidence/<pr>/` | The artifact comes from a build of the head commit and shows the claimed change; if the verifier cannot run the build, the criterion is `unverified` | Artifact is on the PR head and the verifier agrees, or `unverified` is resolved by the user's per-PR `/crew merge-ok` | adapter TBD |

Mobile is specified in full here so a mobile PR is not exempt, but no device
adapter exists yet. Until one lands, the builder attaches what the table asks
for by hand and the verifier treats a build it cannot run as `unverified`.

## Not required

Evidence is **N/A**, with a stated reason, for:

- **Docs-only PRs** and PRs with no behaviour change (comments, renames, a
  moved file, a test-only change that does not alter shipped behaviour). The
  reason is "no observable behaviour changes".
- A shape the PR does not touch, even if the repo has that shape.
- A change that cannot be exercised at runtime, such as a CI config edit that
  only runs after merge. Say what was checked instead (a dry run, a lint).

An unreasoned N/A is a missing artifact. The verifier may reject an N/A it
thinks is wrong, as with any criterion.

## Duties

### Builder

- Decide per shape whether evidence is required, using the table above.
- Commit each artifact on the PR branch under `evidence/<pr>/<name>.<ext>`
  (`<pr>` is the number the builder knows when it writes the body once: the
  PR number if it is already reserved, otherwise the issue number; use the same
  value in the path and in the body).
- In `## Acceptance Evidence`, name the shape and the artifact path on the
  PR head for each behaviour-changing criterion, for example
  `shape: CLI, evidence/<pr>/build-help.txt`. Use a relative path or a
  head-SHA permalink, never a link into a side branch.
- Evidence added after the PR opens goes in as a new commit and is named in the
  fix-round note; the head moves and review re-runs as in protocol §3.
- Never put secrets, tokens or private data in an artifact. Scrub before commit.

### Reviewer-validator

- The validation worker checks the shape and artifact for every
  behaviour-changing criterion, opens the artifact **at head**, and compares it
  with the builder's claim. It reproduces the run where the adapter says it can.
- The validation section records `agrees` / `disagrees` / `unverified` per
  criterion as usual. Missing required evidence is `disagrees`, not a nit, and
  the verdict is `REQUEST_CHANGES`.
- An N/A is checked for its reason. A wrong N/A is a finding.
- List what was not independently reproduced.

### Synthesizer

- The evidence gate is part of [protocol §7](protocol.md#7-merge-gate-synthesizer)
  and the [Gate registry](protocol.md#gate-registry). The synthesizer does not
  squash a behaviour-changing PR whose required evidence is missing: that is,
  no artifact path on the head for a shape row above, and no reasoned N/A.
- The synthesizer checks presence and the formal approval at head. It does not
  re-run the evidence; the validator's verdict at head covers that.

## Fail-open

The evidence gate can be satisfied late, never skipped silently:

- If the evidence cannot be produced (no device, a dependency that is down),
  the builder says so under `## Risks / Not Done`, and the criterion is
  `unverified`. The user can allow the merge with a per-PR `/crew merge-ok`.
  Standing doc-only merge-ok does not cover a behaviour-changing PR.
- Otherwise the coordinator uses the §6 owner-decision path. CI is never
  waived.
- If the PR changes what an adapter captures, the verifier says so and treats
  the old artifact as stale; the builder commits a fresh one.

## Starter adapters

How to capture and re-check each artifact type is in
[templates/evidence/](../templates/evidence/README.md). Two exist: CLI
exit/stdout and web screenshot. Service and API reuse the CLI one for now.
