# Verification protocol

Typed runtime evidence as a merge gate. A PR that changes behaviour attaches
evidence that matches the kind of software it changes, the reviewer-validator
checks that evidence against the claim, and the synthesizer does not squash
when required evidence is missing. This closes the "prove it" gap: a verdict
on diff and CI alone does not show the change works.

This doc extends [protocol §3](protocol.md#3-evidence-requirements). Evidence
is inline only in the change body or signed reviews; never commit review
artifacts to the repo or an evidence branch. The body is written once and
never edited. The body plus reviews is the durable audit trail.

## Shapes

Pick the shape from what the PR changes, not from the repo. A PR that touches
several shapes attaches evidence for each. Evidence for a shape is **required**
when the PR changes behaviour a user or caller of that shape can observe, and
**N/A** otherwise (with a reason in the PR body or a fix-round note).

| Shape | Required when | Builder attaches | Verifier checks | Merge when | Adapter |
|---|---|---|---|---|---|
| Web | The PR changes a rendered view, route, component or client behaviour | A screenshot (PNG) of the changed view at the head commit, plus the URL or route and viewport, embedded as a GitHub user-attachments URL | The image shows the claimed change at the head commit, reproduces on a fresh checkout, and nothing else in the view regressed | Evidence is inline, named in `## Acceptance Evidence` or a fix-round note, and the verifier's validation section says `agrees` | [web-screenshot.md](../templates/evidence/web-screenshot.md) |
| CLI | The PR changes a command's flags, output, exit code or side effects | An inline repro pair with the command, exit code and stdout/stderr | Re-runs the recorded command at head and diffs stdout, stderr and exit code against the fixture | The inline pair is present and the re-run diff is empty (or the differences are named and justified) | [cli-exit-stdout.md](../templates/evidence/cli-exit-stdout.md) |
| Service | The PR changes a long-running process: startup, config, jobs, queues, health or logs | An inline repro pair with the start command, a health or readiness probe result and the relevant log excerpt | Starts the service at head, repeats the probe, and checks the log excerpt for the claimed behaviour and for new errors | The inline pair is present and the verifier's own run agrees; an unreachable dependency is stated as `unverified` | none yet (use the CLI adapter for the commands) |
| API | The PR changes a request or response contract, status code, auth rule or error body | An inline repro pair with the request (method, path, headers without secrets, body) and the response (status, body) | Replays the request against head and diffs status and body, ignoring volatile fields it names | The inline pair is present and the replay agrees | none yet (use the CLI adapter with `curl`) |
| Mobile | The PR changes app UI, navigation, permissions or device behaviour | A screenshot or screen recording from a named device or simulator build of the head commit, plus the build id, embedded as a GitHub user-attachments URL | The artifact comes from a build of the head commit and shows the claimed change; if the verifier cannot run the build, the criterion is `unverified` | Evidence is inline and the verifier agrees, or `unverified` is resolved by the user's per-PR `/crew merge-ok` | adapter TBD |

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

An unreasoned N/A is missing evidence. The verifier may reject an N/A it
thinks is wrong, as with any criterion.

## Duties

### Builder

- Decide per shape whether evidence is required, using the table above.
- Embed each shape's evidence in `## Acceptance Evidence` or `## Test Output`
  of the body at creation, or in a builder-signed fix or ci-fix review. Name
  the shape, capture SHA and proof label (for example `shape: CLI, R1`).
  Fenced blocks go below the table; the proof cell names their label and key
  output. Images may sit in a cell; video URLs go below the table.
- For a behaviour-changing PR that adds or changes a user-visible create,
  update or complete (or equivalent) mutation, include the inline
  create→progress→delete snippet required by
  [protocol §3](protocol.md#3-evidence-requirements) (mutation evidence).
  For list delete with cascade, show the child items are gone too.
- Evidence added after the PR opens goes inline in a signed fix or ci-fix
  review. With no new commit, the coordinator requests a fresh review at the
  same head as in protocol §3; a COMMENT review wakes nobody by itself.
- Never put secrets, tokens or private data in evidence. Scrub before posting.

### Reviewer-validator

- The validation worker checks the shape and artifact for every
  behaviour-changing criterion in the body and signed reviews, and compares it
  with the builder's claim at the current head. An earlier capture counts only
  when the validator confirms it still holds at head. It reproduces the run
  where the adapter says it can.
- The validation section records `agrees` / `disagrees` / `unverified` per
  criterion as usual. Missing required evidence is `disagrees`, not a nit, and
  the verdict is `REQUEST_CHANGES`.
- The validator checks that the mutation evidence required by
  [protocol §3](protocol.md#3-evidence-requirements) is present inline and
  matches the claim, and reproduces the create→progress→delete run where the
  adapter allows. Missing delete proof (including child items for a cascade),
  or missing or mismatched mutation evidence, is `disagrees` and the
  verdict is `REQUEST_CHANGES`. For an app with no delete endpoint, the
  validator checks the stated no-delete claim. Docs-only and non-CRUD PRs
  are not held to it.
- An N/A is checked for its reason. A wrong N/A is a finding.
- List what was not independently reproduced.

### Synthesizer

- The evidence gate is part of [protocol §7](protocol.md#7-merge-gate-synthesizer)
  and the [Gate registry](protocol.md#gate-registry). The synthesizer does not
  squash a behaviour-changing PR whose required evidence is missing: that is,
  no inline evidence for a shape row above, and no reasoned N/A. A path or
  repo-file link does not count. Builder reviews must have a signed header
  and a `role=builder pass=fix` or `pass=ci-fix` marker whose full `sha=` is
  the head or an earlier commit of the change. Validation is at head or at verified H under
  [verdict portability](protocol.md#verdict-portability-and-delta-re-review).
- The synthesizer checks presence and the formal approval at head, or the
  passing verdict carried from verified H under §7. It does not re-run proof;
  the accepted validation at head or portable H covers it. After a clean
  rebase, proof from the verified change remains eligible even when its
  capture SHA is no longer an ancestor.

## Fail-open

The evidence gate can be satisfied late, never skipped silently:

- If evidence cannot be produced or embedded (no device, a dependency down,
  media upload unavailable),
  the builder says so under `## Risks / Not Done`, and the criterion is
  `unverified`. The user can allow the merge with a per-PR `/crew merge-ok`.
  Standing doc-only merge-ok does not cover a behaviour-changing PR.
- Otherwise the coordinator uses the §6 owner-decision path. CI is never
  waived.
- If the PR changes what an adapter captures, the verifier says so and treats
  the old evidence as stale; the builder posts a fresh inline capture.

## Starter adapters

How to capture and re-check each artifact type is in
[templates/evidence/](../templates/evidence/README.md). Two exist: CLI
exit/stdout and web screenshot. Service and API reuse the CLI one for now.

## Inline embedding decisions (#143)

Decisions Q1–Q5 follow the design in PR #302 and the owner’s locked
inline-only goal. This build applies them; per-change owner merge-ok is
required for this gate change.

### Q1. How bots attach images and video

Media counts only as a GitHub user-attachments URL. At creation use
`gh pr create --attach` (requires `gh` 2.99.0 or later, write access, and
GitHub.com or Enterprise Cloud). Reference the local image in the body file
and pass it with `--attach`; GitHub replaces it with a durable attachment.
Keep captures local and untracked. Never use data URIs, repo-file links,
evidence branches, another host or the undocumented upload endpoint.

`gh pr review` has no supported upload path. For a fix or validation review,
or an older CLI / Enterprise Server, state what the media would show and
provide a capture recipe: route or screen, viewport or device, SHA and exact
command. The validator reproduces at head and records what it saw inline.
This satisfies the media fallback only when the validation says `agrees`;
if reproduction is impossible, mark `unverified` and require the user's
per-change merge-ok. This adds no plain comments or body edits. Once review
uploads are supported, use them with the same attachment-host rule.

Web embeds `![route, viewport, SHA](https://github.com/user-attachments/assets/...)`.
Mobile embeds an image or a bare video URL on its own line, with device or
simulator, build id and SHA beside it. Text rules for CLI, service and API
are below.

### Q2. Validator reproduction

CLI, API and service evidence becomes a **repro pair**: an `sh` block with
the exact commands, which GitHub's copy button copies ready to run, and right
after it a `text` block with what they print. It is the
[CLI adapter](../templates/evidence/cli-exit-stdout.md) fixture embedded in the body:

````markdown
**R1** (shape: CLI, head `<sha7>`, from the repo root)

```sh
python3 scripts/check-repo.py --only shapes
```

```text
exit: 0
--- stdout
check-repo: OK (shapes)
--- stderr
```
````

- One pair per claimed behaviour, for example a success case and a failure
  case. The label before the `sh` block names the shape, head SHA and working
  directory, plus any setup step.
- The `text` block keeps the fixture order: an optional `# scrubbed:` line,
  `exit: <code>`, `--- stdout`, `--- stderr`. A service adds a `--- log`
  excerpt. An API pair uses `curl` with the method, path, non-secret headers
  and body, prints the status, and lists fields to ignore on a
  `# volatile:` line.
- Secrets appear only as variable names (`$API_TOKEN`), never as values.
- A fenced block cannot sit inside a table cell. Pairs go in
  `## Test Output` or directly under the `## Acceptance Evidence` table, and
  the proof cell names the label (`R1`) with a one-line excerpt. An image may
  sit in the cell; a video's bare URL goes below the table.
- The validator runs the `sh` block at head, writes the result in the same
  format and compares it against the `text` block, ignoring only the named
  scrubbed and volatile fields. For truncated blocks, compare the retained
  lines and verify the claim from the full re-run; the omission note is not
  expected command output. It records `agrees`, `disagrees` or
  `unverified` with its own excerpt, as today.

### Q3. Size limits

GitHub rejects a PR body, comment or review body over 65,536 characters.

- **Budget:** keep each body or post under 60,000 characters, so the
  signature and the marker always fit.
- **Truncation:** cut a text block over 100 lines or 8,000 characters. Keep
  the command, exit code, lines that show the claim and the output tail,
  and replace the middle with one line:
  `[... <n> lines cut; full output: <link> ...]`.
- **Pointer:** link the CI job log at the head SHA when the output comes from
  CI; otherwise write "re-run R1 for the full output". Actions logs expire
  (90 days by default), so the excerpt in the body is the durable record and
  the log only a convenience.
- **Media:** images up to 10 MB; videos up to 10 MB and about 60 seconds, so
  every plan accepts them. Crop to the change.
- Never split evidence across extra posts to get around the limit, and never
  move it into a repo file or a paste host. Truncate instead.

### Q4. Existing committed evidence

Delete `evidence/` from each tree going forward without rewriting history.
This build removes all current eng-crew evidence files and adds the
`check-repo.py --only evidence` guard: a root `evidence/` path fails, including
an empty directory. Product repo cleanup is one separate PR per repo;
the coordinator files those issues. Old history retains its bytes; relative
links may stop resolving, while the existing inline excerpts remain.

### Q5. Synthesizer gate

Presence means inline evidence in the body or a builder-signed fix or ci-fix
review at or before head, plus the validation section's `agrees` at head.
Earlier evidence counts only if that validation confirms it still applies.
The [gate registry](protocol.md#gate-registry) states who checks and when.
Late evidence without a new commit needs the coordinator's rereview steer.
Missing evidence blocks; impossible capture or embedding is `unverified`
and requires per-change merge-ok, never the standing grant or a CI waiver.
