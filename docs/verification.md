# Verification protocol

Typed runtime evidence as a merge gate. A PR that changes behaviour attaches
evidence that matches the kind of software it changes, the reviewer-validator
checks that evidence against the claim, and the synthesizer does not squash
when required evidence is missing. This closes the "prove it" gap: a verdict
on diff and CI alone does not show the change works.

This doc extends [protocol §3](protocol.md#3-evidence-requirements). The
evidence rules there still apply: evidence is committed **on the PR branch**,
never a side branch, and the PR body is written once and never edited.

A proposed move to inline-only evidence is in
[Inline-only evidence (design, owner decision pending)](#inline-only-evidence-design-owner-decision-pending).
It is not a rule yet: until the owner approves it and its build PR lands, this
doc and protocol §3 and §7 apply as written.

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
  head-SHA permalink, never a link into a side branch. The cell also pastes the
  key output excerpt or embeds the screenshot inline
  ([protocol §3](protocol.md#3-evidence-requirements)).
- For a behaviour-changing PR that adds or changes a user-visible create,
  update or complete (or equivalent) mutation, include the inline
  create→progress→delete snippet required by
  [protocol §3](protocol.md#3-evidence-requirements) (mutation evidence).
  For list delete with cascade, show the child items are gone too.
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

## Inline-only evidence (design, owner decision pending)

Design for [#143](https://github.com/mw-ding/eng-crew/issues/143), part 1 of
2. Nothing here is a rule yet. Protocol §3, the §7 evidence gate, the
[gate registry](protocol.md#gate-registry), `templates/evidence/` and the
builder and validator templates still say evidence is committed under
`evidence/<pr>/`. The build PR changes them once the owner has decided the
five questions below. The interim inline-only rule for #110 roadmap PRs
(recorded on #143 and #111) is unchanged.

**Goal (locked by the owner, 2026-10-29).** No evidence is committed to the
repo. Text, images and video are embedded in the change body or in signed
posts, and the change record is the audit trail. Product trees and their
history carry no review artifacts. What evidence is required (shapes, N/A
rules) does not change; only where it lives.

| Q | Recommendation |
|---|---|
| 1 | Media only as GitHub user-attachments URLs, attached with `gh pr create --attach`. Posts after the change opens have no supported upload path yet: fail open to a text recipe plus the validator's own reproduction |
| 2 | A repro pair: an `sh` block with the exact commands, then a `text` block with the exit code, stdout and stderr |
| 3 | Keep each body or post under 60,000 characters (GitHub's maximum is 65,536). Cut text blocks over 100 lines or 8,000 characters to head and tail, with a pointer to the CI log |
| 4 | Delete `evidence/` from the tree going forward, one cleanup PR per repo, with no history rewrite |
| 5 | The registry row counts evidence embedded in the body or in a builder-signed post at or before head. Who checks it is unchanged; the fail-open (per-change merge-ok for `unverified`) also covers media that cannot be embedded |

Embedding per shape, as proposed:

- **CLI:** a repro pair ([Q2](#q2-validator-reproduction)).
- **API:** a repro pair with `curl`; the output shows the status and body.
- **Service:** a repro pair with the start command, the probe and a log
  excerpt.
- **Web:** an image of the changed view, with route, viewport and head SHA in
  the alt text or the proof cell.
- **Mobile:** an image or a video from a named device or simulator, with the
  build id. A video is a bare URL on its own line.

### Q1. How bots attach images and video

What GitHub offers today (checked 2026-10-31 against `gh` v2.103.3, its
source, GitHub's docs and its published REST API description):

- Since `gh` 2.99.0 (2026-09-01), a repeatable `--attach` flag on
  `gh pr create`, `gh pr edit`, `gh pr comment`, `gh issue create`,
  `gh issue edit` and `gh issue comment` uploads a local file and writes a
  `https://github.com/user-attachments/assets/<id>` URL into the body. If the
  body already references the local path, that reference is rewritten.
  Images (png, jpg, jpeg, gif, webp, svg) become markdown images. Videos
  (mp4, mov, webm) become a bare URL on its own line, which GitHub renders
  as a player.
- Limits: images up to 10 MB; videos up to 100 MB in `gh`, but the server
  applies the plan's video limit (10 MB on GitHub Free); at most 50 files per
  call; github.com and GitHub Enterprise Cloud only, not Enterprise Server;
  the uploader needs write access. Each upload is tied to its repository, so
  media from a private repo stays private.
- `gh pr review` has no `--attach`, and `gh` has no standalone upload
  command. The upload endpoint `gh` uses is not in GitHub's published REST
  API.
- Data URIs are stripped by GitHub's renderer.

The crew's write rules leave one of the six commands. Bots never post plain
conversation comments ([§4](protocol.md#4-marker-conventions)), which rules
out `gh pr comment`, and never edit the body
([§3](protocol.md#3-evidence-requirements)), which rules out `gh pr edit`.
That leaves `gh pr create --attach`, used when the builder opens the change.

**Recommendation.**

1. Text evidence for the CLI, API and service shapes, and logs, is always a
   fenced block ([Q2](#q2-validator-reproduction)). It needs no upload.
2. Media counts only as a GitHub user-attachments URL. The builder attaches it
   when it opens the change: the body file references the local file
   (`![/settings at 1280x800](./settings.png)`) and the command passes
   `--attach ./settings.png`.
3. Media for a post after the change opens (a fix-round note or a validation
   section) has no supported upload path yet. Fail-open: the post says what
   the media would show and gives the capture recipe (route or screen,
   viewport or device, head SHA, command). The validator reproduces it and
   records what it saw itself. If it cannot reproduce it, the criterion is
   `unverified` and needs the user's per-change merge-ok. Once `gh` or the API
   can attach to a review, the bots use it with no rule change, because the
   rule names the host, not the tool.
4. Builder runtimes need `gh` 2.99.0 or later. With an older `gh` or on
   Enterprise Server, the same fail-open covers the body.

| Option considered | Why not |
|---|---|
| Long-lived evidence branch, linked by SHA permalink | Keeps files out of `main`, but they still live in the repo, against the locked goal, and a clone still fetches them. One deletion of the branch breaks every link, and the current plan cannot protect the branch ([merge enforcement](merge-enforcement.md)). The SHA-pinned image links in this private repo's PR #12 broke once their branch was deleted, although the commit still resolves through the API today |
| Commit on the change branch, delete it before merge, link by SHA | Moves the head twice (two CI runs, two review wakes), leaks into `main` if the delete is forgotten, and carries the same PR #12 risk |
| Call the upload endpoint directly with `gh api` for review posts | `gh` calls it with the same credential, but the endpoint is undocumented and the `gh` maintainers scoped the feature to `gh` itself; a crew script would also handle the token. The owner may opt in as an interim step; the fail-open stays |
| `gh pr comment --attach` or `gh pr edit --attach` | A plain comment wakes the steering dispatcher; a body edit re-runs CI and re-wakes review |
| Release assets | Private-repo assets do not render inline, and they would crowd the Releases list the R1 workflow publishes to |
| Gists, data URIs, any non-GitHub host | A secret gist is readable by anyone with the URL, and `gh gist` refuses binary files; data URIs are stripped; other hosts are not allowed |

### Q2. Validator reproduction

CLI, API and service evidence becomes a **repro pair**: an `sh` block with
the exact commands, which GitHub's copy button copies ready to run, and right
after it a `text` block with what they print. It is the
[CLI adapter](../templates/evidence/cli-exit-stdout.md) fixture moved from a
file into the body:

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
  format and diffs it against the `text` block, ignoring only the named
  scrubbed and volatile fields. It records `agrees`, `disagrees` or
  `unverified` with its own excerpt, as today.

Considered: a single `$`-prompt transcript block, today's `## Test Output`
style. It stays fine for `## Test Output`, but its copy button copies prompts
and output together, and a multi-line command is ambiguous. A machine-readable
fixture (JSON or YAML) is hard to read in review, and no tool needs one yet.

### Q3. Size limits

GitHub rejects a PR body, comment or review body over 65,536 characters.

- **Budget:** keep each body or post under 60,000 characters, so the
  signature and the marker always fit.
- **Truncation:** cut a text block over 100 lines or 8,000 characters. Keep
  the command, the lines that show the claim, and the end with the exit code,
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

Considered: failing a change whose evidence is over the limit (some real
output is long, and the excerpt plus a re-runnable command is enough), and
attaching full logs as files (`--attach` takes only images and video).

### Q4. Existing committed evidence

Snapshot on 2026-10-31 (the tree at each repo's `HEAD`): `todo` has 123 files
(4.1 MB), `smart-home` 11 (49 kB) and `eng-crew` 3 (1 kB, `evidence/84/`).
Among merged PR bodies, only `todo` links to `evidence/` files: 55 links in 5
PRs, all pinned to PR-branch commit SHAs that are not on `main` (so deleting
the files on `main` does not affect them), and 2 relative links in one PR.

**Recommendation:** delete `evidence/` from each tree going forward, with no
history rewrite (out of scope). `eng-crew`'s `evidence/84/` goes in the build
PR together with a `check-repo.py` guard that fails when `evidence/` exists.
The guard needs no list of allowed old files. For each product repo, the
coordinator files a cleanup issue, landed as a no-behaviour PR. After that,
a reviewer treats a new file under `evidence/` as a finding. Deleting clears
the tree only: history keeps the bytes. The 2 relative links in `todo` may
stop resolving, but their PRs keep the inline excerpts.

Considered: leaving the files in place and only stopping new ones. That means
no churn, but the clutter the issue is about stays, the old directory invites
copying the old pattern, and a guard would need a list of the old files.

### Q5. Synthesizer gate

The gate keeps its job: a behaviour-changing change does not merge without
required evidence. Only "Satisfied by" changes. Proposed
[gate registry](protocol.md#gate-registry) row for the build PR:

| Gate | Satisfied by | Who / how fast | Fail-open | Binding |
|---|---|---|---|---|
| Required evidence | For a behaviour-changing change, each shape's evidence is embedded inline (a repro pair or a fenced block for text, a GitHub user-attachments URL for media) in `## Acceptance Evidence` or `## Test Output` of the change body, or in a builder-signed fix or ci-fix note whose marker `sha=` is the head or an earlier commit of the change, and the validation section at head says `agrees`; or a reasoned N/A. A path, a link to a repo file or media on any other host does not count. Docs-only and no-behaviour changes are N/A; lighter-lane changes are N/A unless they change behaviour | Builder when the change opens or in a fix-round note; reviewer-validator on `ci-passed`; the synthesizer re-reads the body and posts right before merging (seconds) | User's per-change `/crew merge-ok` for evidence that cannot be produced or embedded (`unverified`, including the Q1 fail-open); standing doc-only merge-ok never covers a behaviour-changing change; owner-decision path for disputes; no waiver of CI | core |

- **Builder-signed:** a narrative post with the builder's signed header and a
  `role=builder pass=fix` or `pass=ci-fix` marker. No new marker field or
  pass value.
- **At or before head:** evidence on an earlier commit still counts as
  present. Whether it still holds at head is the validator's `agrees`. The
  synthesizer checks presence and the verdict only, as today.
- **Late evidence:** evidence added after a verdict without a new commit
  leaves the head unchanged and wakes nobody, so the coordinator posts the
  rereview steer ([§3](protocol.md#3-evidence-requirements), same
  mechanics). Under inline-only this becomes the only late path.
- **Approval:** this is a merge-gate change. The owner approves the build PR
  per change; the standing grant (#111) does not cover gate changes.

The §7 bullet changes the same way: "artifact ... on the change head" becomes
"evidence embedded in the change body, or in a builder-signed post at or
before head".

### Build PR scope (part 2)

- Protocol §3 (inline evidence; "Evidence on the change head" becomes
  "Evidence on the change record"), the §7 bullet and the registry row above.
- This doc: the shape table's "Builder attaches" and "Merge when" columns,
  the duties and the fail-open, with this design section folded in.
- `docs/roles.md` (evidence duties, the PR conventions evidence bullet).
- `templates/evidence/`: the CLI adapter emits a repro pair; the web adapter
  uses `--attach`.
- Grok Bot templates: `builder-b1.md`, `reviewer-validator.md`,
  `reviewer-v2-watch.md` and `synthesizer.md`. This changes live Grok Bot
  behaviour, so the build PR waits for a real mirror.
- Lesson `2026-10-20-evidence-on-pr-head.md` marked `superseded`, plus a new
  lesson; the `evidence/` guard and its test; `evidence/84/` deleted; the
  `evidence/**` row in [deliverables.md](deliverables.md).
- Spec invariant 3 ("Evidence on the change head") and its I3 mentions in
  [concepts.md](concepts.md) and [interfaces.md](interfaces.md). The spec
  edit needs the owner's per-change merge-ok.
