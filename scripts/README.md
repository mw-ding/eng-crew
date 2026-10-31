# Scripts

Repo guard for the spec's hard requirements (R1 no secrets, R6 CI green).
Python 3 standard library only; no dependencies. The guard needs no network;
`metrics-refresh.py` calls the `gh` CLI (read-only).

| File | Purpose |
|---|---|
| `check-repo.py` | The guard: secret scan, required docs/sections, relative links, crew marker SHAs, optional name denylist, deliverables manifest coverage |
| `required-docs.txt` | Single config of required files and sections |
| `deliverables.txt` | Deliverables manifest: the machine-readable copy of the `docs/deliverables.md` inventory, one `glob<TAB>class<TAB>runtime` row per line |
| `test-check-repo.py` | Tests: bad fixtures per pattern, a good fixture, fence/link/section/file-selection cases, denylist hit/miss/unset with a temp denylist, deliverables match/unclassified/double match/bad row/missing manifest in temp git repos and the current tree |
| `metrics-refresh.py` | Refreshes the crew PR metrics artifact in `docs/metrics/` via the `gh` CLI (see [../docs/metrics/README.md](../docs/metrics/README.md)); not run in CI |
| `test-metrics-refresh.py` | Offline self-test for the metrics parsing logic |
| `metrics-decide.py` | Evaluates the metrics-to-decisions sensors on `prs.csv` (rollup and per repo) and prints a markdown report plus `VERDICT:`; exit 0 OK/INSUFFICIENT, 1 TRIP, 3 FOLLOW-UP, 2 usage error. Pure computation, no network; coordinator runs it (see [../docs/metrics/decisions.md](../docs/metrics/decisions.md)); not run in CI |
| `test-metrics-decide.py`, `fixtures/metrics/` | Offline tests for `metrics-decide.py` on fixture CSVs: OK, latency trip, rework trip (rework vs reopen rate), reopen-only, bad tuning flags, per-repo trip that leaves the rollup alone, empty baseline; run in CI |
| `fixtures/bad/`, `fixtures/good/` | Synthetic scan samples (see below) |
| `step-summary.py` | Helper that appends one structured step line to a run's `summary.md` (see [Step summary helper](#step-summary-helper)) |
| `test-step-summary.py` | Fixture test for the helper: format, truncation, redaction; run in CI |
| `intake-sweep.py` | Prints draft intake candidate cards for blocked or stale open PRs from `gh pr list` JSON (see [Intake sweep](#intake-sweep-weekly-stuck-pass)). Offline, print-only; not run in CI |
| `test-intake-sweep.py` | Offline unittest for the intake helper on a built-in fixture; run in CI |
| `crew-config.py` | Profile validator: `validate <file>` checks a `crew.toml` against [../docs/profile.md](../docs/profile.md); `resolve` merges the config layers with per-key provenance (see [Profile validator](#profile-validator)) |
| `test-crew-config.py` | Offline unittest for the validator (valid profile, missing key, unknown concern and backend, token-shaped value, wrong type) and the resolver (layer precedence, merge rule, dropped invariant key, cross-key checks, pack manifest folding with unsupported and undeclared operations); the default profile and GitHub pack manifest validate, cover every concern with no `unsupported` capability, and match the roles.md routing; run in CI |
| `crew-render.py` | Renderer: resolved profile plus render inputs to role briefs and runtime artifacts, failing closed on an unknown placeholder, missing mapping or unsupported capability (see [Renderer](#renderer)) |
| `test-crew-render.py`, `fixtures/render/` | Golden-file tests for the renderer on a fixture profile and inputs (expected tree, unknown-placeholder failure, missing mapping, unsupported capability), and the real tmux briefs rendered from `profiles/tmux.toml` against `fixtures/render/tmux/`; run in CI |
| `test-render-parity.py`, `fixtures/parity/` | Parity test: the real Grok Bot templates render from `profiles/default.toml` (alone and with the agentconnect example values) to the pre-conversion text; a seeded one-word drift fails; every placeholder has a profile-key row and every operation a command in `templates/backends/github.toml`; run in CI |
| `crew`, `crew-tmux.py` | tmux crew CLI: `crew` is a thin entry point that loads one module per command from `crew.d/<cmd>.py` in sorted order (`crew --help` lists them), so a new command adds files only; every tmux call goes through the `crew-tmux.py` adapter (see [../docs/runtimes/tmux.md](../docs/runtimes/tmux.md#usage)) |
| `crew.d/_shared.py` | Helpers the commands share: profile resolve and state paths, the harness launch line and window variables (every window gets `CREW_BIN` and the pack's `CREW_SANDBOX_ENV` variable), run removal with the unlanded-work check, the pane stop (SIGTERM then SIGKILL the process group), liveness probe, queue lock and the command loader |
| `crew.d/acked.py` | `crew acked` checks a `crew send` message by the `ack: <msg-id>` line in the window's status file |
| `crew.d/attach.py` | `crew attach` watches a window read-only (or a temporary tiled builders view) |
| `crew.d/dequeue.py` | `crew dequeue` spawns the oldest request `crew spawn` queued beyond the profile band cap |
| `crew.d/down.py` | `crew down` stops a repo's tmux crew (SIGTERM then SIGKILL each pane process group first) |
| `crew.d/drain.py` | `crew drain` prints and empties `wake/queue.jsonl` without losing a concurrent append |
| `crew.d/guard.py` | `crew guard` is the coordinator's Claude Code turn-end guard (a no-op unless `CREW_ROLE=coordinator`) |
| `crew.d/kill.py` | `crew kill` removes a role window with its own worktree (SIGTERM then SIGKILL the pane process group first) |
| `crew.d/land-lock.py` | `crew land-lock acquire` / `release` holds the serial land lock |
| `crew.d/logs.py` | `crew logs` tails a run's step summary |
| `crew.d/poll.py` | `crew poll` turns GitHub state changes into one-consumer wake records in `wake/queue.jsonl` (`ci-passed` and the evidence-only `fix-at-head` carry the round `k`) |
| `crew.d/restart.py` | `crew restart` restarts a dead or missing run once (a builder even after `done:`; `done:` is terminal only for reviewer and synthesizer runs), in its own worktree when it holds unlanded work |
| `crew.d/send.py` | `crew send` messages a role window by reference: a refs-only inbox line and a fixed nudge |
| `crew.d/spawn.py` | `crew spawn` creates a role window with its own worktree, engine, identity and brief, and queues beyond the profile band cap for `crew dequeue` |
| `crew.d/status.py` | `crew status` prints the coordinator's and each run's liveness (alive, dead, missing, ambiguous; a trust or Codex hooks-review dialog on screen is ambiguous) from its pane identity |
| `crew.d/up.py` | `crew up` starts a repo's tmux crew with the coordinator in window 0 |
| `crew.d/watch.py` | `crew watch` is the zero-token watcher that queues wakes in `wake/queue.jsonl` (one-shot `--source` commands cut off at the scan interval, and queue growth from another poller) and exits with one reason line |
| `crew_testlib.py` | Shared fixtures for the `test-crew-<cmd>.py` files: a fake `tmux` on `PATH`, a temp profile, a temp git repo with a bare origin and PR refs, a fake `gh`, fake panes and a fake `ps`; holds no tests |
| `test-crew-acked.py` | Offline tests for `crew acked`: the ack is read from the status file only, and `send --wait-ack` sees a late ack; run in CI |
| `test-crew-attach.py` | Offline tests for `crew attach`: read-only by default, by role, the builders view leaves the layout unchanged, unknown window and missing session refused; run in CI |
| `test-crew-dequeue.py` | Offline tests for the band caps: spawn beyond the cap queues, `dequeue` spawns the oldest request with a free slot after a kill, bands capped separately; run in CI |
| `test-crew-down.py` | Offline tests for `crew down`: kill order and the land-lock refusal, no-op without a session, names windows holding unlanded work, ends a real pane process that ignores SIGHUP and SIGTERM (SIGKILL) for every window; run in CI |
| `test-crew-drain.py` | Offline tests for `crew drain`: prints and empties the queue (an interrupted drain's file first) and waits for an append holding the queue lock; run in CI |
| `test-crew-guard.py` | Offline tests for `crew guard`: decisions, a live watcher, at most one block per stop cycle, malformed input, no-op outside the coordinator window; run in CI |
| `test-crew-kill.py` | Offline tests for `crew kill`: removes only its own run, refuses the coordinator, removes a reviewer's verdict files (a passed review's kept for validate), refuses unlanded work (uncommitted, untracked, local-only commit; pushed or merged work is removed), `--discard --reason` removes and posts the reason, ends a real pane process that ignores SIGHUP; run in CI |
| `test-crew-land-lock.py` | Offline tests for `crew land-lock`: a second acquire fails fast and `down` refuses until release, release signals only the recorded holder (stale or reused PID); run in CI |
| `test-crew-logs.py` | Offline tests for `crew logs`: tails only the newest summary, `-f` execs `tail`, no run or summary refused; run in CI |
| `test-crew-poll.py`, `fixtures/poll/` | Offline tests for `crew poll`: the decision function on recorded `gh` JSON (ci-passed → reviewer, ci-failed → builder, changes → builder, approved → synthesizer, merged → coordinator, no change → nothing; `ci-passed` carries round `k`, reset by a cutover; an evidence-only fix at the verdict head emits `fix-at-head` once) and `poll --once` against a fake `gh` (baseline, one wake record per change, read-only calls); run in CI |
| `test-crew-restart.py` | Offline tests for `crew restart`: only when dead or missing and only once (fresh worktree when clean, relaunch in place keeping unlanded work), a finished run refused, a builder after `done:` restartable; run in CI |
| `test-crew-send.py` | Offline tests for `crew send`: inbox line format, fixed nudge, refs-only and oversized refusals, unknown window refused; run in CI |
| `test-crew-spawn.py` | Offline tests for `crew spawn` against a temp git repo: unique worktree, next free band index, identity by `CREW_IDENTITY` only, reviewer engine ≠ builder engine (no trailer counts as non-Claude), the synthesizer engine ignores the builder engine, review and validate claims and worktrees per round and pass coexist, failed start cleaned up, a dead pane reads `dead` and fails fast, no token in argv, `-e` or files, `CREW_BIN` and the sandbox variable in Claude Code windows, layout pinned, run identity recorded; run in CI |
| `test-crew-status.py` | Offline tests for `crew status` and the probe with a fake `ps`: each probe class (a same-name window probes `missing`), the status table, a trust dialog and the Codex hooks dialog probe `ambiguous`; run in CI |
| `test-crew-up.py` | Offline tests for `crew up`: session created, engine command, brief path (default inputs give the tmux briefs from `templates/`), Stop hook install, idempotent, other runtime refused, a pre-trusted Codex coordinator, `CREW_BIN` and the sandbox variable in window 0, no render chatter, rebuilding `ash` from disk without respawning runs; run in CI |
| `test-crew-watch.py` | Offline tests for `crew watch`: scan with a fake clock (fresh, silent, dead → restart, twice → escalate, status line once; a builder after `done:` flagged when dead, a reviewer's `done:` terminal), exit with a reason line and queue record, PID file, `--source` events, typed wake line only into an idle coordinator, backstop backoff while idle, a never-exiting source cut off as `source-timeout`, a wake on queue growth with no re-queue, a self-queueing source queued once, SIGTERM removing the PID file and saving state; run in CI |
| `changelog-cut.py` | Release helper: `changelog-cut.py <version> [--file CHANGELOG.md] [--date YYYY-MM-DD] [--dry-run]` moves the `[Unreleased]` entries byte for byte under `## [<version>] - <date>` (default today in UTC) and leaves an empty `[Unreleased]`; refuses (exit 1, file untouched) an empty Unreleased, a non-SemVer version (no leading `v`), an existing version and one not greater than the latest. Not run in CI |
| `test-changelog-cut.py` | Offline tests on temp files: normal cut, dry run, CRLF, every refusal, SemVer precedence, date handling; run in CI |
| `release-bundle.py` | Release helper: `release-bundle.py <version> [--out DIR] [--ref REF] [--repo OWNER/REPO]` builds `eng-crew-<version>.tar.gz` (every path at `REF`, default `HEAD`, that `deliverables.txt` classifies `deliverable`, at its repo path under one top-level `eng-crew-<version>/` folder, plus `VERSION` holding `v<version>`) and `SHA256SUMS`. Deterministic: sorted entries, mtime from `SOURCE_DATE_EPOCH` or the commit time, uid/gid 0, no user names. In bundled Markdown a relative link to a tracked path outside the bundle becomes `https://github.com/<owner>/<repo>/blob/v<version>/<path>`, or `raw/` for an image (an `![...]` link or a png, jpg, jpeg, gif, svg or webp file) so it renders inline (owner and repo from `--repo` or the `origin` remote); then an offline link check needs every relative link to resolve inside the bundle. Refuses (exit 1, nothing written) a non-SemVer version, a path the manifest does not classify exactly once, and a dangling link. Not run in CI |
| `test-release-bundle.py` | Offline tests on temp git repos: two builds give identical bytes and `SHA256SUMS`, deliverable-only contents under `eng-crew-<version>/` and tar metadata, `SOURCE_DATE_EPOCH`, link rewriting (inline, image, reference, root-relative; code spans and fences untouched), `raw/` URLs for images, `--repo` over the remote, a dangling link failing the link check, refusals, and a build of the current repo; run in CI |
| `release-check.py` | Release helper: `release-check.py <version> [--file CHANGELOG.md] [--notes OUT] [--tags TAG ...]` passes only when `[Unreleased]` is empty, the top version section is `[<version>]`, `v<version>` is not in `--tags` and is greater than every SemVer tag there; writes that section (the release notes) to `--notes` or stdout, else exit 1. Run by the release workflow (see [Release workflow](#release-workflow)) |
| `test-release-check.py` | Offline tests on temp files: pass and notes, pre-release order, every failure; run in CI |
| `check-skill-drift.py` | Drift check: reviewed docs vs the box skill copies, or rendered output vs the live copy with `--project` (see [Skill drift check](#skill-drift-check-coordinator)). Not run in CI |
| `test-check-skill-drift.py`, `fixtures/drift/` | Tests for the drift check on synthetic fixtures, and for the render-vs-live mode on `fixtures/render/` (match, wording, drift, missing and extra live file, live-dir sources); run in CI without any box files |

## Run it

From the repo root:

```sh
python3 scripts/check-repo.py            # all checks
python3 scripts/check-repo.py --only secrets   # or docs / links / markers / blockers / shapes / denylist / deliverables (repeatable)
python3 scripts/test-check-repo.py       # fixture and structural tests
```

Every problem prints as `file:line: [rule] reason`; the exit code is 1 if there
is any problem, 0 otherwise. CI runs both commands in the `repo-guard` job
(`.github/workflows/ci.yml`) on every pull request and push to `main`.

## What it checks

| Rule | Fails on |
|---|---|
| `github-token` | GitHub tokens with the `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` prefixes |
| `github-pat` | fine-grained tokens with the `github_pat_` prefix |
| `sk-key` | `sk-` style API keys (20+ key characters) |
| `aws-access-key` | AWS access key ids (`AKIA`, `ASIA`, and related prefixes) |
| `private-key` | `-----BEGIN ... PRIVATE KEY-----` blocks |
| `bearer-header` | an `Authorization` header with a literal bearer value |
| `url-credentials` | URLs with a literal `user:password@` part |
| `missing-file`, `missing-section` | an entry in `required-docs.txt` that is absent |
| `marker-sha` | a `crew:v1` marker (also wrapped over lines, also inside fences) in `*.md` whose `sha=` is a literal that is not 40 hex characters, or a placeholder naming a short SHA (`sha7`, `short`). Placeholders like `<head-sha>` and `<40-char head sha>` pass. Encodes the lesson in `docs/lessons/2026-10-23-watch-handoff-first-run.md` (issue #69) |
| `synthesizer-blockers` | `docs/protocol.md` or `templates/runtimes/grok-bot/synthesizer.md` (when present) no longer names the `hold-until` blocker or an open `steer cmd=rereview`. Static presence guard only; live hold and rereview state is not checkable offline. Lesson `docs/lessons/2026-10-29-synthesizer-hold-race.md` (issue #81) |
| `verification-shapes` | `docs/verification.md` (when present) has a shape table without a row whose first cell is each of Web, CLI, Service, API and Mobile. Static presence guard; whether a PR attached the right evidence is judged by the validator. Lesson `docs/lessons/2026-10-29-typed-verify-evidence.md` (issue #83) |
| `denylist` | a whole-word, case-insensitive match of a name from the `CREW_DENYLIST` file in any scanned file (see [Denylist](#denylist)); skipped when the variable is unset |
| `unclassified`, `double-classified` | a tracked path (`git ls-files`) that matches no row, or more than one row, of `deliverables.txt`. Globs: `**` matches across `/`, `*` and `?` stay inside one segment. A bad or missing manifest fails as `deliverables-config`; outside a git work tree the check is skipped. Issue #235 |
| `broken-link` | a relative markdown link (or image) whose target file does not exist, or that points outside the repo |

Every file is scanned for secrets (binary files are skipped). In a git work
tree (the repo root is the top level) the file list is `git ls-files`, so
everything tracked is scanned, including a tracked `node_modules/`, and an
untracked or ignored directory such as a local `node_modules/` is not; `git add`
a new file for local runs to see it (CI only has tracked files anyway). Outside
a git work tree (or if `git` fails) every file except `.git/` is scanned.

Token patterns use alnum-only boundaries, not `\b`, so a token wrapped in `_`
(Markdown emphasis, such as `_ghp_<36 chars>_`) is still caught. Git history is
not scanned.

Links are checked in `*.md` files; `http(s):`, `mailto:` and fragment-only
links are ignored. Fragment (`#anchor`) checks stay with the `links` CI job
(lychee). Destinations are URL-decoded (`other%20file.md`) and may contain
balanced parentheses (`other(v1).md`) or be written as `<other file.md>`.

Code fences follow CommonMark. A fence opens with 3+ backticks or tildes (up to
3 spaces of indent), also after list markers (`-`, `*`, `+`, `1.`, `1)`, nested
to any depth) and block-quote `>` prefixes, and closes only on a fence of the
same character, at least as long as the opener, with nothing but whitespace
after it (inside a list item or quote the closer may be indented as far as the
content). Fenced lines are skipped by the link check, and a heading inside a
fence never satisfies a required section.

Safety rule for stray fences: CommonMark runs an unclosed fence to the end of
the file, which would let one unrecognised opener (or a lone closer of a fence
the scanner did not see) hide every later link. So for the link check an
unclosed opener is treated as plain text: nothing after it is skipped. The
section check stays strict and fails closed instead: a heading after an
unclosed fence does not count, and the `missing-section` message names the
line of the unclosed fence. The only way a fence hides lines is therefore a
recognised opener with a matching closer, and a fence the scanner opens that
CommonMark would not (for example inside an indented code block) can hide only
the lines up to its closer.

Inline code spans are skipped: a backtick run closes at the next run of the
same length, a backslash-escaped backtick is literal, and an unmatched run is
literal (the text after it is still checked). HTML comments (`<!-- ... -->`,
also across lines; an unclosed one runs to the end of the file) never satisfy a
required heading; links inside comments are still checked.

Known limits:

- A link split across lines (`[x](` then the destination on the next line) and
  a reference definition whose destination is on the next line are not checked.
- Code spans are matched within one line; a span that wraps lines is not
  skipped, so a link inside it is checked (this can only add findings).
- A fence or comment marker inside an HTML comment is not understood: a lone
  fence line in a comment is read as a fence opener (an unclosed one is
  harmless for links but makes the section check fail closed).

## Denylist

Portable spec P6: eng-crew never names an organization's internal tools
([docs/packs.md](../docs/packs.md#direction-rule)). The names themselves are
never committed here. Keep them in a file outside the repo, one per line
(`#` comments and blank lines are ignored), and point `CREW_DENYLIST` at it:

```sh
CREW_DENYLIST=<path-to-denylist> python3 scripts/check-repo.py --only denylist
```

A hit prints `file:line: [denylist]` with the denylist line number, never the
name, so CI logs do not leak it. Matching is case-insensitive and whole-word
(`\w` boundaries): an entry inside a longer word does not match. With the
variable unset the check is skipped (a note goes to stderr); a set variable
naming an unreadable file fails. CI runs without it today.

## Step summary helper

`step-summary.py` is the thin builder helper for the
[observe protocol](../docs/observe.md). It creates
`.crew/runs/<issue-or-pr>/<run-id>/summary.md` with a header on the first call
and appends one block per call: step, status (`ok`, `fail`, `warn`, `skip`),
duration, a 1-3 line outcome and an optional log path.

```sh
python3 scripts/step-summary.py --ref issue-<n> --run-id r1 \
  --step build --status ok --duration 42 --outcome "built 3 targets"
python3 scripts/step-summary.py --ref issue-<n> --run-id r1 \
  --step tests --status fail --duration 3m04s \
  --outcome-from-log steps/tests.log --log steps/tests.log
python3 scripts/test-step-summary.py
```

The outcome is cut to 3 lines of 200 characters and obvious token patterns
(GitHub and `sk-` keys, AWS key ids, bearer values, URL credentials,
`password=` style pairs) are replaced by `<redacted>`. It never echoes or
copies a raw log; `--outcome-from-log` reads only the last three lines (at most
32 KiB, `TAIL_MAX_BYTES`, read from the end of the file, so a log ending in one
huge line yields only its tail) and resolves a relative path against the run
dir. A relative path that leaves the run dir (`..` or a symlink, checked with
`realpath`) is rejected; absolute paths work as given, the caller's choice.
`--ref` and `--run-id` must match `[A-Za-z0-9._-]+` and not be only dots. The redaction is best effort, not a secret scanner. Standard library only.

## Allowlist: placeholder form only

There is no ignore comment and no path exclusion. A secret-looking value is
accepted only when written as a placeholder, a name in angle brackets:

- `ghp_<token>`, `sk-<key>` (the `<` stops the token pattern from matching)
- `Authorization: Bearer <token>`
- `https://<user>:<password>@host/path`

Anything else, including well-known documentation example keys, fails. Refer to
credentials by mechanism instead (see spec R1).

## Required docs

Edit `required-docs.txt`. One entry per line: `path` requires the file;
`path :: ## Heading` requires that exact heading line (outside code fences
and HTML comments, as defined above).
Blank lines and lines starting with `#` are ignored. Add entries in the same PR
that lands the doc.

## Fixtures

`fixtures/bad/*.txt` holds fake samples per rule (including `_`-wrapped
variants named `*-underscore.txt`), always on line 3, with the
rule id on the `# expect:` line. Each token is stored **defanged**: a `~~`
marker splits the string, so the repo never contains a matching (or
push-protection-triggering) value. `test-check-repo.py` strips the marker into a
temp directory and requires `check-repo.py` to fail with `<file>:3: [<rule>]`.
`fixtures/good/` holds the placeholder forms and must pass.

Because the fixtures are inert, the real scan does not exclude them, and
verifies it by scanning them as ordinary files. Fixtures are `.txt` so
markdownlint and lychee ignore them. Structural cases (missing file or section,
broken link) are built in temp directories by the test, not stored as `.md`.

To add a pattern: add it to `PATTERNS` in `check-repo.py`, add
`fixtures/bad/<name>.txt` with a defanged sample, and extend the table above.

## Skill drift check (coordinator)

`docs/protocol.md` and `docs/roles.md` are the reviewed copies of the box skills
`eng-pr-pipeline` and `eng-crew-roles` (spec R4). `check-skill-drift.py` reports
where they have diverged. It needs the box files, so it is **not** part of CI.

**Who runs it:** the coordinator (Ash), (1) when a PR carries `crew:needs-mirror`,
after mirroring the box skill and before posting the mirror comment, which
must carry the clean result inline
([mirror hold gate](../docs/runtimes/grok-bot.md#mirror-hold-gate)), and (2)
after any merged PR that touches `docs/protocol.md` or `templates/`. A non-zero
exit means the mirror is not finished; fix the box copy (or this repo) and rerun
before removing `crew:needs-mirror`.

```sh
python3 scripts/check-skill-drift.py \
  --pipeline-skill <skill-dir>/eng-pr-pipeline/SKILL.md \
  --roles-skill <skill-dir>/eng-crew-roles/SKILL.md      # add -v for first differing words
```

The paths can also come from `ECREW_PIPELINE_SKILL` and `ECREW_ROLES_SKILL`;
`--only pipeline|roles` checks one pair. The check only reads the files.

What it compares (not bytes, since the skills have frontmatter and box wording):

- `protocol.md` against the pipeline skill, per `##`/`###` section. Text is
  normalized (links, backticks, whitespace). A section is `OK` (identical),
  `WORDING` (text differs, but the key facts match) or `DRIFT` (key facts
  differ). Key facts are single-word code spans (labels, markers such as
  `pass=watch`, event names, flags; spans over 40 characters are skipped;
  placeholders such as `<sha7>` are stripped inside a span) and quantities such
  as `3 rounds`, `40-char` or `5 minutes`, also when written inside a code span.
  `char`/`character(s)` and `min`/`minute(s)` count as the same unit.
  Link destinations (`](#5-rounds-and-escalation)`, reference-style
  definitions) are dropped first, so a link fragment is never a quantity.
  A fact found only as a code span on one side is not reported when the other
  side has the same word unformatted (bold, plain text); link destinations,
  reference labels and reference definitions do not count as that text, so a
  changed fact cannot hide in a URL or `#fragment`. What is reported reads
  "not found in skill/repo", meaning absent from that section (for roles, from
  the whole file); a per-section compare can still list a fact that the other
  file has in a different section. A section only in one file is `MISSING` or
  `EXTRA`. The `Worked example / pilot notes` section and the roles example
  with historical quota percentages are skipped as repo-only
  (`--ignore-heading` adds more).
- `roles.md` against the roles skill, by the same key facts over the whole file
  including the text before the first heading, because the skill's headings do not line up with the reviewed doc.
- `templates/` are not compared: the box skills carry no template copies.

Exit codes: 0 no drift, 1 drift, 2 usage error or a missing skill file (never a
silent pass; also for a file that cannot be read or decoded as UTF-8). Existing drift is a finding for the coordinator, not a bug in the
check. `WORDING` is informational and does not fail.

### Render vs live (`--project`)

```sh
python3 scripts/check-skill-drift.py --project <crew.toml> [--org-profile <path>] \
  [--live-dir <live-dir>]                                # add -v for first differing words
```

Renders the profile with the [renderer](#renderer) (same layers and inputs; for
the default profile, the Grok Bot runtime files that `test-render-parity.py`
covers) into a temp dir and compares each
rendered file with the same relative path under the live copy dir, laid out
like `crew-render.py --out` (`runtime/...`, `briefs/...`). The live dir comes
from `--live-dir`, else `ECREW_LIVE_DIR`, else the profile's `paths.live_dir`
([profile](../docs/profile.md#paths)). Files are compared per section with the
classification above; the text before the first `##` heading counts as a
`(preamble)` section. In the output, "repo" means the rendered file and
"skill" the live one. A rendered file missing from the live copy, a live dir
that is unset, still a placeholder (`<live-dir>`) or absent, and a profile
that does not resolve or render are exit 2; a live file the render does not
produce is `EXTRA` (exit 1). It only reads the live copy; deploying it stays
with the coordinator. Not run in CI.

```sh
python3 scripts/test-check-skill-drift.py   # synthetic fixtures, no box files
```

## Intake sweep (weekly stuck pass)

`intake-sweep.py` is the one live trigger of the
[self-improve intake](../docs/self-improve.md). It reads the JSON that
`gh pr list --json number,title,url,labels,updatedAt,isDraft` prints, from a
file or stdin, and prints one markdown candidate card per open PR that is
labelled `crew:blocked` or has had no update for more than `--stale-days`.
Cards follow [templates/intake-candidate.md](../templates/intake-candidate.md);
Scope defaults to `repo:` with a "(triage: confirm or promote)" hint. Draft PRs
are skipped. Python 3 standard library only; it makes no network call, files no
issue and edits no skill.

```sh
gh pr list --repo <owner>/<repo> --state open --limit 200 \
  --json number,title,url,labels,updatedAt,isDraft \
  | python3 scripts/intake-sweep.py --repo <owner>/<repo>
```

Then the coordinator reviews the drafts and files the keepers as eng-crew
issues. Options: `--stale-days N` (default 7), `--label NAME` (default
`crew:blocked`), `--repo OWNER/REPO` (shown on cards), `--now
YYYY-MM-DDTHH:MM:SSZ` (override the clock). Empty input prints nothing and
exits 0; unreadable input exits 2.

```sh
python3 scripts/test-intake-sweep.py   # offline, no gh
```

## Profile validator

`crew-config.py validate <file>` checks one install-time profile
(`crew.toml`) against the schema in [../docs/profile.md](../docs/profile.md):
required keys, closed tables (unknown keys, concerns, runtimes, backends and
engines fail), types, capability values, and token-shaped values anywhere in
the file. The token check reuses `PATTERNS`, `BEARER`, `URL_CRED` and the
placeholder allowlist of `check-repo.py` (imported, not copied). Python 3.11+
standard library only (`tomllib`); no network.

```sh
python3 scripts/crew-config.py validate crew.toml
python3 scripts/crew-config.py validate packs/github/manifest.toml   # a file with [pack] is a pack manifest
python3 scripts/test-crew-config.py   # offline; also checks the docs/profile.md example
```

Every problem prints as `file:key: reason` (dotted key path); exit 1 on any
problem, 0 otherwise (2 on a usage error).

`crew-config.py resolve --project <crew.toml> [--org-profile <path>]` merges
core defaults, `profiles/default.toml` (if present), the org profile and the
project file, folds each backend's `packs/<name>/manifest.toml` capabilities
under them, validates the result, runs the cross-key checks and prints
`key = value  # layer` per key (`pack:<name>` for a manifest value). Layers, merge rule and checks:
[Layers and precedence](../docs/profile.md#layers-and-precedence).

## Renderer

`crew-render.py` produces role briefs and runtime artifacts from render
inputs and the resolved profile, so the live copy is generated, not
hand-edited ([portable spec P4](../docs/specs/portable.md#2-requirements)).
It resolves the profile in-process with `crew-config.py resolve` (same
layers and checks; a resolve problem is printed as is and stops the run).
Python 3.11+ standard library only; no network.

```sh
python3 scripts/crew-render.py --project crew.toml [--org-profile <path>] \
  [--inputs <inputs-dir>] --out <out-dir>
python3 scripts/test-crew-render.py   # golden files under fixtures/render/
python3 scripts/test-render-parity.py # real templates vs pre-conversion text
```

Inputs layout. `--inputs` defaults to the repo's real input tree,
[`templates/`](../templates/README.md): the Grok Bot templates under
`runtimes/grok-bot/`, the tmux role briefs under `runtimes/tmux/` (14.8,
[#137](https://github.com/mw-ding/eng-crew/issues/137)) and the GitHub command
mapping `backends/github.toml` (13.14, [#126](https://github.com/mw-ding/eng-crew/issues/126)).
It has no `core/` yet, so it renders no `briefs/`; the fixture tree
`fixtures/render/inputs/` has all three parts:

| Input | Output |
|---|---|
| `core/<role>.md`, required for each of `coordinator`, `builder`, `reviewer`, `synthesizer` when `core/` exists | `briefs/<role>.md` |
| `runtimes/<runtime>/**`, only the profile's `runtime.name`; required | `runtime/**` |
| `backends/<backend>.toml`: `[<concern>] <operation> = "<command>"` | substituted for `<op:<concern>.<operation>>` |

Every `<name>` token is a placeholder. Install-time placeholders are
replaced from resolved profile keys (the "Replaces" columns of
[docs/profile.md](../docs/profile.md#keys)):

| Placeholder | Profile key |
|---|---|
| `<owner>`, `<repo>`, `<default-branch>` | `repo.owner`, `repo.name`, `repo.default_branch` |
| `<author-login>` | `identities.<role>.gh_user` of coordinator, builder and synthesizer; they must be equal |
| `<reviewer-login>` | `identities.reviewer.gh_user` |
| `<user-logins>` | `identities.owners`, joined with `", "` so `["<user-logins>"]` becomes one JSON string per login |
| `<state-dir>`, `<worktree-root>`, `<toolchain-bin>` | `paths.state_dir`, `paths.worktree_root`, `paths.toolchain_bin` |
| `<timezone>` | `runtime.timezone` |
| `<eng-crew>`, `<merge-grant>`, `<hold-label-blocks>` | `paths.eng_crew`, `runtime.options.merge_grant`, `runtime.options.hold_label_blocks` (a boolean renders as `true` / `false`) |
| `<fallback-engine>` | `engines.fallback_engine` |
| `<CoordinatorBot>`, `<BuilderBot>`, `<ReviewerBot>`, `<SynthesizerBot>` | `identities.<role>.name` |
| `<op:<concern>.<operation>>` | the command in `backends/<backend>.toml` for the concern's backend; the operation must not be `unsupported` |

Run-time placeholders are kept verbatim, because they are filled per task:
the rest of the [templates table](../templates/README.md#placeholders)
(`<n>`, `<sha7>`, `<head-sha>`, `<k>`, `<pass>`, `<role>`, ...) and
`<issue#>`, `<pr>`, `<tier>`, `<engine>`, `<model>`, `<effort>` from
[docs/roles.md](../docs/roles.md). A test keeps every placeholder in the
templates table known to the renderer, and the parity test keeps every
placeholder in the real inputs in that table with its profile key.

Parity (`test-render-parity.py`): renders `templates/` from
`profiles/default.toml`, alone and layered with the
[agentconnect](../examples/agentconnect/README.md) example values
(`fixtures/parity/crew.toml`), and diffs each `runtime/*.md` against the
pre-conversion template text (`fixtures/parity/pre/*.md.txt`) filled in by
plain string replacement, with trailing whitespace normalized. Any diff fails.
A template edit therefore updates its `pre/` copy in the same PR.

Fail closed: every problem prints as `file:line: reason` and the run exits 1
without writing any file. Reasons: `unknown placeholder <name>`, `unknown
operation <concern>.<operation>`, `unsupported capability
<concern>.<operation>` (the profile's `capabilities` override the pack
manifest `packs/<backend>/manifest.toml`; undeclared is unsupported), and
`missing mapping` (a profile key not set or ambiguous, no command in the
backend file, a missing role brief or runtime binding). On success it prints
each written path and exits 0.

## Release workflow

`.github/workflows/release.yml` (the release gate in the
[protocol gate registry](../docs/protocol.md#gate-registry); design in
[release.md](../docs/release.md#steps)). It never commits: the cut
(`changelog-cut.py`) lands first as a normal crew PR.

- **Dispatch** on `main` with `version` (`X.Y.Z`, no `v`) and `dry_run`
  (default `true`). The `validate` job (read-only) runs `check-repo.py`,
  every `scripts/test-*.py` (render parity included), markdownlint, the
  offline link check and `release-check.py`, and uploads the notes. The
  bundle step is a placeholder until #236.
- **Dry run in CI:** a pull request touching the workflow,
  `changelog-cut.py` or `release-check.py` runs `validate` on a simulated cut
  of `[Unreleased]` as `999.0.0-dryrun`; it never tags or publishes.
- **Publish** runs only with `dry_run=false`, behind the `release`
  environment, and creates the annotated tag `v<version>` on the validated
  SHA and its GitHub Release (pre-release for a `-` version).
- **Owner setup:** create the `release` environment and set the repository
  variable `RELEASE_OWNER` to the owner's login. A private repo on GitHub
  Free cannot add required reviewers to an environment, so as a stopgap the
  publish job refuses unless the run's actor and triggering actor equal
  `RELEASE_OWNER`; with it unset, publish always refuses. Bots that share
  the owner-level account pass that check, so no role approves a pending
  deployment or dispatches with `dry_run=false`.
