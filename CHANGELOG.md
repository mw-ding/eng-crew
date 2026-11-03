# Changelog

All notable changes to this repo are recorded here, in the style of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Every PR adds an entry
(spec R5: date, PR number, summary) and says whether the box skill copy was mirrored (spec R4). See
[CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

## [4.0.0] - 2026-11-03

### Added

- Route express changes (X5, the switch in `docs/express-lane.md`). `crew poll` resolves the express lane the way `crew train` does (`crew:express`, the item record and class rules; an unreadable resolution runs the crew lane). For an express change it emits no `new-head` or `fix-at-head`, emits `ci-passed` only with a builder selfgate pass at head (or one carried by a `merge-up` that poll now recognises from the selfgate pass at the previous head), and emits the new `selfgate-passed` event to the synthesizer when a selfgate pass lands with CI green. When the change falls back to the crew lane, poll emits `new-head` at its head so normal review starts. `crew route` never starts a reviewer pass for an express change, so the reviewer lead skips any queued review, and the tmux coordinator brief routes express `ci-passed` and `selfgate-passed` to land, sends `ci-red` without holding, and hands review back on fallback. A synthesizer gate-status block that only waits on `selfgate` (with `ci`, `review`, `validation` or `train`) is now recorded without a coordinator wake, since `selfgate-passed` wakes it. (issue #672, PR #711, 2026-11-03) Box skill copy: deferred (tmux mirror deferral; Grok Bot runs express items in the crew lane).
- `crew schedule summary` prints one line from the latest scheduler decision: busy workers against each pool's cap, the target, the machine signals, queued demand by kind, deferrals by reason and orphans (live tool sessions of closed-item runs or of unrecorded crew windows) with their process ids. `crew watch` prints that line after every exit line, and finishing work (classes 1–6) deferred for `stuck_after` seconds (new profile option, default 1800) sends one `schedule-stuck` wake with the item, its reasons and the latest snapshot. Deferrals themselves never wake the coordinator. (issue #628, PR #706, 2026-11-03) Box skill copy: none (tmux only).
- Add the express gate to the tmux synthesizer and `crew train`. `crew train` resolves a `crew:express` change by program: the newest signed coordinator item record on its one linked issue must resolve `express` (`item-flavor.py`, with the issue and PR labels), and no changed path, both rename paths, may match a tightening class (`class-flavor --express`). Only a change resolved express takes the latest builder `pass=selfgate verdict=pass` at head (checked with `crew-precheck.py --pass selfgate`) in place of the formal approval; any other change, labelled or not, needs the crew-lane verdict. `build` carries an express member by its selfgate record's `base` and `sha` and drops an unreadable one (`express-unreadable`); `check` reports the selfgate result and an `express` gate (crew lane, unreadable resolution, or `crew:spec` without merge-ok block); `land` re-resolves at head and stops on a missing or stale record; the merge record names `pass=selfgate`. The synthesizer brief's step 2 names the express approval, with doc pointers shortened to keep the brief inside its size budget headroom. (issue #673, PR #705, 2026-11-03) Box skill copy: deferred (tmux mirror deferral; Grok Bot runs express items in the crew lane).
- Add the express self-gate loop to the tmux builder brief. On an express change (the `express` item record plus `crew:express`, resolved by `class-flavor --express`), the builder writes a self-gate brief in `.crew/`, runs a fresh read-only review sub-session on the `selfgate_engine` mode's engine with the protocol §3 review rubric and the adapter's code-review skill, fixes findings until a pass or `caps[0]`, posts the `pass=selfgate` record and checks it with `crew-precheck.py --pass selfgate`, and falls back to the crew lane on a capped open finding, a new sensitive or tightening match, or the owner's ask. The renderer fills `<flavor-selfgate-engine>` from `flavor.selfgate_engine` (default `different`), and harness adapters gain a code-review skill field (Claude Code `code-review`, Codex `codex review`; none declared for Pi, Cursor and Muse). (issue #671, PR #704, 2026-11-03) Box skill copy: deferred (tmux mirror deferral; Grok Bot runs express items in the crew lane).
- `scripts/metrics-refresh.py` adds the express-lane metric columns to `prs.csv` and `prs.md`: `lane`, `selfgate_mode`, `selfgate_reviews`, `selfgate_findings`, `dispatch_to_merge_min`, `ci_red_rounds` (every lane), `merge_ups` and `reverted`. The metrics README defines each field. Offline tests cover every column through a fake `gh`. (issue #675, PR #697, 2026-11-03) Box skill copy: none.
- Add `crew-precheck.py --pass selfgate` for express changes. It reads the latest signed builder `pass=selfgate` record at the full head SHA, rejects a malformed record (exact field set, full `base`, `round=n/a`, `pr` matching the PR, `reviews` from 1 to the express cap, `open` at most `findings`), and fails a `changes` verdict, a `pass` with open findings or failed checks, a `mode` other than the profile's effective `selfgate_engine`, and, under `different`, a reviewer engine (before the first `/`; model IDs may contain `/`) that matches the record's builder engine or any commit's `Engine:` trailer. The precheck pass is unchanged. (issue #670, PR #696, 2026-11-03) Box skill copy: none.
- Make release a backend concern. `docs/interfaces.md` adds an optional `release` concern (`cut`, `approve-check`, `record-release`, `notify`), declared in the GitHub pack, mapped in `templates/backends/github.toml` and named in the default profile. An optional `[release]` profile table (`changelog`, `fragments`, `versioning`, `release_id = "tag" | "commit"`) defaults to today's behaviour; with it, `resolve` fails closed unless `approve-check` and `record-release` are kept. The release gate row is backend-neutral with the same satisfaction, and `docs/release.md` gives the GitHub binding (unchanged `release.yml`) plus a commit-hash reference binding covering the version pin, update path and rollback. `scripts/changelog-cut.py` no longer loads `check-repo.py`, takes paths from `--project` or flags, and accepts fragments with only `type`; eng-crew's own cut output is byte-identical. (issue #585, PR #693, 2026-11-03) Box skill copy: none (rendered briefs unchanged; no template uses the release operations).
- `crew brief` prints the `## This run` block (required `Item`, `Pass`, `Base`; optional `Window`, `Round`, `Slot`, `Host`, `Worktree`, `Engine`, `Claim`, `Flavor`, `Comments`) for any runtime or session backend, and exits 2 with no block when a required field is missing. `crew spawn` builds its tmux block with the same helper (output unchanged). The session runtime docs show hosted dispatch with it, and the worker brief rules say a pass does not start without the block. (issue #647, PR #692, 2026-11-03) Box skill copy: pending coordinator mirror.
- `crew schedule decide --pool builder|reviewer` makes the crew scheduler's admission decision under `schedule/lock`. It ranks both pools' demand, grants the caller's items within the pool cap, the target T, the ramp limit and the optional `max_suites`/`max_load` ceilings, and reserves only the caller's grants in `schedule/reservations.json` (they expire after 600 seconds or when a run record appears). The other pool's would-be grants become holds for that walk only: they are dropped as `lead-down` when that pool's lead is down, and otherwise the owning lead gets a backstop nudge. Each pool's floor admits its top item past T, the ramp and the ceilings. Every decision appends a snapshot line and its admits, holds and new defers to `schedule/decisions-<yyyymmdd>.jsonl` (7 days kept). `crew schedule release` frees a reservation after a failed spawn. `crew dequeue --ref #N` starts only that queued request, so the lead starts the scheduler's grant instead of the oldest request. The builder lead brief now calls `schedule decide` instead of `crew lead capacity`; the reviewer lead is unchanged until S7. (issue #624, PR #691, 2026-11-03) Box skill copy: none.
- Add coordinator triage for the express lane. `item-flavor.py --labels` checks an `express` record's eligibility: a `crew:sensitive` or `crew:spec` item needs a whole-line `Owner override:` quote in the record, a `crew:solo` item never qualifies, and a missing `--labels` fails closed. An ineligible record resolves to the default with status `express-ineligible`, its `blockers`, and exit 1. `templates/triage-flavor.md` adds the express steps: sensitive classifier first, the check, then `crew:express` only on a recorded express flavor. (issue #674, PR #689, 2026-11-03) Box skill copy: none.
- Add `[runtime.options.launch]` to the tmux profile: `coordinator` (`tmux` or `none`, a preflight-only `crew up`), `roles` (`tmux`, `hosted` or `none`; `crew up --coordinator-only` for one run), `resume` (`fresh`, `ask` or a Claude Code or Codex session id) and `reconcile` (`backend`). With the table absent `crew up` is unchanged; with hosted or no roles it opens only the coordinator window, tagged as before, and starts no lead windows. The control-item ownership read now follows `backends.markers.name`: for a non-GitHub backend, `crew up` records its rendered `markers.read-item` command and the read runs it instead of `gh api`, failing closed to read-only. The tmux runtime doc lists each reconciliation read by backend operation, with a placeholder non-GitHub pack binding. (issue #606, PR #688, 2026-11-03) Box skill copy: none.
- Write the express lane into the protocol. §3 adds express resolution (`class-flavor --express`, tightening and sensitive/spec exclusions, `review = off` only for express) and the builder's selfgate record with its `pass=selfgate` hidden line. §4 adds the `selfgate` pass and the `crew:express` state tag. §7 and the gate registry add the express self-gate, which replaces formal approval for an express change and keeps every other gate. The portable spec §3 records the scoped I1 and I2 exception, and `docs/architecture.md` adds the label and pass rows. Until the routing build issue lands, an express change is still reviewed as usual. (issue #669, PR #687, 2026-11-03) Box skill copy: deferred (tmux mirror deferral; Grok Bot runs express items in the crew lane).
- Team files: one `<config-home>/teams/<team>.toml` holds a crew's team-only settings under `[team]`, with `pack`, `personas` and `accounts` shorthands. Each repo gets a small `[repos.<name>]` section that may set only an allowlist: repo, default branch, precheck, sensitive paths and landing overrides. A project reference `<file>#<repo>` resolves as core < default < org < team < repo. A legacy `crew.toml` resolves byte-identically. `crew up --team <file>` starts one session and coordinator for every repo, with a render per repo under `<state_dir>/<team>/<owner>__<repo>`. docs/profile.md gains a migration note from two `crew.toml` files to one team file. (issue #634, PR #686, 2026-11-03) Box skill copy: none (config tooling and docs; no template changes).
- Packs can extend the rendered briefs without copying `templates/`. A pack's `render/` directory overlays the render inputs per file (`crew-render.py`, `crew bootstrap`, `crew up`, `crew upgrade` and `check-skill-drift.py`). Every `gh` call in the tmux briefs now goes through a backend operation, with new `change`, `state-tags` and `markers` operations; the GitHub render is byte-identical. A backend map can declare extra run-time placeholders with `[placeholders] kept`. `runtime.options.notes.render` appends notes for any role, leads included, at render time, where `size_budget` and the drift check see them. (issue #580, PR #685, 2026-11-03) Box skill copy: none.
- Add the item-only `express` flavor preset (`review = off`, `validation = off`, `merge = auto`) and the `flavor.selfgate_engine` knob (`different` by default, or `same`). The validator rejects `express` as a project, class or custom base flavor, and `review = "off"` anywhere else still fails as `floor F4`. `crew-config.py class-flavor --express` applies the express knobs unless a path matches a tightening class, and reports `lane` and `tightening`. `item-flavor.py` accepts an `express` record that has a `Reason:` line, but never accepts `express` as a default. `docs/flavors.md` adds the preset and the scoped F4, I1 and I2 exceptions. (issue #668, PR #680, 2026-11-03) Box skill copy: none.
- The crew scheduler computes its crew-wide target T in `schedule/target.json`: T starts at the busy count, stays between 1 and the sum of the pool caps, and moves by one at most once per `schedule_interval`, down on any high signal (load, memory pressure, gateway errors) and up when every signal is low and demand waits; unknown signals hold it. A ramp limit counts starts per interval. New profile options `load_high`, `load_low`, `error_high`, `schedule_interval` and `schedule_ramp` are validated. No command calls the target yet; admission is unchanged. (issue #623, PR #678, 2026-11-03) Box skill copy: none.
- Gateway errors now reach the crew scheduler's input `schedule/errors.jsonl`. `crew watch` matches each live run's screen against its harness adapter's new transient-error text (Claude Code and Codex declare it; Pi, Cursor and Muse declare none) and appends each new line, and `crew train land` appends a stop or pause whose reason names HTTP 429, a 5xx or a rate limit. The same text from the same source within 10 minutes counts once. `crew schedule snapshot` already counts the file's last 10 minutes; nothing admits on it yet. (issue #621, PR #667, 2026-11-03) Box skill copy: none.
- The crew scheduler ranks both pools' demand from a schedule snapshot in one list: the eight finish-before-start classes of the scheduling design, then milestone order, `Depends on` critical path (open items waiting, directly or transitively) and age. It is a pure function with no command yet and changes no admission. (issue #622, PR #665, 2026-11-03) Box skill copy: none.
- `scripts/evidence-cli.py` captures CLI, service and API evidence mechanically: a header with proof label, capture SHA and working directory, a copyable `sh` block with optional setup, and the exit code, stdout and stderr in separate sections with scrub notes. Builder briefs now require CLI proof from the helper or the template script, never hand-written, with executable setup and deferred AC evidence in a signed fix review; reviewer briefs make a capture without the header, or one that does not reproduce, one finding with the re-run output. This keeps evidence quality independent of the builder and reviewer models. (issue #652, PR #658, 2026-11-02) Box skill copy: pending coordinator mirror.
- Add a paste-ready coordinator-session brief (`templates/runtimes/session/coordinator.md`) that carries the ownership guard and the runtime handoff outgoing and incoming steps until the session binding exists, and `crew ownership --runtime session`, which checks the record as `session@<runtime.instance>`. This is build issue B of the runtime handoff design. (issue #638, PR #656, 2026-11-03) Box skill copy: none (session template; no Grok Bot routine changes).
- Builders can now catch common markdownlint failures locally without the binary: the new dependency-free `scripts/check-markdown.py` covers MD001, MD003, MD009, MD012, MD018, MD022, MD031, MD032, MD040, MD047 and MD056 (the rules this repo configures and has failed in CI, such as MD018 and MD056). It checks the changed `*.md` files by default (`--all` for every tracked file) and prints `path:line rule message`. `check-repo.py` runs it on every tracked `*.md` file as a new `markdown` check, so the targeted local set and the tmux builder brief pick it up without an extra step. The whole repo passes, and CI's markdownlint stays the authority (`scripts/README.md#markdown-lint`). (issue #644, PR #655, 2026-11-02) Box skill copy: pending coordinator mirror.
- Owner handoff chat commands: protocol §9 now defines `/crew handoff to <runtime-id> [drain | stop] [deadline <minutes>]`, `/crew handoff abort` and `/crew takeover from <runtime-id>`, given in the coordinator chat and recorded with `cmd-id=chat`. On tmux the new `crew handoff to|abort|takeover` re-reads the ownership record, refuses an illegal transition and posts the signed `draining`, `aborted` or `takeover` state on the control item. A drain writes `asks/handoff.json` so the watcher wakes the coordinator at the deadline, and the Stop guard now keeps its normal block while draining so the coordinator sees in-flight runs end. This is build issue A of the runtime handoff design. (issue #637, PR #654, 2026-11-02) Box skill copy: pending coordinator mirror.
- Express lane design doc: an opt-in `express` flavor where one builder builds, self-reviews and tests end to end, and the change lands on green CI with no independent review or validation. It scopes the floor exceptions to `crew:express` changes (F4's verdict post and I1, plus I2 only when the `selfgate_engine` flip is `same`), excludes sensitive and spec items unless the owner overrides per item, and defines the self-gate loop that loads the reviewer rubric in a fresh sub-session, the signed `pass=selfgate` record, the §7 express gate row, tmux routing, trade-offs, per-lane metric columns and build issues. Design only: it adds no rule until its build issues land. (issue #636, PR #651, 2026-11-02) Box skill copy: none (design doc only).
- `scripts/run-tests.py` runs the `scripts/test-*.py` suite in parallel (`-j N`, default the CPU count up to 8), prints per-file durations and the slowest files, shows the output of every failing file and exits non-zero on any failure. CI's `repo-guard` job runs the full suite with it in one step instead of one step per test. (issue #613, PR #650, 2026-11-02) Box skill copy: none.
- `crew schedule snapshot` prints one JSON object with every crew scheduler input from the scheduling design: both pools' pending demand by kind, worker state, reservations, open trains, open milestones and issue dependencies, normalized load, memory pressure on macOS and Linux, local suites, recent gateway errors and each pool's cap. A failed read is `unknown` for that input only. It is read-only and changes no admission yet. (issue #620, PR #642, 2026-11-02) Box skill copy: none.
- Add `crew handoff manifest` and `crew handoff reconcile` with the `templates/handoff-manifest.md` template. The outgoing coordinator's manifest lists open crew items as dependency-closed sets, by reference only, secret-scanned and within one post. Posting re-reads the control item first and posts `offered` only once per handoff id, so a retry never makes a second handoff and nothing is posted after the ack. The incoming side's read-only plan adopts each set, holds a set whose PR head moved, and skips sets it already claims. Tests cover retry, partial and duplicate-ack cases. (issue #211, PR #633, 2026-11-02) Box skill copy: none.

### Changed

- The reviewer lead now admits through `crew schedule decide --pool reviewer` instead of `crew reviewer-pool`'s own capacity check. Before each reviewer spawn, the dispatcher starts the pass only when decide admits its PR, and it releases the grant if the spawn fails. A deferral prints `crew: reviewer admission deferred: #PR REASON` and the request stays pending. A review held by a builder-lead call is granted on the next reviewer call, and the reviewer floor admits one pass under builder load. The scheduler snapshot now ranks a reviewer `work` event as the pass it starts: a new head, fix at head, merge-up, built PR or recheck escalation as a review, and a passing review as a validation. Before dispatching a stale, dialog or lifecycle wake whose worker has written `done:`, the reviewer lead saves the event as that status wake (line and round), so a review reclaimed through `crew kill` still ranks its validation and a deferral keeps it pending until a later call starts it. `crew reviewer-pool` no longer takes `--suites`. (issue #625, PR #707, 2026-11-03) Box skill copy: none.
- **Breaking:** Validation scope is bounded by default. A new rigor knob, `validation_scope` (`repo` · `bounded`), sets how far the validate pass reaches: `bounded` (every preset but `thorough`) runs the item's acceptance checks and only the checks covering the files changed at head, using the configured `builder.precheck` test command for those paths, and cites green CI at head for the rest. `repo` (thorough, or a custom flavor or class rule) adds the configured repo-wide lint and test commands. The tmux and Grok Bot reviewer briefs render the scope baseline and the configured commands instead of a fixed `scripts/check-repo.py` / `scripts/test-*.py` list; docs/flavors.md adds a validation cost note. Migration: set `validation_scope = "repo"` in a custom flavor or class rule, or `[flavor] name = "thorough"`, to keep the repo-wide validate pass. (issue #648, PR #698, 2026-11-03) Box skill copy: pending coordinator mirror (reviewer templates).
- **Breaking:** An unset project flavor now resolves `standard` (thin review, validation for behaviour changes only) instead of `thorough`, still flagged as `flavor.name = "standard"  # core (unset: flagged)`. Rendered briefs for unset projects now carry the standard `Flavor:` baseline line, and `item-flavor.py`, class matching and class validation use the same default. Item records and class rules still raise rigor; `thorough` stays the preset for releases, security and gate-contract work, and the flavor docs recommend a `thorough` class for gate-defining paths. Unset all of 2026-11-02, validation found problems after a passing review in 2 of 217 rounds (0.9%). Migration: set `[flavor] name = "thorough"` to keep the old behaviour. (issue #632, PR #681, 2026-11-03) Box skill copy: pending coordinator mirror.
- **Breaking:** The release gate now also requires a green `ci.yml` push run at the cut's exact SHA. `release.yml` adds a `ci-gate` job that waits up to 40 minutes for that run and refuses publishing on a red, cancelled, missing or still-pending run; `workflow_dispatch` runs the same check at the dispatched commit. The `validate` job drops its own `check-repo.py` and every-test loop (now 10 minutes) and keeps only release-specific checks; `ci.yml` runs the suite once. `ci.yml` cancels superseded runs only for pull requests and groups `main` runs per commit, so a quick second merge no longer cancels the cut's CI. A publishing run whose actor is not `RELEASE_OWNER` now fails in `prepare`, before validation, naming the fix (dispatch as the owner account, or have the synthesizer merge). Migration: after a CI refusal, re-run CI to green, then re-run the failed release jobs. The release design and gate registry row describe the sequenced gate. (issue #615, PR #677, 2026-11-03) Box skill copy: none.
- CLI evidence for a command that only runs against test fakes (a fake tmux, a fake `gh`, a temp git origin) may use a named test command as its repro pair, when no real-environment run is possible without the fakes. The test must invoke the changed command and assert its exit code, stdout and stderr; the validator re-runs it at head and diffs it like any other pair. The verification CLI row and Q2, protocol §3, the tmux builder and reviewer briefs, Grok Bot B1, the reviewer-validator and V2 watch prompts, and their render and parity fixtures carry the rule. (issue #653, PR #660, 2026-11-02) Box skill copy: pending coordinator mirror.
- `crew train build` keeps approved PRs that change the same paths together in one train, in the dependency then approval order the synthesizer supplies, and drops a member only when its merge actually conflicts (`reason=conflict`). It no longer defers clean overlapping members with `reason=overlap` for a merge-up after the train. Train CI still tests the combined result, so the land gate is unchanged. The tmux synthesizer brief and the crew train docs say the same (crew scheduler design S9, #587). (issue #627, PR #645, 2026-11-02) Box skill copy: deferred to #140 (tmux synthesizer brief only).
- Lead admission is caps only by default: the hard-coded one-minute load gate (`load >= cpus`) is gone and `max_suites` no longer defaults to `cpus // 4`. Two optional gates, both unset by default, defer expansion when reached: `max_suites` on observed local suites and the new `max_load`, a positive number compared with the one-minute load average. A missing load or suite observation defers admission only when a configured gate needs it, and an empty reviewer pool still keeps one slot at a reached gate. This is build issue S1 of the crew scheduler design. (issue #619, PR #643, 2026-11-02) Box skill copy: none (tmux only).
- A release cut PR may carry a release-pipeline fix (`release.yml`, `ci.yml`, `scripts/release-*.py` or `scripts/changelog-cut.py`) without a fragment: `check-changelog-pr.py` recognises a cut diff and instead requires a new entry naming the issue in the new version section. Any other change in a cut, or a non-cut change without a fragment, is still refused. (issue #616, PR #618, 2026-11-02) Box skill copy: none.
- Builders run a targeted local test set instead of the full suite on builds, fix rounds and release cuts: `check-repo.py` and `check-changelog-pr.py` always, the test named for each changed script, render and parity tests when templates or fixtures change, and release and changelog tests for a cut. Diffs touching shared plumbing (`scripts/crew.d/_shared.py`, `scripts/crew`, the config and render cores) still run the full suite locally. The PR Testing section lists the set and its coverage reason; PR CI runs the full suite, and red CI still returns as a ci-red round. AGENTS.md, the tmux builder brief, Grok Bot B1 and their render and parity fixtures follow the new rule. (issue #614, PR #617, 2026-11-03) Box skill copy: pending coordinator mirror.

### Removed

- **Breaking:** Retire `crew lead capacity` and its `--suites`/`--queued` flags: both leads now admit through `crew schedule decide`, and no brief calls it. `docs/scheduling.md` is marked built and records the owner's 2026-11-03 overlap decision (D + S9): builds are not overlap-sequenced, S8 (#626) is closed unbuilt and the `Touches:` triage footprint is dropped, while overlap trains (#627) stay. The tmux binding's Q6, builder lead section and Scaling policy inputs point to the scheduler as built. Migration: call `crew schedule decide --pool builder|reviewer` instead of `crew lead capacity`. (issue #629, PR #709, 2026-11-03) Box skill copy: none.

### Fixed

- **Breaking:** Stop transient GitHub failures from waking the coordinator. `crew poll` retries its PR and issue list reads when one fails with a 5xx, timeout or connection reset (three retries, 1, 2 and 4 s apart) and exits 75 (`EX_TEMPFAIL`) if the failure persists. `crew watch` records a source cut off at `--source-timeout` (now 60 s by default) or exiting 75 as a line in `wake/incidents.jsonl` instead of waking, and sends one `source-failing` wake with the count after `--source-failures` (default 3) in a row; a clean run resets the count. The watcher also re-execs itself in place, before it queues or routes a scan's wakes, when `scripts/crew`, `crew.d/*.py` or `crew-*.py` change on disk, so a crew-home update no longer leaves an old process validating new profile keys (folds in #703). Migration: a wrapper of `crew poll --once` that read exit 1 as any failure should treat exit 75 as a transient failure and retry. (issue #702, PR #708, 2026-11-03) Box skill copy: none (tmux CLI only).
- `crew kill` and idle-builder reclaim no longer report a squash-merged builder worktree as unlanded when the builder's `done: #<issue> #<pr> <sha>` line carries a trailing note. The PR number is now read from a done line with text after the SHA, so the `pull/<n>/head` commits count as landed after the branch is deleted. (issue #695, PR #699, 2026-11-03) Box skill copy: none (tmux only).
- `crew train check` now accepts an inline `sh` + `text` reproduction anywhere in the PR body, such as captures under `## Test Output` that the Acceptance Evidence table references, as well as in signed builder fix or ci-fix reviews at head. Required `evidence/` artifact paths are still read only from the Acceptance Evidence section and those builder reviews, and reviewer or coordinator posts still count for neither. (issue #679, PR #684, 2026-11-03) Box skill copy: none.
- `crew train check` no longer blocks on prefixed paths such as `templates/evidence/cli-exit-stdout.md` or `.crew/evidence/<file>`: only a repo-root `evidence/<path>` counts as a required artifact. The evidence gate reads only the PR body's `## Acceptance Evidence` section and signed builder fix or ci-fix reviews at head, so another role's mention creates no requirement, and it accepts inline reproductions in those reviews and in `~~~` fences. (issue #657, PR #666, 2026-11-03) Box skill copy: none.
- The release workflow's `validate` job timeout is raised from 10 to 25 minutes, matching CI's `repo-guard`. It runs the same full suite, so the v3.2.0 cut's release run was cancelled at the 10-minute limit with no failing test, and the release could not publish. No other workflow job runs the full suite. (issue #610, PR #612, 2026-11-02) Box skill copy: none.

## [3.2.0] - 2026-11-03

### Added

- Added the crew scheduler design (docs/scheduling.md): one crew-wide `crew schedule decide` that both pool leads call, built from observable crew demand, item priority, worker state, machine load, memory pressure, gateway errors and owner presence. It ranks finishing work before new builds, moves a crew-wide concurrency target between load watermarks with a ramp limit instead of on/off gates, keeps one slot per pool so reviews cannot starve, sequences builds that touch the same files, records every admit, defer and reclaim with reasons, and lists eleven follow-up build issues. Design only: admission is unchanged until those land. (issue #587, PR #604, 2026-11-02) Box skill copy: none.
- Add an optional per-role engine override, `[engines.roles.<role>] order = [...]`, for spawned roles. It replaces the tier order for that role's workers (the tier still sets effort), reviewer independence still filters it, and `validate`, `resolve`, `crew doctor` and `crew up` read it. (issue #597, PR #602, 2026-11-03) Box skill copy: none (profile schema and spawn engine choice; no box skill change).
- Add the Cursor harness adapter with interactive launch, coordinator reload and foreground probing, fake-binary coverage and explicit trust, effort and bootstrap gaps. Engine quota and contributor-tier rules still apply. (issue #201, PR #593, 2026-11-02) Box skill copy: none.
- Add a profile-selected local herdr session adapter with background run workspaces,
  read-only observation, verified doorbells and OS-backed identity and process
  cleanup, covered by fake-binary tests. Document backend capability gaps. (issue #203, PR #590, 2026-11-02) Box skill copy: none.
- Muse can launch coordinator, worker and pool-lead sessions through the tmux harness adapter with model, reasoning effort and brief pointers. Versioned foreground processes are recognized at startup, probe and wake; trust and login dialogs remain ambiguous. Private repositories, unreadable visibility and unverified permission modes are refused. Fake-binary lifecycle tests cover launch, completion and cleanup; the adapter records remaining live-session, turn-end guard and bootstrap gaps. (issue #202, PR #589, 2026-11-02) Box skill copy: none.
- Role briefs in both runtimes render project flavor review, validation, evidence, caps, merge and builder values from presets and custom knobs. Optional diff paths apply class rigor at render time; absent flavor remains thorough, with existing precheck settings and owner grants preserved. Live item/path resolution and every merge gate still apply. (issue #351, PR #588, 2026-11-02) Box skill copy: eng-pr-pipeline, eng-crew-roles.
- Pi can launch coordinator, worker and pool-lead sessions through the tmux harness adapter, preserving provider-qualified models, thinking effort and brief pointers. Fake-binary tests cover launch, liveness and cleanup; unsupported approval modes are refused. The adapter documents provider eligibility and remaining live-wake, turn-end guard and bootstrap gaps. (issue #200, PR #583, 2026-11-02) Box skill copy: none.
- Add optional owner-present builder and reviewer limits. Both pools switch admission live between owner-friendly present limits and full away caps, preserve running workers, and honor an optional away bound. Restore the coordinator brief’s owner-away and first-return-message instructions after the merge-up. (issue #577, PR #582, 2026-11-02) Box skill copy: pending coordinator mirror.
- Add `/crew away --cap <n>` to limit concurrent runs while away and `--quiet` to batch notifications while the owner stays present, with the normal SLA clock and every authority gate unchanged. Extend the away record and contract tests. (issue #199, PR #579, 2026-11-02) Box skill copy: pending coordinator mirror.
- Add an away-only Slack notification binding with environment-only webhook credentials, durable event deduplication, bounded retry backoff, progress digest wakes and delivery failure evidence for the return brief. Recorded asks and approvals remain on GitHub. (issue #495, PR #576, 2026-11-02) Box skill copy: deferred to #140.
- Record project flavor in bootstrap profiles and item rigor at triage, with a coordinator contract, signed record template and offline resolver tests for defaults and refused reasonless lowering. (issue #196, PR #575, 2026-11-02) Box skill copy: pending coordinator mirror.
- Add runtime.options.max_active_milestones (integer at least 1, default 1) to both
  runtimes. Coordinator briefs render the limit and prioritize the earliest
  milestone, using later milestones only for spare builder capacity while
  in-flight PRs in any milestone finish. (issue #566, PR #571, 2026-11-02) Box skill copy: pending coordinator mirror.
- Add the solo coding-agent lane, its crew:solo routing label and flavor preset, and a paste-ready session brief sharing the builder PR and fix contract. Builder dispatch and fix delivery skip solo items; independent review, inline evidence, the floor and synthesizer landing remain required. (issue #102, PR #569, 2026-11-02) Box skill copy: pending coordinator mirror.
- Add deterministic path class flavor matching with a JSON CLI, knob-wise strictest rigor, layered class rules, and fail-closed invalid input. Document recorded owner overrides and keep sensitive classification and merge authority separate. (issue #197, PR #568, 2026-11-02) Box skill copy: none.
- Record owner away mode on the project tracking issue, batch notifications while preserving SLA defaults and every authority gate, and send one standalone return brief on the first owner message back. Add steering and coordinator instructions, the return template, and contract tests. (issue #198, PR #565, 2026-11-02) Box skill copy: pending coordinator mirror.
- Validate named thorough, standard and fast flavors, custom knob compositions and class declarations against closed profile tables and the seven floor rules. Check class lowering reasons, caps, resource limits and engine routes; resolve an unset project flavor to thorough with flagged provenance. Runtime gate application remains a separate integration. (issue #195, PR #564, 2026-11-02) Box skill copy: none.

### Changed

- Cut coordinator wake noise from `crew watch`. An idle live lead or synthesizer, with no queued or in-flight work, no longer raises a stale wake. A synthesizer gate-status block that only waits on CI, review, validation or a train now carries `wait=<items>` and is recorded without a wake. `ci-failed` records for a superseded head are dropped by the poller and by route. A lead's `unblocked` message for a block that resolved itself is recorded in the coordinator inbox without a nudge. (issue #578, PR #600, 2026-11-02) Box skill copy: none (tmux only).
- Define change flavor rules for review, validation, evidence, caps and merge permission in protocol §3/§5/§7 and the gate registry. Role templates resolve item/path rigor at head, record justified validation skips and optionally name the effective flavor on verdicts. Existing owner standing grants retain their recorded scope until the renderer migration; grants remain scoped and sensitive/spec gate changes require owner permission. (issue #350, PR #581, 2026-11-02) Box skill copy: pending coordinator mirror.
- Document separate Cursor parent-turn and CLI worker quota meters, diagnostic per-stage wake targets, reference-only handoffs, stable worker sessions and prefixes, and sequential issue lanes unless independence is recorded. Tie cost choices to tier and flavor configuration while preserving all merge gates; defer the quiet-week comparison until metrics data exists. (issue #109, PR #570, 2026-11-02) Box skill copy: pending coordinator mirror.

### Fixed

- CI's `repo-guard` job timeout is raised from 10 to 25 minutes. The suite had grown to about 10 minutes, so main and PR runs were cancelled at the limit with no failing test, and nothing could land. Splitting the job into parallel jobs is left as a follow-up. (issue #607, PR #608, 2026-11-02) Box skill copy: none.
- Verify the Codex coordinator wake path on codex-cli 0.164.0 and fix its turn-end notify recipe: the recipe now pipes Codex's turn payload to `crew guard`, types the wake line with a 0.3 s settle before Enter (a single send-keys left it unsent in the composer), and `crew guard` treats a turn started by its own wake line as already continuing, so it blocks once per stop cycle instead of looping every few seconds. `crew up` still does not install the recipe. (issue #170, PR #605, 2026-11-02) Box skill copy: none.
- `crew dequeue` now decides idle-builder reclaim against the same effective builder pool cap as admission (the owner-present cap, or the recorded-away cap), not the full `builders` cap, so a full builder band with the present cap reached no longer reclaims an idle builder whose slot it cannot use. (issue #598, PR #601, 2026-11-02) Box skill copy: none.
- Stop `crew watch` crashing when a run record is reaped between listing and stat: the scan and `heartbeat()` now skip a record that disappears mid-scan. A watcher started while another live `crew watch` is armed exits 1 without touching its PID file or watch state, and a watcher removes `wake/watcher.pid` on exit only when the file holds its own PID. (issue #591, PR #599, 2026-11-02) Box skill copy: none (tmux only).
- Count only busy builders for admission, reclaim the longest-idle pushed builder with output retained when windows are full, and expire idle builders after a configurable 30 minutes. Stop descendant process groups during cleanup and exclude closed or merged items from lead suite probes, so finished work cannot block new builds. (issue #572, PR #586, 2026-11-02) Box skill copy: none (tmux only).
- Pool leads admit workers while running suites stay below the profile max_suites cap (defaulting to one per four CPUs) and CPU load stays below the CPU count. An empty reviewer pool retains one slot under known load or suite pressure; unavailable observations still defer admission. (issue #567, PR #573, 2026-11-02) Box skill copy: none.
- Retry pending lead admission when any worker finishes and every 60 seconds while requests remain pending. Start delta review and independent validation after a signed builder fix records a resolved merge-up conflict or differing patch at the new head; identical merge-ups retain synthesizer verdict portability. (issue #547, PR #563, 2026-11-02) Box skill copy: none.
- Builder lead records admission deferrals locally and reports only actionable blocks to the coordinator, deduplicating identical notifications across restarts. The router consumes deferred status wakes without coordinator action. (issue #542, PR #562, 2026-11-02) Box skill copy: none.

## [3.1.0] - 2026-11-02

### Added

- Profile validate and resolve support --install to reject unfilled install-time placeholders while retaining the renderer's run-time placeholders and ordinary template validation. (issue #166, PR #556, 2026-11-02) Box skill copy: none.
- Bootstrap proposes missing project profiles from local git config, records owner-confirmed or edited TOML once, and preserves the flavor answer as a comment pending M18. Existing profiles remain authoritative. (issue #191, PR #555, 2026-11-02) Box skill copy: none.
- Projects can record an org pack directory in paths.pack, resolving its optional profile without repeating --org-profile and preserving explicit overrides and layer precedence. (issue #166, PR #554, 2026-11-02) Box skill copy: none.
- Profile validation and resolution accept an explicit external pack manifest declaring a new backend, while retaining capability checks, profile overrides and bundled GitHub defaults. (issue #166, PR #553, 2026-11-02) Box skill copy: none.
- `crew upgrade` previews and re-renders a pinned tmux install, waits for active passes, and restarts roles in place with the coordinator last. Worktrees, claims and inboxes survive; unchanged installs do not restart. (issue #192, PR #545, 2026-11-02) Box skill copy: none.
- Grok Bot renders eng-pr-pipeline and eng-crew-roles skills from the bundle's reviewed docs alongside routines, so deployment and render-vs-live drift checks replace hand mirroring. Budget measurement uses fixed path tokens for included skill links, keeping byte counts independent of the install root. (issue #341, PR #543, 2026-11-02) Box skill copy: deferred to #140.
- Design the single-session runtime binding with explicit C1–C9 contract gaps, harness and worker lifecycle boundaries, attended operation, safe recovery and implementation follow-ups. The proposed `session` profile selector remains unimplemented; bootstrap pointers provide no new runtime capabilities. (issue #340, PR #541, 2026-11-02) Box skill copy: none.
- Long-lived reviewer lead in reserved window 3 owns review, validation, recheck escalation and terminal reclaim through durable serialized handoffs, cap/load/suite admission and one-restart supervision. Replay recovers missing validation and deduplicates fresh passes while preserving synthesizer verdict portability. Failed Actions jobs with no started steps are infrastructure incidents: validation may proceed, but green CI remains required for landing. Scaling, replay and recovery fixtures accompany the change. (issue #531, PR #537, 2026-11-01) Box skill copy: deferred to #140.
- Long-lived builder lead with a reserved session window, durable reference handoffs, cap/load/suite admission decisions, and one identity-checked restart with its inbox and workers preserved. The coordinator hands builder lifecycle to the lead; automatic cross-pool dequeue stops for lead-owned builders. Fixtures cover scaling, replay, restart, ambiguity, and cleanup boundaries. Part of the role-lead split under issue #521. (issue #530, PR #534, 2026-11-01) Box skill copy: deferred to #140.

### Changed

- CI feeds the repository CREW_DENYLIST secret to the repo guard through a private temporary file, without logging its terms, and removes the file on success or failure. (issue #166, PR #557, 2026-11-02) Box skill copy: none.

### Fixed

- Bootstrap measures role brief budgets with install-time path placeholders rendered as a fixed token, so install-path length cannot change the result. Diagnostics and profile/bootstrap docs name the path-normalized UTF-8 byte measure. The tmux coordinator and synthesizer briefs reference the full protocol landing rules instead of repeating them, restoring at least 1 KiB of default-budget headroom. Tests cover short and long roots, UTF-8 boundaries and over-budget rejection. (issue #540, PR #544, 2026-11-02) Box skill copy: deferred to #140.

## [3.0.0] - 2026-11-02

### Added

- `crew train bisect` tests ordered halves of a red train, identifies failing members and rebuilds survivors together on the default branch for normal head-bound landing. Failed predecessors cannot seed `--after`; green combined retries recover flaky trains. (issue #463, PR #526, 2026-11-01) Box skill copy: none.
- Proposed builder and reviewer role-lead contract in the tmux binding: pool authority, durable handoffs, scaling inputs, pass deduplication, and worker/lead recovery. This is the required design review before implementation; current runtime behavior is unchanged, and the builder/reviewer code and fixture coverage remain pending. (issue #521, PR #525, 2026-11-01) Box skill copy: none.
- tmux profiles can configure ordered standing runtime note files per role in `runtime.options.notes`. Each launch appends the current file contents under a heading naming the file; missing or unreadable notes block launch. Worker spawns and coordinator startup load their own notes, and omitted notes leave briefs unchanged. The profile and runtime docs explain configuration, and the coordinator brief uses this option instead of repeated manual policy sends. (issue #492, PR #514, 2026-11-01) Box skill copy: deferred to #140.
- Metrics refresh records builder precheck markers and reports rounds per PR, request-changes verdict rate and mean PR-to-merge time by repo and recorded versus unrecorded precheck cohort. Counts and empty denominators are explicit; unrecorded checks do not establish that the profile switch was disabled. Offline fixtures cover marker parsing, duplicate verdicts, closed unmerged PRs and the CSV/Markdown CLI output. No gate thresholds changed. (issue #183, PR #513, 2026-11-01) Box skill copy: none.
- Gate review, validation and every land on the enabled builder pre-review check:
  require fresh passing or reasoned N/A step results, with only an owner’s
  per-change override. Add a shared marker checker and missing, stale, failed
  and passing fixtures; update reviewer and synthesizer instructions. (issue #182, PR #497, 2026-11-01) Box skill copy: pending coordinator mirror.
- Optional `builder.precheck` profile settings supply lint, test and docs commands
  and a positive fix-attempt limit. Enabled profiles render ordered builder steps;
  disabled profiles retain existing briefs, and missing commands render as `n/a`.
  Validator and renderer tests cover the switch and layered overrides. No merge
  gate change. (issue #181, PR #470, 2026-11-01) Box skill copy: pending coordinator mirror.
- Record today's engineering orchestration roles in `roles/eng.toml`, with a schema validator and equivalence tests for tmux constants, including reviewer recheck and merge-up wakes. The runtime continues using its existing constants (roadmap 15.8). (issue #318, PR #467, 2026-11-01) Box skill copy: none.
- Bootstrap self-test enforces per-role UTF-8 byte budgets for rendered briefs
  and role-owned runtime Markdown files. The optional `size_budget` profile
  table defaults each role to 16 KiB per file; oversized files fail installation
  verification with their rendered path, byte count, role and limit. (issue #194, PR #459, 2026-11-01) Box skill copy: none.
- The tmux runtime detects approved default-branch merge-ups and routes one fresh recheck session to inspect resolution hunks, rerun acceptance checks and post a merge-up re-approve at the new head. Non-mechanical resolutions return to full review and validation; the approval round and merge gates stay unchanged. (issue #454, PR #456, 2026-11-01) Box skill copy: coordinator deploy required.
- Prepare successor merge trains while a predecessor runs CI or lands, with
  `train build --after N --no-wait` and `train wait N`; rebuild a successor
  on current main after its predecessor stops. Landing stays serial and
  head-bound. `train check` reports read-only gate snapshots, with manual
  verification named explicitly. Pairwise merge checks defer likely conflicts
  before a train merge, while clean shared-file pairs stay together. (issue #451, PR #455, 2026-11-01) Box skill copy: tmux brief rendered; live deployment deferred to coordinator.
- Role registry schema (15.7): closed TOML fields and validation contract, worked examples for all four current roles, and the hard-coded migration inventory. Documentation only; runtime migration remains in 15.9 and 15.10. (issue #317, PR #453, 2026-11-01) Box skill copy: none.
- Doctor compares running and installed tool versions from profile-defined read-only probes, checks optional minimum pins, and reports drift with restart or upgrade hints without changing tools. (issue #193, PR #447, 2026-11-01) Box skill copy: none.
- Route mechanical tmux wakes before waking the coordinator: start review and
  validation with head-bound deduplication, clean up terminal role windows and
  dequeue, and close out merged PRs. Keep judgement records for the coordinator,
  prioritize owner replies in its brief, and record the saturation lesson. (issue #434, PR #445, 2026-11-01) Box skill copy: coordinator deploy required.
- Bootstrap now validates and re-renders every role after installation, checks deployed content and target hashes, reruns doctor, and records failed checks. Explicit `--smoke` queues one docs-only pipeline test issue per install after checks pass; dry-run creates no issue. (issue #342, PR #443, 2026-11-01) Box skill copy: none.
- Added bootstrap offboarding with a dry-run and confirmation: pause active crew items, stop the runtime, remove unchanged install targets, optionally remove crew labels, and archive state with a removal record. Unlanded work blocks tmux cleanup; edited targets and leftover worktrees are preserved. Routine removal and access or protection changes remain explicit human steps. (issue #343, PR #436, 2026-11-01) Box skill copy: none.
- Add `crew host check` and `crew hosts` for per-project readiness and live host capabilities, prepared projects, reachability and load. Remote checks use a fixed SSH entrypoint contract for the runner in #208; `--fix` requests safe repairs and reports human steps, while missing logins or an unavailable runner keep hosts unready. (issue #205, PR #435, 2026-11-01) Box skill copy: none.
- Bootstrap can install Claude Code subagent and coordinator skill pointers with the existing Stop hook, and print a Codex launch pointer with per-process trust. Selected harnesses deploy one render, exclude every project target locally and record hashes; tracked or edited targets are refused, and tracked instruction files and home files are never written. Harness selection is forwarded to fetched release bundles; installed pointers and renders participate in the post-apply self-test. (issue #339, PR #433, 2026-11-01) Box skill copy: none.
- Bootstrap can fetch a release with `--version`, verify its SHA256SUMS before extraction, and run it from a separate version directory. Existing bundles and live installs remain protected, rc tags require `--pre`, and an org pack must pin the stable installed tag. The install record retains the verified bundle checksum. Fetching preserves post-apply self-tests and the opt-in smoke request. (issue #337, PR #428, 2026-11-01) Box skill copy: none.
- CI requires a newly added changelog fragment for PR content changes, using
  the PR merge base and a documented exempt path list. Cut output, fragment-only
  changes, verification artifacts and empty diffs pass without a new fragment;
  pushes to main skip the requirement. (issue #421, PR #426, 2026-11-01) Box skill copy: none.
- Merge-train land records include the literal land rule. The tmux synthesizer uses configurable train_min (default 2) and train_window (default 600 seconds), waits only when another PR is close to approval, and lands a single ready PR alone when none is close. (issue #321, PR #425, 2026-11-01) Box skill copy: coordinator render required.
- Publish releases when a CHANGELOG cut PR lands on main, after validating the real cut and verifying the owner's merge-ok at the merged PR head and release actor. Non-cut pushes skip cleanly; dispatch remains for dry runs and approved fallback publishing. Releases attach the bundle and checksums, then notify and close the linked release issue. (issue #387, PR #419, 2026-11-01) Box skill copy: none.
- Add owner-feedback intake with too-slow, too-costly and missed-bug classes,
  owner verification, source links, duplicate checks and normal coordinator
  triage in both runtime bindings. Cards feed future flavor suggestions and
  never apply a flavor or change merge permission. (issue #353, PR #418, 2026-11-01) Box skill copy: coordinator deploy required.
- Add offline flavor suggestions with six feedback signals, tighten precedence,
  metrics-gate and cooldown guards, scope attribution, custom knob steps and
  owner decision defaults. Add the suggestion issue template and coordinator
  triage duty; missing dated defect evidence blocks relaxation. (issue #354, PR #416, 2026-11-01) Box skill copy: deferred to coordinator mirror.
- Profile role personas: identity name, title and emoji keys render into both
  runtime templates, with Ash and a neutral Coordinator title by default.
  Signatures name the harness and model actually used, including fallback;
  marker formats and effort attribution are unchanged. Validator, renderer,
  tests and golden briefs are updated. (issue #187, PR #415, 2026-11-01) Box skill copy: deferred to #140.
- Synthesizer templates now maintain one gate-status review per change listing all unmet merge gates and who owes each item, update it across heads, clear it when satisfied, and wake the coordinator. Gate rules remain unchanged; rendered fixture checks cover the item list and reporting contract. (issue #185, PR #414, 2026-11-01) Box skill copy: coordinator deploy required.
- Added trusted repo-level handoff markers and ownership guards in Grok Bot templates and tmux, keeping non-owners read-only and preventing land while ownership is moving or unreadable. (issue #210, PR #410, 2026-11-01) Box skill copy: deferred to coordinator mirror.
- Metrics refresh adds flavor at the verdict head, escaped defects linked by whole-line issue-body references, and an engine-run proxy from commit trailers and attributed review/validation sections. Coordinator triage and the intake card gain the optional `Escaped from:` source line; unknown flavor and engine attribution stay blank. Offline tests cover the derivation and CSV/Markdown output. No merge gate changes. (issue #352, PR #403, 2026-11-01) Box skill copy: deferred to #140.
- `crew doctor` checks and repairs GitHub repository prerequisites: the runbook's
  crew labels, a confirmed current milestone, a linked Project with four Status
  options, and the reviewer invitation. `--dry-run` prints plans without local
  or remote writes. Namespace collisions stop label repairs, populated boards
  keep their Status options, and CI and branch protection remain human steps.
  Bootstrap passes the new doctor options explicitly for its prerequisite checks.
  Post-apply bootstrap and primary host checks also pass these options, and doctor retains the
  profile's tool drift checks alongside repository repairs. (issue #338, PR #402, 2026-11-01) Box skill copy: none.
- Added crew bootstrap to locate a stable bundle or explicit development clone, resolve the project, preflight with doctor, preview changes, apply on confirmation and record the install. Dry runs write no install, and existing targets must match their recorded hashes. The crew entry point and command modules are now available to every runtime. (issue #336, PR #401, 2026-11-01) Box skill copy: none.
- `crew doctor` checks whether a host can run the crew and prints one `ok`, `warn`, `fail` or `human` line per check with its fix hint: tools, `gh` logins, engines (the coordinator's, and a second one so the reviewer engine can differ), Codex hook trust and Claude Code folder trust for tmux, placeholder paths, the state dir layout, and the installed version against the latest release. It is read-only by default; `--fix` creates the missing state dir layout, and the steps only a person can take are listed at the end. Exit 1 on any `fail`. (issue #190, PR #364, 2026-11-01) Box skill copy: none.
- Runtime handoff (design): `docs/handoff.md` proposes how the owner pauses one crew runtime on a repo and resumes the same work in another, both ways (for example Grok Bot to a Claude Code or Codex session when orchestration quota runs short). One runtime instance owns a repo at a time, recorded by `pass=handoff` markers on a control item; every other runtime runs read-only. It covers drain, stop and takeover modes, a references-only handoff manifest with its template, an `acked` marker keyed by a handoff id so a retry is never a second handoff, reconcile against live state in dependency-closed sets, prompt stop of the outgoing runtime's wake sources, the return path, session rules as profile and flavor settings, and the build issues (#210 to #213 plus proposed follow-ups). The runtime contract gains C9 Ownership handoff, which the Grok Bot and tmux bindings declare unsupported today, compensated by the manual pause. Roadmap 21.1; part of #110. (issue #157, PR #363, 2026-11-01) Box skill copy: none.

### Changed

- Trim tmux coordinator and synthesizer briefs to restore headroom against the
  16 KiB per-role budget. Repeated owner communication, flavor suggestion and
  train checks refer to their existing reviewed rules; marker semantics and
  merge gates are unchanged. Refresh rendered fixtures and keep the existing
  budget unchanged; the 14 KiB trim target is not a new permanent limit. (issue #527, PR #532, 2026-11-01) Box skill copy: deferred to #140.
- Retain tmux builders after completion until their PR merges or closes, count only busy builders toward the cap, reclaim the oldest safely pushed idle builder when the physical band fills, and route later fix messages to a replacement automatically. (issue #493, PR #523, 2026-11-01) Box skill copy: deferred to #140.
- Reviewer validation runs acceptance checks, the repo guard, and tests covering changed files, citing green PR CI at head for the full suite. Verdicts list the local tests and CI link; red or missing CI remains the merge gate and cannot be replaced by a local full run. Both runtime templates and their render/parity fixtures follow this scope. (issue #503, PR #520, 2026-11-01) Box skill copy: deferred to #140.
- Reviewer bindings gain delta re-review of builder-resolved base updates with independent validation and a new head-pinned verdict, and record the reviewed base SHA. The router leaves clean merge-up events queued for synthesizer dispatch; missing reviewed bases trigger fresh review and validation through the coordinator. Approved merge-up events route to the synthesizer for patch identity rather than an automatic reviewer session. Coordinator dispatch never sends a change back solely for being behind and treats overlap as a risk signal, serializing only semantic dependencies, shared mutable external state or incompatible migrations. Final slice of #502. (issue #502, PR #519, 2026-11-01) Box skill copy: coordinator mirror required.
- Give the synthesizer sole landing decisions under the protocol and profile, limit coordinator inputs to recorded steers, and define urgency and project stop/resume markers. All runtime briefs carry the rules; the train gate reads durable landing-control reviews and refuses outstanding stops without weakening any merge gate. The Grok dispatcher records resumes on the same landing-control issue as their stops. (issue #496, PR #517, 2026-11-01) Box skill copy: pending coordinator mirror.
- The content helper compares verified and tool-updated patches without ignoring whitespace, paths, modes or binary changes. With a recorded review base, trains check each applied patch before inclusion and again at land, route differing patches to the builder and record content=identical with the full carried-from SHA. Both synthesizer bindings carry only a passing verdict with green live CI and recheck every other gate. Unchanged-head legacy train approvals remain eligible without claiming content portability. Second slice of #502. (issue #507, PR #516, 2026-11-01) Box skill copy: coordinator mirror required.
- Protocol §7 and its gate registry permit passing verdicts to carry across clean tool-performed base updates only with exact changed-line equality and green CI at the updated head. Conflicts or differing patches route through the builder and delta re-review; owner permission, holds, rereview and runtime gates remain live checks. First slice of #502; synthesizer and reviewer bindings follow separately. (issue #506, PR #512, 2026-11-01) Box skill copy: coordinator mirror required.
- Profile identity and engine validation and rendered role placeholders now read the engineering role registry. Existing profile behavior and rendered briefs are unchanged. (issue #320, PR #499, 2026-11-01) Box skill copy: none.
- Add the tmux lone_pr_land profile option: direct lands a single ready PR without a default-branch catch-up, records the gate waiver and checks merge-commit CI; a red default branch triggers a blocking coordinator fix issue. The default train policy and all other merge gates remain required. (issue #491, PR #498, 2026-11-01) Box skill copy: deferred to #140.
- The tmux runtime reads role bands, passes, names, caps, event consumers and spawn metadata from the engineering role registry, preserving existing behavior and leaving profile and renderer migration to the next slice. Bootstrap and offboarding test bundles include the role registry, and release bundle tests verify it is shipped with the CLI. (issue #319, PR #477, 2026-11-01) Box skill copy: none.
- Builders running a merge-up (a push whose only new commit merges the default branch) now run `check-repo.py` and only the `scripts/test-*.py` covering the conflicted files, and list them with the reason in the merge-up note; PR CI and the recheck pass cover the rest. Normal builds and fix rounds keep the full local run. (issue #464, PR #469, 2026-11-02) Box skill copy: coordinator deploy required.
- Make runtime evidence inline only in the change body and signed reviews, with
  copyable text recipes, GitHub media attachments and explicit size limits.
  Update the evidence merge gate, adapters and role templates; remove committed
  evidence from this tree and reject a root `evidence/` directory. No history
  rewrite; existing product evidence cleanup remains a separate change per repo.
  Keep the incoming builder pre-review checklist consistent with inline proof,
  and remove evidence files added on main before this change lands, including
  the subsequent repository-fixer, routing and merge-up recheck captures. (issue #143, PR #448, 2026-11-01) Box skill copy: coordinator mirror required.
- The new-repo runbook now leads with crew bootstrap preview and confirmed apply, verifies its recorded state before completing wiring, and retains manual profile, render and state setup as the fallback. It distinguishes the current core from pending automation and keeps routine creation, tmux startup and the smoke test explicit. (issue #344, PR #441, 2026-11-01) Box skill copy: none.
- Merge trains skip the duplicate local suite by default, with `--local` or a profile option to opt in and green train CI still required. A scoped, recorded owner mirror deferral can satisfy the tmux mirror gate for covered PRs that do not change live Grok Bot behaviour; merge records name its use and gate changes still require per-PR owner permission. (issue #430, PR #439, 2026-11-01) Box skill copy: deferred to #140.
- Builder pre-review check (16.1): protocol and worker role text now specify fresh-base synchronization, bounded lint/test fixes, private self-review, docs/changelog, typed evidence gathered during testing, and a head-bound `pass=precheck` marker with each step's result. Record the six drawbacks from #160; profile switching and review/merge enforcement remain separate. (issue #180, PR #411, 2026-11-01) Box skill copy: deferred to #140.
- Start tmux review on each opened or pushed head alongside CI, combine held CI failures with review findings in one builder handoff, and treat CI as information during review and validation. CI green at head remains a merge gate. Update the reviewed protocol and declare the Grok Bot review-start gap; live Grok Bot impact is none until mirrored (deferred to #140). (issue #380, PR #392, 2026-11-01) Box skill copy: deferred to #140.
- Grok Bot and tmux bindings declare supported harness adapters and session backends against runtime contract v2 (roadmap 15.6). Grok Bot uses platform-managed turns, with no terminal adapter/backend, and explicitly declares its missing handle-plus-start-time identity probe; tmux declares Claude Code, Codex and tmux support, including the uninstalled and unverified Codex coordinator guard. Existing waiting-cost and unlanded-work teardown gaps remain declared. Docs only; no rule, gate or code change. (issue #179, PR #390, 2026-11-01) Box skill copy: none.
- **Breaking:** Release approval is the owner's per-PR merge-ok at the CHANGELOG cut PR's head, checked by the publish job with the RELEASE_OWNER actor check; landing the cut triggers validation, tagging the merge commit, publishing and release-issue notice. Migration: approve each cut PR at its head instead of approving a deployment after dispatch; workflow implementation follows in #387. Dispatch remains for dry runs and owner-only manual fallback; no standing grant or auto-applied default publishes. The release design, release-approval registry row and workflow usage docs agree (#274). (issue #386, PR #389, 2026-11-01) Box skill copy: deferred to #140.
- The merge train is now a standing synthesizer skill in the rules (#321, part
  2a; part of #110). Protocol §7 gains the "tested with the default branch"
  gate and its gate-registry row: the head contains the current default
  branch, or the change is the next member of a green train on it. A new §7
  section gives the owner's land rules (train two or more ready changes, merge
  a lone or urgent one alone, wait briefly for one close to approval, never
  past the window), and each merge record names its rule in a `Land rule:`
  line. `docs/roles.md`, both synthesizer templates and the tmux runtime doc
  follow it; the `train_min` and `train_window` profile options come in part
  2b. (issue #321, PR #367, 2026-11-01) Box skill copy: deferred to #140.

### Fixed

- The tmux watcher refreshes heartbeats for live windows with live tool sessions or recent output; persistent helpers sharing the harness session do not mask a stale window. Mechanical routing starts full review after recheck escalation and allows validation after zero-step CI startup failures, reporting ci-infra to the coordinator while preserving the green-CI merge gate. (issue #494, PR #524, 2026-11-01) Box skill copy: none.
- Keep the synthesizer alive during an unfinished land, held land lock or open
  train, including merged-PR cleanup. Save pending lands in run state and restore
  them after kill or crash; name open trains and recovered inbox IDs on spawn.
  Unacknowledged retries ignore historical completions for the same PR.
  Bind detached land-lock holders to the owning pane's process identity, and
  clean up dead or orphaned holders without signalling a live owner or reused PID.
  Allow the expanded repo-guard suite ten minutes in CI. (issue #510, PR #515, 2026-11-01) Box skill copy: none.
- Mechanical routing consumes approved merge-up builder completions without starting a full review and routes merge-up events to one deduplicated recheck at the approval round. An open rereview steer keeps normal review, as do ordinary fix pushes. (issue #468, PR #504, 2026-11-01) Box skill copy: none.
- Keep the synthesizer window alive after a completion while another land request
  or undelivered inbox message remains. Serialize inbox appends with the route's
  check and reap so a pending request cannot disappear during cleanup. (issue #472, PR #500, 2026-11-01) Box skill copy: none.
- Merge train gates recognize hold-until dependencies only in coordinator posts,
  so quoted test strings in reviewer, builder and synthesizer posts no longer
  block landing. Missing or unreadable dependencies produce a clear blocked
  gate result instead of an unhandled lookup error. (issue #485, PR #489, 2026-11-01) Box skill copy: none.
- Merge trains preserve green CI across transient landing stops, select members by changed-file overlap, automatically route deferred members for merge-up after landing, and report members, lands, drops and stop causes in one line. HTTP retry codes require an explicit HTTP status prefix, so numbers in changed SHAs and hold references remain real stops. Pipelined successors retain their CI while a predecessor is transiently paused, and resume serial landing after it completes. (issue #460, PR #465, 2026-11-01) Box skill copy: deferred to #140.
- Automatically dequeue the freed role band after crew kill, persist sandbox env through the profile and window launches, and spell out reviewer section markers, rereview overrides and retained reviews for re-validation. Cover the existing builder scratch-file policy in brief tests. Keep the reviewer parity fixture aligned with the ownership guard and actual-run signature on main. (issue #429, PR #437, 2026-11-01) Box skill copy: coordinator deployment of rendered tmux briefs required.
- Skip scratch JSON in tmux run discovery, reset watcher status offsets when a
  window's run identity changes, retain builders' opened PRs for cleanup after
  squash landing, and require a prompt heading plus a final footer when detecting
  older trust and hooks-review dialogs so quoted output stays usable. (issue #369, PR #420, 2026-11-01) Box skill copy: none.
- `crew up` refuses before rendering when a profile can use Codex and a host
  `hooks.json` or inline `config.toml` hook lacks stored trust. The read-only
  check shares `crew doctor`'s host-hook check, tells the operator to review
  hooks once in plain Codex, and never writes config or recomputes trust hashes. (issue #370, PR #406, 2026-11-01) Box skill copy: none.
- The tmux builder, reviewer and synthesizer briefs and `AGENTS.md` now say: never download or install a binary from the internet, never bypass OS code-signing or quarantine, never use an alternate or mirror package registry; when a CI tool is missing or its registry fails, skip that one local check, say so in the PR evidence, and leave it to CI. The tmux briefs also say role scratch files go in the worktree's `.crew/`, and only `$CREW_ID.body.md` goes in `$CREW_STATE/runs/`, since a stray `runs/*.json` crashed `crew watch` (#369). (issue #400, PR #405, 2026-11-01) Box skill copy: none.
- `crew watch` skips stale wakes for runs without `start` while their run-record
  mtime is less than 60 seconds old, avoiding a false missing-run restart during
  spawn. Older unfinished spawns and started runs with missing windows still
  wake as missing and restartable. Regression tests cover all three cases. (issue #361, PR #393, 2026-11-01) Box skill copy: none.
- `crew spawn` and an in-place `crew restart` now pass `--add-dir <git common dir>` to every Codex role window, in every permission mode, next to the state dir. A linked worktree keeps its refs and objects there, so a host sandbox that allows writes only under the working directory and `--add-dir` paths no longer stops a Codex builder from creating a branch, committing or pushing. (issue #384, PR #385, 2026-11-01) Box skill copy: none.

### Security

- **Breaking:** Sensitive path classification now requires per-change owner merge-ok; no standing grant covers `crew:sensitive`. Profiles can extend mandatory path defaults. Migrate by classifying changes at triage/open/push and recording owner overrides; synthesizers and merge trains enforce the label. (issue #184, PR #413, 2026-11-01) Box skill copy: deferred to #140.

## [2.1.1] - 2026-11-01

### Added

- Session backend interface: `docs/runtimes/session-backends.md` defines what a
  runtime needs from the program hosting its role sessions (create in the
  background, attach read-only by default, doorbell, identity probe, state read,
  kill), each tied to the runtime contract capability it serves. The identity
  probe restates C5 as backend operations: a unique handle plus a start time,
  recorded at spawn, and a different handle or start time probes `missing`,
  never `alive`. tmux is filled in from `scripts/crew-tmux.py` and the tmux
  binding. The runtime contract links it from a new `## Session backend
  interface` section; the docs index, deliverables inventory and manifest, and
  required-docs list gain its row. Docs only; no rule, gate or code change.
  Roadmap 15.5. (issue #178, PR #360, 2026-11-01) Box skill copy: none.
- Host inventory and project affinity in the profile (20.2): optional
  `[hosts.<name>]` tables (primary, capabilities, `max_runs`, roles) and a
  `[placement]` table (affinity hosts and capability rules), documented in
  `docs/profile.md`. `scripts/crew-config.py validate` names hosts by overlay
  network name only (an IP literal, `@` or `:` fails) and rejects an unknown
  capability, zero or several primaries, unknown placement hosts, uncovered
  roles, unmeetable rule needs and `[hosts]` outside the tmux runtime; the
  secret-pattern scan covers every host value. Part of #110. (issue #204, PR #358, 2026-11-01) Box skill copy: none.

### Changed

- M14.3 tmux polish close-out (part of #110): the README Status marks M14.3
  done (#301, #303, #312, #270, #262), and `docs/specs/portable.md` §5 gains
  an M14.3 table with each slice `done` and its merged PR (status only, no
  requirement changes). The runtime contract's C5 `ambiguous` row in
  `docs/runtimes/README.md` no longer says a flat "never restart": it names
  the tmux binding's two kill-and-respawn exceptions, the dialog rule and one
  respawn of a stuck synthesizer after a failed nudge (#312), and links Q7 of
  `docs/runtimes/tmux.md`. (issue #368, PR #379, 2026-11-01) Box skill copy: none.
- Conflict-free index files, part 2 of #325 (part of #110). The inventory table in `docs/deliverables.md` is now generated from `scripts/deliverables.txt` (one row per manifest row; the manifest gained an optional Why column), and `python3 scripts/check-repo.py --fix` rewrites it. `scripts/deliverables.txt`, `scripts/required-docs.txt` and the `docs/README.md` rows are sorted, so a new entry lands at its own place instead of the end of the file, where every PR appended. The new `check-repo.py` check `index` (rules `index-stale`, `index-order`, `docs-index`) fails on a stale table, an unsorted file, a duplicate row, or a deliverable doc missing from the index. CONTRIBUTING.md and the worker brief rules in `docs/roles.md` gain the rule: no new shared append-hotspot files, one file per item or a generated aggregate. `test-check-repo.py` proves that two branches that each add a script, a doc and their index rows merge with no conflict, and that the same additions appended at the end of the files conflict. (issue #325, PR #362, 2026-11-01) Box skill copy: deferred to #140.
- The tmux coordinator brief now treats a window as `ambiguous` when `crew send` exits 4 (nudge not submitted) or an ack is still missing after the re-nudge, even if it probes `alive`, and still never restarts it, with one exception (#312, split from #308 ask 2; part of #110). The synthesizer window holds no worktree work, so the coordinator may kill and respawn it once per PR (`crew kill`, then `crew spawn synthesizer --pr <n>`), only while no land is in flight (`locks/merge.pid` absent), re-sends any other pending `land` because the kill drops its inbox, and asks the owner on a second miss. `docs/runtimes/tmux.md` names the exception in the Q7 failure policy. The brief-lint test gains a rule against restarting an `ambiguous` window outside this exception, and the rendered coordinator brief golden carries the new text. (issue #312, PR #359, 2026-11-01) Box skill copy: deferred to #140.
- Per-script docs replace the shared usage table in `scripts/README.md`, a merge
  hotspot that nearly every scripts PR edited (#325, part 1 of 2; part of #110).
  Each script's usage now lives in its module docstring, and `--help` prints it
  (`crew --help` and `crew <cmd> --help` too); `scripts/README.md` keeps a short
  guide and the long-form sections. A new `check-repo.py` check, `script-docs`
  (rule `script-doc`), fails when a script under `scripts/` has no module
  docstring, or a script you run or a `crew` command has no `Usage:` line.
  `test-check-repo.py` proves that two branches that each add a script with its
  docs merge with no conflict. Index files (deliverables, required docs, docs
  index) follow in part 2. (issue #325, PR #335, 2026-11-01) Box skill copy: none.

### Fixed

- tmux: a Codex coordinator now starts pre-trusted like a role window. `crew up`
  still launched it with `-c projects."<project-dir>".trust_level="trusted"`, the
  key form that did not stop codex-cli 0.164's `Trust this folder?` dialog, and
  with the project path as given rather than its real path (on macOS a temp path
  under `/var` is really under `/private/var`). It now gets the same per-process
  `projects` table as role windows (#293), from a new `codex_trust()` helper in
  `scripts/crew.d/_shared.py` that `harness()` also uses: the real project
  directory and, in a git repository, its repository root, where Codex applies a
  linked worktree's trust. `~/.codex/config.toml` is still never edited. The
  detection half of #262 shipped in #289: a window showing the dialog probes
  `ambiguous` and wakes the coordinator. Pre-resolving Codex's `Hooks need review`
  gate stays the owner's host-level step; a safe design for it is proposed in
  the PR, not built. `scripts/test-crew-up.py` tests both launches;
  `docs/runtimes/tmux.md` and `docs/runtimes/harness-adapters.md` show the new
  coordinator launch. (issue #262, PR #365, 2026-11-01) Box skill copy: none.
- Under the tmux runtime the reviewer now posts the protocol §6 intake ack (#303, part of #110). Before this, no
  reviewer posted it: `crew poll` has no `pr-opened` event and the reviewer brief had no ack duty, so the first
  thing on a PR was the final verdict. The rendered tmux `reviewer.md` brief has a new step 3: the round-1 `review`
  pass, after its live re-read and engine check, posts one COMMENT review `[<ReviewerBot>/ack] intake @ <sha7>` with
  a `pass=ack` marker (`round=n/a verdict=n/a`). It skips a draft and a head that already has one, so a respawned
  pass adds none, and the `validate` pass and later rounds never post it. The ack is narrative only: it wakes
  nobody, counts no round and is never an approval. `docs/runtimes/tmux.md` records the choice over a `pr-opened`
  poll event. `test-tmux-briefs.py` checks the rendered brief's ack step and `test-crew-poll.py` proves a
  `pass=ack` marker emits no event. (issue #303, PR #357, 2026-11-01) Box skill copy: deferred to #140.
- The tmux role briefs now say where a `gh` `--body-file` scratch file goes
  (#270, from the #139 final live run L1; part of #110). Builder, reviewer and
  synthesizer write it to `$CREW_STATE/runs/$CREW_ID.body.md`, which `crew kill`
  and `crew down` delete with the run's other `runs/<window>.*` files; before,
  roles wrote bodies to `/tmp` and to the parent of the state dir, where they
  outlived the run. The coordinator, whose window is never killed, writes
  `runs/coordinator.body.md` and deletes it after the post. The brief lint in
  `test-tmux-briefs.py` fails a brief that uses `--body-file` without that
  location or names a `/tmp` scratch file, and `test-crew-kill.py` pins that kill
  removes `runs/<window>.body.md`. `templates/backends/github.toml` is unchanged,
  and the Grok Bot runtime templates do not use it, so their rendered text is
  unchanged. (issue #270, PR #356, 2026-11-01) Box skill copy: deferred to #140.
- tmux turn-end guard counts open owner asks (restores documented
  behaviour): Q1 step 4 in `docs/runtimes/tmux.md` said `crew guard` blocks
  the coordinator's stop while an owner ask is open and no watcher is armed,
  but the guard counted only run records and a non-empty
  `wake/queue.jsonl`, so the coordinator could end its turn with an ask open
  and nothing armed to wake it at the deadline. Since #287 gave each open
  ask a record, `asks/<n>.json`, the guard now counts any record there as
  work in flight, an unreadable one included. The `crew guard` section of
  `docs/runtimes/tmux.md` and the guard's docstring say so; the Q1 step 2
  reason list and the `crew watch` usage already named the `ask:` wake.
  Test in `scripts/test-crew-guard.py`. Grok Bot runtime unchanged.
  Refs #110. (issue #301, PR #355, 2026-11-01) Box skill copy: none.

## [2.1.0] - 2026-11-01

### Added

- `crew train`, a merge train for the tmux runtime (part 1 of #321): approved
  PRs are tested together once, then land with no catch-up between them, in
  place of the merge queue GitHub does not offer private repos on GitHub Free.
  `crew train build <pr>...` merges each PR head onto the freshly fetched
  default branch as `crew/train-<n>` in a temporary clone that ignores local
  merge attributes, so a local `merge=union` cannot hide a conflict GitHub
  would hit (a PR that conflicts is dropped). It runs the local checks,
  pushes the branch with a draft train PR and waits for CI after a grace
  period, since `gh pr checks` fails until checks register.
  `crew train land <n> <pr>` lands the next member with
  `--match-head-commit`. The synthesizer re-runs the whole §7 check at that
  head right before each call, and `land` itself stops unless the default
  branch is still the train's tested state, the head is the tested head, a
  pass verdict and merge permission are at head, there is no
  `crew:escalated`, `crew:changes`, blocking `crew:hold`, open rereview or
  open hold-until, and GitHub reports the PR mergeable. It posts a merge
  record citing the train branch, SHA and CI run; a stop or the last member
  closes the train PR and deletes its branch, and `crew train close` ends a
  train early. `crew train bisect` is not built yet. The tmux synthesizer
  brief uses the train for two or more PRs waiting to land,
  `docs/runtimes/tmux.md` documents it, and `scripts/test-crew-train.py`
  covers it with a fake `gh` and a logging `git`.
  The protocol §7 and gate registry wording follow in part 2. Part of #110. (issue #321, PR #326, 2026-11-01) Box skill copy: deferred to #140.
- Crew flavors (design): `docs/flavors.md` proposes per-project rigor
  presets (`thorough`, `standard`, `fast`, `solo`) built from eleven knobs
  (review depth, validation, engine diversity, caps, evidence, merge
  permission, pre-review check, lighter lane, parallelism, engine routing,
  builder); the floor F1–F7 (CI never waived, no secrets, synthesizer-only
  land, audit on the record, owner hold, gate changes need the owner,
  `crew:sensitive` needs a per-change merge-ok) with validator rules; a
  `[flavor]` profile schema proposal; project / item / change resolution
  per #160 row 15 (flavor chosen at intake, item flavor recorded at
  triage, a stated reason to lower, no flavor = `thorough`, path-based
  class rule, uncertain → stricter); a mapping of every existing one-off
  knob; and the metrics feedback loop (inputs, thresholds T1–T3 and R1–R3,
  suggestion issue, owner accept path, never auto-applied). Maps onto
  build issues #195–#199, #102 and #109. `docs/flavors.md` is classified
  as a deliverable and pinned in `scripts/required-docs.txt`. Adds no
  rule, gate, cap, marker field or label. Roadmap 18.1. (issue #156, PR #307, 2026-10-31) Box skill copy: none.
- Multi-device design: `docs/runtimes/multi-device.md` designs role runs on
  several hosts of a private overlay network under one primary host, as a
  capability of the tmux runtime (not a new binding), carrying out the #160
  row 6 decision. It covers overlay assumptions, a host inventory profile
  extension (`[hosts.<name>]` with capabilities, `max_runs`, roles;
  `[placement]` affinity and capability rules; proposal for #204), the
  `place()` function in `crew spawn` with a recorded `--host --reason`
  override, `crew host check` / `prepare` and `crew hosts`, the hardened
  remote call and per-account runner, C1–C8 across hosts with gap lines,
  failure and partition handling (the `unreachable` class is never
  restarted or re-placed), the security model, alternatives per decision,
  and a map onto build issues #204–#209 plus proposed 20.8–20.12. Docs
  only; no rule, gate, cap, marker field or label changes. Roadmap 20.1. (issue #158, PR #306, 2026-10-31) Box skill copy: none.
- Bootstrap design: `docs/bootstrap.md` answers the ten #144 questions,
  with the alternatives considered for each. `crew bootstrap` runs from an
  extracted, checksum-verified release bundle at a tag. It resolves the
  config layers, proposing a project file when there is none (#191), and
  runs `crew doctor` (21 preflight checks, each with a fix hint, failing
  closed; includes the nested-sandbox quirk through `CREW_SANDBOX_ENV`).
  It plans first (`--dry-run`), applies idempotent `crew:*`-only repo
  fixers, renders once into the state dir and installs untracked pointers
  per harness. It records `VERSION` and `install.json`, then self-tests.
  The doc also has a per-runtime install-target table (Claude Code, Codex,
  Grok Bot, tmux) with contract gaps, upgrade with role reload (#192),
  uninstall as automated offboarding, secrets by mechanism, and a mapping
  onto #165, #166 and #190–#194 plus proposed build issues. Indexed in
  `docs/README.md`, classified as an install doc in
  `docs/deliverables.md` and `scripts/deliverables.txt`, and listed in
  `scripts/required-docs.txt`. No rule or gate changes. Roadmap 17.1. (issue #144, PR #304, 2026-10-31) Box skill copy: none.
- Inline-only evidence design (#143, part 1 of 2, owner decision pending): a
  design section in `docs/verification.md` that answers the five open
  questions and lists the alternatives considered for each. It recommends:
  media only as GitHub user-attachments URLs, attached with
  `gh pr create --attach` (`gh` 2.99.0 or later), and for posts after the
  change opens a text recipe plus the validator's own reproduction; text
  evidence as a copyable repro pair (an `sh` block, then a `text` block with
  the exit code, stdout and stderr); size budgets under GitHub's
  65,536-character limit; deleting `evidence/` from each tree going forward,
  with no history rewrite; and a new Required evidence gate registry row. No
  live rule, gate, template or marker changes: protocol §3 and §7, the
  registry and the templates change in the build PR. (issue #143, PR #302, 2026-10-31) Box skill copy: none.
- Knowledge routing and correct-not-add for always-loaded files:
  `docs/self-improve.md` gains a `## Knowledge routing` table (owner
  profile, product-repo `AGENTS.md` via `repo:`, org pack, eng-crew
  harness via `crew:`, or lesson only; most specific owner first; profile
  and org-pack cards close as routed) and an `## Always-loaded files`
  section (any role may correct wrong text; a learning adds text only
  through an accepted intake card and its PR; prune before adding).
  `docs/roles.md` gets a matching **Knowledge routing** paragraph. No gate,
  cap, marker field or label changes; no size budget (M17, #194).
  Decision: #160 row 18. Roadmap 16.9. (issue #188, PR #297, 2026-10-31) Box skill copy: deferred to #140.
- CHANGELOG fragments, part 1 (tooling and `CONTRIBUTING.md`): a PR records
  its change as `changes/unreleased/<issue>-<slug>.md` (front matter `type`,
  `issue`, `pr`, `date`, `box-skill`, then one paragraph) instead of editing
  `CHANGELOG.md`. `scripts/changelog-cut.py` turns each fragment into an entry
  under its Keep a Changelog heading in the cut section, together with any
  entries already under `[Unreleased]`, then deletes the fragments; it refuses
  a malformed fragment or `pr: TBD`. `scripts/release-check.py` refuses a
  release while a fragment is left, and `scripts/check-repo.py --only
  fragments` checks every fragment's format. `changes/**` is classified
  internal. The process text for roles, release and the briefs follows in a
  part 2 PR. (issue #264, PR #292, 2026-10-31) Box skill copy: none.
- Coordinator owner-communication rules: a new `## Owner communication
  (coordinator)` section in `docs/roles.md` (outcomes first, a final message
  that stands alone with every outcome, decision and full URL, escalations as
  evidence → consequence → options → recommendation, plain words in chat while
  markers keep exact terms, reach the owner only for review-ready work,
  findings, gate decisions, blockers, destructive or security-sensitive actions
  and credentials, full URLs copied from the record, and one fixed neutral
  reply for a true no-op), rendered into the tmux coordinator brief
  (`templates/runtimes/tmux/coordinator.md`, golden refreshed). Credits
  firstmate's etiquette as prior art, persona removed (decision #160 row 14).
  Roadmap 16.7. (issue #186, PR #284, 2026-10-31) Box skill copy: deferred to #140.
- Spec slice for M15–M21: `docs/specs/portable.md` goes to v0.3 with §5
  slice tables for M15–M21 (every issue from the #160 review with its
  dependencies, the moved design and backlog
  issues #150, #143, #144, #165, #166, #156, #102, #109, #170, #158
  and #157, and 15.7 #264), each milestone linked to its #160 row comments;
  the missing 14.1j (#265), 14.1k (#266) and R1.9–R1.11 (#275–#277) rows; §2
  P10 (per-PR changelog fragments under `changes/unreleased/`, assembled at
  cut); and four §6 decisions (#160 option A, the 14.11 M14 freeze
  exception, changelog at cut time, M15+ hold lifted). No rule changes. Spec
  PR: the owner approves the merge per PR. Roadmap 15.0. (issue #173, PR #283, 2026-10-31) Box skill copy: none.
- Harness adapter interface: `docs/runtimes/harness-adapters.md` defines
  the fields a runtime needs per agent CLI (launch line with the brief by
  pointer, trust and first-run dialogs, turn-end and wake recipe, idle
  detection, expected foreground process), each tied to the runtime
  contract capability it serves (C1, C3 or C5), and fills them in for
  Claude Code and Codex from what the tmux binding does today. The runtime
  contract links it from a new `## Harness adapter interface` section; the
  docs index, deliverables inventory and manifest, and required-docs list
  gain its row. Docs only; no rule, gate or code change. Roadmap 15.4.
  (issue #177, PR #294, 2026-10-31) Box skill copy: none.

### Fixed

- tmux nudges never type into a prompt (safety fix): `crew watch` typed its
  `wake: watcher` line plus `Enter` into an idle window 0, and `crew send`
  typed its `inbox: <msg-id>` nudge into a role window, even when the pane
  showed a blocking prompt. Claude Code's permission prompt and Codex's
  approval prompt preselect yes, so that `Enter` could approve a command
  nobody reviewed. Both now check `dialog()` (the prompt and fatal-error
  screens of #289) first and press no key when it matches. `crew send` still
  appends the inbox line, prints `dialog: a prompt is on its screen; nothing
  typed` with `treat <window> as ambiguous` and exits 4; it also re-checks
  before each `Enter` retry. The watcher queues a `dialog` wake for window 0
  (liveness `ambiguous`, action `escalate`) instead of the wake line. A
  normal screen still gets the nudge. (issue #315, PR #331, 2026-11-01) Box skill copy: none.
- tmux stuck detection (patch): a role window sitting on a Codex command
  approval prompt, the Codex `Trust this folder?` screen, a Claude Code
  permission prompt (`Do you want to proceed?`, `Do you want to make this
  edit to …?`) or idle after a fatal API error (`"type":"error"` with a 4xx
  or 5xx status) probed `alive`, so `crew status` showed it healthy and
  `crew watch` sent no `dialog` wake. `dialog()` in
  `scripts/crew.d/_shared.py` now matches each prompt by its heading on a
  line of its own plus its footer as the last screen line, and the error by
  the harness's own error line (`■` in Codex, `⎿  API Error:` in Claude
  Code), so text quoted in a prompt echo or diff does not match. Such a
  window probes `ambiguous` and the watcher wakes the coordinator with
  `dialog` on its next scan. `scripts/fixtures/dialog/` holds captured
  screens of each case plus working screens that quote the same text;
  `scripts/test-crew-status.py` and `scripts/test-crew-watch.py` test them.
  `docs/runtimes/tmux.md`, `docs/runtimes/harness-adapters.md` and
  `scripts/README.md` describe it. Part of #110; refs #262. (issue #289, PR #313, 2026-10-31) Box skill copy: none.
- `crew send` nudges no longer pile up unsent in a Codex composer: an
  `Enter` sent right behind the typed `inbox: <msg-id>` landed in Codex's
  paste burst and added a newline, so each nudge stacked under the last and
  none was submitted. The adapter's `send_keys` now waits 0.3 s before
  `Enter` (the watcher's `wake: watcher` line too), and `crew send` follows
  firstmate's verified-submit pattern: it reads the composer at the cursor,
  clears earlier `inbox:` lines with `C-u` when they are all it holds (other
  text is never cleared), types the nudge once, retries `Enter` up to 3
  times while the nudge is still in the composer, and exits 4 with
  `crew: nudge not submitted: ...; treat <window> as ambiguous` if it never
  submits. `scripts/test-crew-send.py` adds the composer check on captured
  Codex and Claude Code screens and a fake-composer test; `docs/runtimes/tmux.md`
  and `scripts/README.md` describe it. (issue #308, PR #310, 2026-10-31) Box skill copy: none.
- `crew spawn` and `crew restart` rejected Claude Code windows on a native
  install (patch): the installer's `claude` is a symlink, and tmux reports
  `#{pane_current_command}` as the target file's name, the version (for
  example `2.1.314`), so the exact `claude` match failed each `claude-code`
  launch there, reviewers and `trivial`-tier builders included. The start check
  (`wait_harness`) now takes the evidence liveness takes: `claude` or
  `codex` among the pane tty's foreground process names, or a pane command
  equal to that name or to the name of the file it resolves to on `PATH`.
  A version-shaped name alone still fails, and a dead pane still fails at
  once. `scripts/test-crew-spawn.py` and `scripts/test-crew-restart.py` add
  version-string pane tests; `docs/runtimes/tmux.md`, the expected
  foreground process rows in `docs/runtimes/harness-adapters.md` and
  `scripts/README.md` describe the check. Part of #110. (issue #286, PR #309, 2026-10-31) Box skill copy: none.
- tmux watcher owner-ask deadline (restores documented behaviour): the C8
  row and Q1 in `docs/runtimes/tmux.md` said the watcher wakes the
  coordinator at an owner ask's §6 auto-apply time, but `crew watch` had no
  such timer, and its backstop backs off to 16 × `--backstop` while no run
  is recorded, so a deadline could pass hours before the coordinator woke.
  The coordinator brief now writes each open ask's deadline to
  `<state-dir>/<owner>__<repo>/asks/<n>.json` (`{"deadline": ...}`, ISO
  8601 with its UTC offset) and deletes it when the ask closes. `crew watch`
  queues one `ask: <n> deadline <time>` wake per deadline on the first scan
  at or after it, cuts its scan sleep short so that scan lands on the
  deadline, whatever the backstop, and wakes at once on an unreadable
  deadline. The C8 row, Q1 and the `crew watch` source list in
  `docs/runtimes/tmux.md` name the `ask:` wake. Tests in
  `scripts/test-crew-watch.py` use an injected clock; golden
  `scripts/fixtures/render/tmux/runtime/coordinator.md` updated; Grok Bot
  renders unchanged. Refs #110. (issue #287, PR #300, 2026-10-31) Box skill copy: deferred to #140.
- `crew watch` flakes (patch): a `--source` was cut off after `--interval`
  seconds, so at the tests' `--interval 0.05` even `printf` could time out
  on a loaded runner, and a slow `crew poll --once` risked the same. The
  source timeout is now `--source-timeout` (new flag), default `--interval`
  with a 5 s floor. A SIGTERM, SIGINT or SIGHUP that landed while the
  watcher was starting a `tmux`, `ps` or `--source` child left that child
  running after the watcher exited (it then wrote into the test's temp dir,
  failing cleanup with `Directory not empty`); a signal during a scan is
  now held until the scan's children exit, and the watcher exits at once
  between scans or on a second signal. `scripts/test-crew-watch.py` adds a
  slow-source floor test, a held-signal test and a second-signal test, and
  gives the timed-out source `--source-timeout 1`. `docs/runtimes/tmux.md`
  and `scripts/README.md` describe both. (issue #272, refs #110, PR #305,
  2026-10-31) Box skill copy: none.

### Changed

- Upgrade note (2.1): tmux role windows now launch with permission prompts
  off by default (`runtime.options.permission_mode = "bypass"`, following
  firstmate), so agents run any command in their worktree without asking;
  set `"auto"` or `"safe"` in `crew.toml` to opt out. Each project needs a
  one-time Claude Code folder trust on its first `crew up`: accept the trust
  dialog once in the coordinator's window, which also covers the role
  worktrees. Codex windows trust the worktree and its repo root
  automatically. Details:
  [docs/runtimes/tmux.md](https://github.com/mw-ding/eng-crew/blob/main/docs/runtimes/tmux.md#crew-spawn)
  and the runbook's
  [tmux runtime](https://github.com/mw-ding/eng-crew/blob/main/docs/runbook-new-repo.md#tmux-runtime)
  section. (issue #328, PR #329, 2026-11-01) Box skill copy: none.
- tmux role-window launch policy (behaviour change: role windows no longer
  stop on permission or approval prompts): new profile key
  `runtime.options.permission_mode`, `bypass` | `auto` | `safe`, default
  `bypass` (firstmate's default, owner decision on #110). `harness()` in
  `scripts/crew.d/_shared.py` gives Claude Code `--add-dir
  <state-dir>/<owner>__<repo>` in every mode, then `--permission-mode
  bypassPermissions --settings '{"skipDangerousModePermissionPrompt":true}'`
  (per process; the user's settings are never edited), `auto`, or
  `acceptEdits` (`safe`, the old launch). Codex gets
  `--dangerously-bypass-approvals-and-sandbox`, or `workspace-write` with
  network on (plus `-a on-request` for `auto`), always with `--add-dir
  <state>`. Codex pre-trust is now one `-c projects={...}` table for the
  worktree and its repo root: the old `projects."<dir>".trust_level` form did
  not stop the trust dialog on codex-cli 0.164. `crew spawn` and `crew
  restart` pass the mode, `crew-config.py` validates it, and
  `profiles/tmux.toml`, `docs/profile.md`, `docs/runtimes/tmux.md`,
  `docs/runtimes/harness-adapters.md` and the runbook document it, with the
  `auto` / `safe` residual gap. Tests: argv per mode and engine and an unknown
  mode refused (`test-crew-spawn.py`), the validator (`test-crew-config.py`)
  and the restart launch (`test-crew-restart.py`). The coordinator's `crew up`
  launch is unchanged. (issue #293, PR #311, 2026-10-31) Box skill copy: none.
- Runtime contract C6 provable landing: `docs/runtimes/README.md` C6 now
  says teardown never removes a worktree unless its work has provably
  landed (no uncommitted or untracked paths, and every commit on a freshly
  fetched default branch, run branch or change head; a check that cannot
  run counts as not landed) or the owner discarded it, with the reason and
  the unlanded list recorded on the change or tracker item first.
  `docs/runtimes/tmux.md` cites `crew kill`'s existing unlanded-work check
  and `--discard --reason` (#172) as its C6 answer.
  `docs/runtimes/grok-bot.md` declares a partial C6 gap: cleanup runs only
  after a pass pushes or on `pr-merged` / `pr-closed`, with no landed check
  before the delete. No code or routine change. Roadmap 15.3,
  decision #160 row 3. (issue #176, PR #295, 2026-10-31) Box skill copy: none.
- Resolver as a function (structural, no behaviour change):
  `scripts/crew-config.py` exposes `resolve_profile(project,
  org_profile=None)`, which returns the merged profile, per-key provenance,
  the problems and the layer names. The `resolve` CLI prints from it, and
  `scripts/crew-render.py` calls it directly instead of running
  `resolve_main` and parsing its printed `key = value  # layer` lines. The
  `resolve` output (stdout, stderr, exit code) and the render goldens are
  unchanged. (issue #165, PR #290, 2026-10-31) Box skill copy: none.
- Runtime contract C1 (`docs/runtimes/README.md`) says what waiting may
  cost: waiting costs no model turns, only an actionable event or a due
  backstop starts a turn, and a backstop's interval backs off while nothing
  is in flight. Token-free pollers such as `crew poll` are not model-turn
  polling; a runtime that cannot wait token-free may poll with model turns
  only with backoff, declared as a C1 gap. Both binding tables re-checked:
  Grok Bot declares its fixed hourly sweeper and no-op dispatcher wakes,
  tmux its default watcher nudge (a possible second, empty turn per wake
  for a Claude Code coordinator). Roadmap 15.1, decision #160 row 4. (issue #174, PR #285, 2026-10-31) Box skill copy: none.
- Runtime contract C5 run identity: `docs/runtimes/README.md` C5 now says a
  run is identified by a unique handle plus its start time, recorded at
  spawn, and a probe that finds a different handle or start time classifies
  the run as `missing`, never `alive`. `docs/runtimes/tmux.md` makes its
  decisions table, C5 contract row and Q7 classes consistent with the
  identity probe `crew` already runs (pane id, pane pid and that process's
  start time), so a same-named replacement window never probes `alive`. No
  probe code change. Roadmap 15.2, decision #160 row 5.
  (issue #175, PR #282, 2026-10-31) Box skill copy: none.

## [2.0.1] - 2026-10-31

### Added

- R1 close-out (the #259 closing slice for R1): a README `## Install`
  section that installs from a GitHub Release (`gh release download`,
  `shasum -a 256 -c SHA256SUMS`, extract, record `VERSION`, check
  `crew-config.py validate` and `crew --help` run, then the runbook), with a
  one-line caveat that the `v2.0.0` bundle fails the tool check until #275
  ships. Status sync, status-only: the README Status marks R1 done with
  `v2.0.0` released through `release.yml`, and "What you get" no longer says
  `v2.0.0` is unpublished; the tmux runbook prerequisites accept an extracted
  bundle as `<eng-crew>`; `docs/release.md` records the `v2.0.0` cut and
  adds bundle extraction to the "Before bootstrap" update row;
  `docs/deliverables.md` says the bundle build and release workflow are
  implemented; `docs/specs/portable.md` §5 marks R1.4 (#219) `done`. No
  rule or gate wording changes. Roadmap R1.10. (issue #276, PR #278,
  2026-10-31) Box skill copy: none.

### Fixed

- Release bundle install CLI (patch: restores documented behaviour): the
  v2.0.0 bundle left out `scripts/check-repo.py`, which `crew-config.py`
  imports for its secret-scan patterns, so `crew-config.py`,
  `crew-render.py` and `crew` failed with `FileNotFoundError` from an
  extracted bundle. `scripts/check-repo.py` is now a deliverable (install
  CLI, runtime `all`) in `scripts/deliverables.txt` and the
  `docs/deliverables.md` inventory. `scripts/test-release-bundle.py` now
  extracts the bundle built from the current repo and requires
  `scripts/crew --help`,
  `scripts/crew-config.py validate profiles/default.toml` and
  `scripts/crew-render.py --project profiles/default.toml --out <tmp>` to
  exit 0, so every release validate run gates this. Roadmap R1.9.
  (issue #275, refs #110, PR #280, 2026-10-31) Box skill copy: none.

## [2.0.0] - 2026-10-31

### Added

- tmux runtime runbook: a `## tmux runtime` section in
  `docs/runbook-new-repo.md` (prerequisites including Codex hook trust on
  the host, target-repo setup with placeholder-path refusal, the one-time
  trust dialog, the `crew` operator commands with `--project
  "$CREW_PROJECT"`, the wake path, close-out, owner duties with a hold
  default for merge-ok, troubleshooting from the dry and live runs, and the
  final live sandbox run's timeline and pass bar a–g, all PASS), and the
  lesson `docs/lessons/2026-10-30-tmux-dry-runs.md` mapping the findings of
  two dry runs and three live runs to their fix PRs or backlog issues (#269,
  #270). Roadmap 14.10. (issue #139, PR #249, 2026-10-30) Box skill copy:
  none.
- tmux brief lint: `scripts/test-tmux-briefs.py` renders the tmux briefs
  from `profiles/tmux.toml` and fails on the prose bugs from the dry runs
  and the #139 live run: typing or pressing keys (or `tmux send-keys`) in a
  role window, a `--project` other than `"$CREW_PROJECT"` (or its escaped
  or owner-facing `PATH` forms), a merge-ok auto-applied, defaulted or recorded without the owner's words under
  `merge_grant = "none"`, a raw `flock` instead of `crew land-lock`, and a
  `gh` command without `-R` (except `gh api`) when the brief lacks the
  blanket `-R` rule. Prose that forbids the action passes. Each rule has a
  bad and a forbidding fixture, and the real rendered briefs must pass.
  Wired into the CI `repo-guard` job.
  Roadmap 14.1i. (issue #257, refs #139, PR #261, 2026-10-30) Box skill
  copy: none.
- Spec sync, part 1 of 2 (post-M14): `docs/specs/portable.md` goes to v0.2
  with a Status column (`open`, `done`, `dropped`, from live issue state) on
  every §5 slice table, the missing 14.11 (#172) row, new M14.1 and R1 slice
  tables, four new §6 decisions (standing grant for all milestones and
  status-only spec edits, inline-only evidence, release owner and gate, spec
  bookends), and Q8 moved to "revisit with M15". `docs/specs/framework.md`
  R4 now describes the post-#128 render-and-drift-check mirror. New
  `check-repo.py --only spec-status` guard fails a §5 slice row without a
  valid Status cell, with tests. Spec PR: the owner approves the merge per
  PR. (issue #259, PR #263, 2026-10-30) Box skill copy: none.
- Release bundle attached: in `.github/workflows/release.yml` the `validate`
  job runs `scripts/release-bundle.py "$VERSION"` at the validated SHA,
  checks `SHA256SUMS` with `sha256sum -c`, and uploads
  `eng-crew-<version>.tar.gz` and `SHA256SUMS` as the `release-bundle`
  artifact, replacing the `TODO(#236)` placeholder; the pull request dry run
  builds it for the simulated version. The `publish` job downloads the
  artifact and attaches both files to `gh release create --verify-tag`. No
  other workflow behaviour changes. `crew:sensitive`: the owner approves the
  merge per PR. Roadmap R1.7. (issue #246, PR #248, 2026-10-30) Box skill
  copy: none.
- Release bundle build: `scripts/release-bundle.py <version>` builds
  `eng-crew-<version>.tar.gz` (the paths `scripts/deliverables.txt` classifies
  `deliverable`, at their repo paths under one top-level
  `eng-crew-<version>/` folder, plus `VERSION`) and `SHA256SUMS`,
  deterministically (sorted entries, fixed mtime from `SOURCE_DATE_EPOCH` or
  the commit time, uid/gid 0). Relative links from bundled Markdown to
  internal paths are rewritten to the file at the `v<version>` tag (`raw/`
  URLs for images, so they render inline), then an
  offline link check runs on the bundle. Tests in
  `scripts/test-release-bundle.py`, run in CI. Attaching the bundle in
  `release.yml` is a separate `crew:sensitive` PR. Roadmap R1.6. (issue #236,
  PR #245, 2026-10-30) Box skill copy: none.
- Release workflow: `.github/workflows/release.yml`, dispatched on `main`
  with `version` and `dry_run` (default `true`). A read-only `validate` job
  runs the repo guard, every `scripts/test-*.py` (render parity included),
  markdownlint, the link check and the new `scripts/release-check.py`
  (`[Unreleased]` empty, top section `[<version>]`, tag new and greater than
  the latest), and uploads the notes; pull requests touching the release
  files run it as a dry run on a simulated cut. The `publish` job, behind
  the `release` environment and only with `dry_run=false`, creates the
  annotated tag `v<version>` and the GitHub Release; it never commits, and
  refuses unless the actor is the `RELEASE_OWNER` repository variable (a
  stopgap: GitHub Free private repos have no required reviewers). Bundle
  step left as a placeholder for #236. New release gate row in the
  `docs/protocol.md` gate registry (guards publishing, not merging; no
  fail-open, only defer or cancel). Tests in `scripts/test-release-check.py`,
  run in CI. Roadmap R1.3. (issue #218, PR #243, 2026-10-30) Box skill
  copy: deferred to #140.
- Deliverables manifest: `scripts/deliverables.txt` is the machine-readable
  copy of the `docs/deliverables.md` inventory (#229), one
  `glob<TAB>class<TAB>runtime` row per line. A new `check-repo.py` check,
  `deliverables`, fails on a tracked path that matches no row
  (`unclassified`) or more than one row (`double-classified`).
  `scripts/changelog-cut.py`, not in the #229 table, is classified internal.
  Tests in `scripts/test-check-repo.py`. Roadmap R1.5. (issue #235, PR #242,
  2026-10-30) Box skill copy: none.
- tmux crew watcher hardening, from the #139 dry run (B1, F10, F11, F12):
  `scripts/crew watch` runs each `--source` with a timeout of one scan
  interval (killed and queued as a `source-timeout` wake), so a looping
  source no longer wedges it; sources are documented as one-shot
  (`crew poll --once`). It also wakes when `wake/queue.jsonl` grows (byte
  offset in `watch-state.json`), so a `crew poll` loop in its own window
  works, and ignores the stdout of a source that queued its own records, so
  poll events are queued once. New `crew drain` prints and empties the
  queue under `wake/queue.lock`, which every append takes, so no concurrent
  record is lost. SIGTERM / SIGINT remove `watcher.pid` and save
  `watch-state.json`, which is now saved after every scan. Tests in
  `scripts/test-crew.py`. Roadmap 14.1a. (issue #230, refs #139, PR #241,
  2026-10-30) Box skill copy: none.
- Deliverables and versioned release (design, R1.1): `docs/deliverables.md`
  classifies every path as deliverable or internal (runtime, source or
  generated), packages one bundle per release rendered at install, and sets
  SemVer rules (what is breaking: gates, marker fields, state tags, profile
  keys, pack and interface operations, CLI flags and output, placeholders),
  the compatibility promise to packs and installs, and the first versions
  (`v1.0.0` retro-tag of M12, `v2.0.0` after M14). `docs/release.md`
  designs the release: manual dispatch, the CHANGELOG cut as a normal PR,
  validate and build, owner approval through a protected environment, tag
  and GitHub Release, a draft release-gate row (fail-open: none), rollback,
  the pull-only update path and the session-tooling helpers to upstream.
  Spec P9 and layout rows in `docs/specs/portable.md`; README "What you
  get" points at it. (issue #145, PR #229, 2026-10-30) Box skill copy: none.
- CHANGELOG cut: `scripts/changelog-cut.py <version>` turns `## [Unreleased]`
  into `## [x.y.z] - YYYY-MM-DD` (default today in UTC, `--date` to pin it,
  `--dry-run` to print only), keeps its subsections and entries byte for
  byte and leaves an empty `## [Unreleased]` above. It refuses an empty
  Unreleased, a non-SemVer version, an existing version and a version not
  greater than the latest, leaving the file untouched. Tests in
  `scripts/test-changelog-cut.py`, run in CI. Roadmap R1.2. (issue #217,
  PR #228, 2026-10-30) Box skill copy: none.
- tmux crew watcher: `scripts/crew watch` is the zero-token watcher
  (`docs/runtimes/tmux.md` Q1). It writes `wake/watcher.pid`, blocks on
  new role status lines, runs that probe `dead` / `missing` or stay silent
  past `--stale` (default 15 min), and `--source` event commands (the
  `crew poll` hook), appends each wake to `wake/queue.jsonl`, and exits
  with one reason line so the coordinator is re-invoked. A stale wake says
  `restart` only for a first `dead` / `missing` run and `escalate`
  otherwise. It also types `wake: watcher` into an idle coordinator
  (`--no-nudge` to turn off), and a backstop wake's interval doubles while
  nothing is in flight. `crew restart` no longer loses unlanded work
  (#172): a dead or missing run with unlanded work is relaunched in its own
  worktree, brief and claim instead of being killed and respawned fresh.
  Fake-clock and fake-tmux tests in `scripts/test-crew.py`. Part 2 of 2. (issue #135, PR #222, 2026-10-30)
  Box skill copy: none.
- Render-vs-live drift mode: `scripts/check-skill-drift.py --project
  <crew.toml>` renders the profile with `crew-render.py` and compares every
  rendered file with the same path under the live copy dir (`--live-dir`,
  `ECREW_LIVE_DIR`, else the new optional profile key `paths.live_dir`),
  per section with the existing OK / WORDING / DRIFT classification; a
  rendered file missing from the live copy, an absent or placeholder live
  dir, or a failed render is exit 2, and a live file the render does not
  produce is `EXTRA`. Tests on the render fixtures (match, wording, drift,
  missing, extra, path sources) in `scripts/test-check-skill-drift.py`.
  PR (a) of two; the mirror gate change follows. (issue #128, PR #226,
  2026-10-30) Box skill copy: none.
- tmux role briefs: `templates/runtimes/tmux/{coordinator,builder,reviewer,synthesizer}.md`
  tell each window how to work in this runtime: the coordinator drains the
  wake queue, routes by `crew spawn` / `crew send` / `crew kill`, keeps the
  watcher armed and never pastes payloads; the builder keeps its window for
  the issue, takes fix rounds from its inbox with `ack: <id>` and writes
  `done:` / `blocked:` to `$CREW_STATUS`; the reviewer-validator runs one
  pass in a fresh session, writes its verdict file and `done:`, then exits;
  the synthesizer lands serially under `flock`. They render from the new
  example profile `profiles/tmux.toml`; golden files in
  `scripts/fixtures/render/tmux/`. `crew up --inputs` now defaults to
  `templates/`, and `crew up` / `crew spawn` fall back to
  `render/runtime/<role>.md` when no core brief is rendered. (issue #137,
  PR #225, 2026-10-30) Box skill copy: deferred to #140.
- tmux crew liveness: `crew spawn` records the run identity (pane id, pane
  pid and that process's start time) and its spawn arguments in
  `runs/<window>.json`; `scripts/crew status` prints window, role, item,
  head, heartbeat age, liveness and last status line per run, where
  liveness is the C5 probe from tmux and `ps` (`missing` on any identity
  mismatch, so a new window with the same name and harness is never
  `alive`; `dead` on a dead pane; `alive` when `claude` / `codex` is the
  pane command or a foreground process; otherwise `ambiguous`, `node`
  included); `scripts/crew restart <window>` restarts only a `dead` or
  `missing` run, only once, never a finished one; `crew up` on a dead
  session rebuilds `ash` from disk and lists the recorded runs without
  respawning them. Tests with a fake `tmux` and a fake `ps` in
  `scripts/test-crew.py`; usage in `docs/runtimes/tmux.md`. Part 1 of 2;
  the watcher follows. (issue #135, PR #220, 2026-10-30) Box skill copy:
  none.
- tmux crew serial land and caps: `scripts/crew land-lock acquire|release`
  takes a fail-fast `flock` on `locks/merge.lock`, held by a detached
  holder until release, so a second land fails fast and `crew down`
  refuses meanwhile. `crew spawn` beyond the band cap
  (`runtime.options.builders`, default 5; `runtime.options.reviewers`,
  default 2) creates no window and appends the request to
  `spawn-queue.jsonl`, printing `queued:`; `crew dequeue` spawns the oldest
  queued request whose band has a free slot. Tests in
  `scripts/test-crew.py`; usage in `docs/runtimes/tmux.md`. (issue #136,
  PR #215, 2026-10-30) Box skill copy: none.
- tmux crew CLI: `scripts/crew poll [--once]` is the GitHub wake source:
  read-only `gh` JSON for open crew PRs (head SHA, CI rollup, verdicts
  from hidden `crew:v1` lines at head, merged or closed) and assigned
  `crew:ready` issues is diffed against `poll-state.json` by a pure
  decision function, and each change becomes one wake record in
  `wake/queue.jsonl` naming one consumer (ci-passed → reviewer, ci-failed
  or changes → builder, approved → synthesizer, merged or closed →
  coordinator, newly assigned ready issue → builder). The first run
  records a baseline only. New profile option
  `runtime.options.poll_interval` (default 60). Tests on recorded `gh`
  JSON fixtures in `scripts/fixtures/poll/` and a fake `gh` in
  `scripts/test-crew.py`; usage in `docs/runtimes/tmux.md`. (issue #134,
  PR #223, 2026-10-30) Box skill copy: none.
- tmux crew observe: `scripts/crew attach <window>|<role>` attaches
  read-only by default (`tmux attach-session -r`; `--rw` to type), and
  `crew attach builders` opens a temporary tiled view of the builder band in
  a separate session (one `capture-pane` snapshot pane per builder window),
  killed on detach, so no crew window moves. `scripts/crew logs <window>
  [-n N] [-f]` tails the newest `.crew/runs/**/summary.md` in the run's
  worktree, never raw logs. `docs/observe.md` gains a tmux section that
  replaces the deferred-attach note; usage in `docs/runtimes/tmux.md`; tests
  with the fake `tmux` in `scripts/test-crew.py`. (issue #138, PR #216,
  2026-10-30) Box skill copy: none.
- tmux crew CLI: `scripts/crew send <window> <kind> <ref>...` messages a
  role window by reference: it refuses anything but refs (issue or PR
  number, full SHA, https link, path; no whitespace, no diff or traceback
  markers, 1024-byte line cap), appends one JSON line `{id, kind, refs,
  from, ts}` to `inbox/<window>.jsonl` and types the fixed nudge
  `inbox: <msg-id>` through the tmux adapter. Delivery is proven only by
  `ack: <msg-id>` in the window's status file: `--wait-ack <secs>` or
  `crew acked <window> <msg-id>`. Tests with the fake `tmux` in
  `scripts/test-crew.py`; usage in `docs/runtimes/tmux.md`. (issue #133,
  PR #214, 2026-10-30) Box skill copy: none.
- tmux crew CLI: `scripts/crew spawn <role> --issue <n> | --pr <n>
  [--pass build|fix|review|validate|land]` creates a role window in the
  repo's session at the next free index of its band (`ben-<issue>`,
  `vera-<pr>-r<k>-<pass>`, `sam`), in a unique worktree
  `<worktree-root>/<n>-<sha7>-<role>-<pass>/` from a fresh fetch (refusing
  the primary checkout and existing paths), with engine, model and effort
  from the profile tier routing (a reviewer skips the PR's `Engine:`
  trailer engines), `CREW_*` env via `-e` and the login `CREW_IDENTITY`
  only (the token is derived inside the window), a per-run brief, an atomic
  claim and a run record; Codex is pre-trusted per worktree, and a window
  whose harness is not in the foreground within the timeout is reported
  `failed:` and cleaned up. `scripts/crew kill <window>` stops the window
  and removes only that run's worktree, build output and state files;
  `crew down` now calls it for each role window. Tests with a fake `tmux`
  and a temp git repo in `scripts/test-crew.py`; usage in
  `docs/runtimes/tmux.md`. (issue #132, PR #171, 2026-10-30) Box skill
  copy: none.
- Grok Bot templates as render inputs, with a parity check: `templates/` is
  now the renderer's default `--inputs` tree (`runtimes/grok-bot/`, plus the
  new `backends/github.toml` command mapping for every operation, from
  `docs/backends/github.md` Interface mapping); `crew-render.py` renders
  briefs only when the tree has a `core/` directory and keeps the templates'
  remaining run-time placeholders verbatim. `scripts/test-render-parity.py`
  (run in CI) renders `profiles/default.toml`, alone and with the
  agentconnect example values, and diffs each template against its
  pre-conversion text (`scripts/fixtures/parity/pre/`); a seeded one-word
  drift fails. The `templates/README.md` placeholder table gains a "Profile
  key" column. No template text changes. (issue #126, PR #169, 2026-10-30)
  Box skill copy: deferred to #140.
- tmux crew CLI: `scripts/crew up --project <crew.toml> --inputs <dir>`
  resolves a `runtime.name = "tmux"` profile, renders the briefs into
  `<state-dir>/<owner>__<repo>/render/` and starts the detached session
  `crew-<owner>-<repo>` with the coordinator engine (Claude Code or Codex) in
  window 0 pointed at its brief; `GH_TOKEN` is derived inside the window,
  never in argv or a file. `up` on a running session changes nothing. For a
  Claude Code coordinator it installs the turn-end guard (`crew guard`, a
  Stop hook in the project's `.claude/settings.local.json`); the Codex
  recipe is documented. `crew down` refuses while the land lock is held,
  then kills role windows and the session. All tmux calls go through
  `scripts/crew-tmux.py`; tests with a fake `tmux` in `scripts/test-crew.py`,
  run in CI; usage in `docs/runtimes/tmux.md`. Design credit: firstmate's
  turn-end guard (contract only, no code copied). (issue #131, PR #168,
  2026-10-30) Box skill copy: none.
- Onboarding runbook leads with install by profile: `docs/runbook-new-repo.md`
  gains Step 0 (copy `profiles/default.toml` to `crew.toml`, `crew-config.py
  validate`, `crew-config.py resolve`, `crew-render.py`), maps command
  placeholders to resolved profile keys instead of a placeholder table, keeps
  the GitHub install mechanics (labels, collaborator, milestones and board,
  CI) as Steps 1 to 4 linked from the GitHub backend's Tracking section,
  installs routines from the rendered output with hand-fill as a short
  fallback, and adds checklist rows P1 profile validates, P2 render clean and
  P3 parity (once #126 lands). (issue #129, PR #167, 2026-10-30) Box skill
  copy: none.
- External pack contract and internal-name guard: `docs/packs.md` defines
  the pack layout (`manifest.toml`, optional `profile.toml`, binding docs,
  render overrides), the `eng_crew_version` pin and its compatibility rule,
  the capability declaration and wiring by `resolve --org-profile`, plus the
  direction rule (packs reference eng-crew, never the reverse; also in
  `AGENTS.md`). `check-repo.py --only denylist` fails on a whole-word,
  case-insensitive match of any name in the file named by `CREW_DENYLIST`
  (skipped when unset; no names committed). `crew-config.py resolve` folds
  each backend's `packs/<name>/manifest.toml` capabilities under every
  layer (`# pack:<name>`), and the unsupported-invariant check counts
  undeclared operations as unsupported; manifests accept
  `pack.eng_crew_version`. Tests in `scripts/test-check-repo.py` and
  `scripts/test-crew-config.py`. (issue #127, PR #164, 2026-10-30) Box
  skill copy: none.
- Renderer: `scripts/crew-render.py --project <crew.toml> [--org-profile
  <path>] --inputs <dir> --out <dir>` resolves the profile in-process
  (`crew-config.py resolve`), then writes one brief per role
  (`briefs/<role>.md`) and the profile runtime's artifacts (`runtime/**`)
  from render inputs, replacing install-time `<name>` placeholders from
  profile keys and `<op:<concern>.<operation>>` from a backend command
  mapping. Run-time placeholders stay verbatim. Fails closed with
  `file:line: reason` and writes nothing on an unknown placeholder, missing
  mapping or unsupported capability. Golden-file tests on a fixture profile
  and inputs in `scripts/test-crew-render.py` and `scripts/fixtures/render/`,
  run in CI; usage and placeholder map in `scripts/README.md`. (issue #125,
  PR #163, 2026-10-30) Box skill copy: none.
- Default GitHub profile and pack manifest: `profiles/default.toml` (Grok
  Bot runtime, `github` for all eight concerns, placeholder identities,
  engine routing from `docs/roles.md` Current routing for private repos) and
  `packs/github/manifest.toml` (the GitHub backend's capability declaration,
  every operation `supported`). The schema gains role display names
  (`identities.<role>.name`), `runtime.timezone`, `engines.fallback_engine`
  and `paths.toolchain_bin`; `crew-config.py validate` accepts them and
  validates a pack manifest. Tests in `scripts/test-crew-config.py`. (issue
  #124, PR #161, 2026-10-30) Box skill copy: none.
- Layered config resolver: `scripts/crew-config.py resolve --project
  <crew.toml> [--org-profile <path>]` merges core defaults, the default
  profile (`profiles/default.toml`, when present), an optional org profile
  read by path only and the project file. Tables merge by key; scalars and
  arrays replace; dropping a key under `identities`, `backends` or `engines`
  is an error. The result must pass `validate` plus cross-key checks: the
  unsupported-invariant rule of `docs/interfaces.md`, the single-identity
  `emulated` verdict requirement (#111) and integer options >= 1. Prints
  each key with the layer that set it. Documented in `docs/profile.md`
  (Layers and precedence); tests in `scripts/test-crew-config.py`.
  (issue #123, PR #162, 2026-10-30) Box skill copy: none.
- Profile schema and validator: `docs/profile.md` documents the `crew.toml`
  install-time profile (`[repo]`, `[runtime]` with tmux options,
  `[backends.<concern>]` for the eight interface concerns with an optional
  capability declaration, `[identities]` by `gh_user` login, `[engines]` tier
  routing, `[paths]`): every key, type, default and the placeholder it
  replaces. `scripts/crew-config.py validate <file>` (stdlib `tomllib`)
  prints `file:key: reason` and exits 1 on a missing or unknown key, unknown
  concern, runtime, backend or engine, wrong type, bad capability or a
  token-shaped value (patterns imported from `check-repo.py`); tests in
  `scripts/test-crew-config.py`, run in the CI `repo-guard` job. Indexed in
  `docs/README.md`, pinned in `scripts/required-docs.txt`. (issue #122,
  PR #159, 2026-10-30) Box skill copy: none.
- Backend interfaces (`docs/interfaces.md`): the minimum operations for each
  of the eight concerns (change, review, tracker, state tags, markers, CI,
  events, owner channel), the guarantee of each and the invariant (I1–I5) it
  protects; the capability declaration format (`supported | emulated (how) |
  unsupported`) with the unsupported-invariant rule; and the single-identity
  analysis (I1 breaks; compensation is COMMENT-review verdicts plus a recorded
  owner merge-ok, #111). `docs/backends/github.md` gains an Interface mapping
  section: one `gh` command or API call per operation. Adds no rule, gate,
  cap, marker field or label; `docs/protocol.md` untouched. Indexed in
  `docs/README.md`, pinned in `scripts/required-docs.txt`. (issue #121,
  PR #154, 2026-10-30) Box skill copy: none.
- tmux runtime binding design (`docs/runtimes/tmux.md`): answers #110 Q1
  wake (status files, inbox nudges and `crew poll` feed a zero-token watcher;
  turn-end guard), Q2 lifetime, Q3 coordinator engine, Q5 identities, Q6
  concurrency and Q7 failure (process-identity liveness probe), each with
  alternatives; contract table C1–C8 with C1 and C8 gaps declared; window
  layout with index bands; spawn and kill mechanics from #132. Watcher,
  turn-end guard, delivery-ack and liveness patterns credited to firstmate
  (MIT), no code copied. Indexed in `docs/README.md`, pinned in
  `scripts/required-docs.txt`. (issue #130, PR #152, 2026-10-30) Box skill
  copy: none.
- GitHub backend (`docs/backends/github.md`), section Tracking: the ten
  `crew:*` labels with GitHub colours and descriptions, why no listener fires
  on labels, Milestones and Project (v2) board, `Closes #n` / `Refs #n` /
  `Part of #n` / `Depends on #n` linkage, and the no-issue-comment steering
  limit. Protocol §4, §6, §7 and §9, `architecture.md` (label table kept as the
  role view), the runbook Steps 1 and 3 and `concepts.md` link it. Text move
  only; no rule, gate, cap, marker field or label changes. Indexed in
  `docs/README.md`, pinned in `scripts/required-docs.txt`. (issue #116,
  PR #149, 2026-10-30) Box skill copy: deferred to #140.
- GitHub backend (`docs/backends/github.md`), section Reviews, markers and
  identities: COMMENT vs formal reviews and the events each fires, why bots
  never post plain or inline comments, `gh` identity selection, why GitHub
  refuses self-approve, and the land (`--match-head-commit`) and
  update-branch mechanics. Protocol §1 and §4 keep the rules and link the
  mapping. Text move only; no rule, gate, cap, marker field or label changes.
  Indexed in `docs/README.md`, pinned in `scripts/required-docs.txt`; lesson
  hygiene note in `docs/lessons/2026-10-19-bottlenecks.md`. (issue #115,
  PR #146, 2026-10-30) Box skill copy: deferred to #140.
- Runtime contract (`docs/runtimes/README.md`): eight capabilities every
  runtime provides (wake on event, one consumer per event, messages by
  reference with proof of delivery, status protocol, liveness classes,
  isolation, serial land, owner channel and SLA), each with the guarantee it
  protects, plus a gap-declaration format. Contracts adapted from firstmate
  (`kunchenguid/firstmate`), no code copied (#130 decision).
  `docs/runtimes/grok-bot.md` gains a contract table with gaps declared.
  Pinned in `scripts/required-docs.txt`, indexed in `docs/README.md`.
  (issue #120, PR #148, 2026-10-30) Box skill copy: none.
- Concepts glossary (`docs/concepts.md`): one entry per abstract protocol
  term (change, change head, verdict, narrative post, state tag, marker, CI
  signal, wake event, tracker item / milestone / board, owner channel, land,
  runtime, backend, profile / pack) with its definition, the invariant it
  touches and today's GitHub / Grok Bot mapping. Terms only; no rule moves.
  Linked from `docs/README.md` and the `AGENTS.md` map; pinned in
  `scripts/required-docs.txt`. (issue #113, PR #142, 2026-10-29) Box skill
  copy: none.
- Portable eng-crew spec (`docs/specs/portable.md`): requirements P1–P8
  for runtime and per-concern tool abstraction, install-time profile and
  config layers; invariants every runtime + backend keeps; target layout;
  M13/M14 slices with dependencies; dated decisions from #110, #111, #112
  and #140; open questions mapped to the issues that settle them. Indexed
  in `docs/README.md` and pinned in `scripts/required-docs.txt`.
  (issue #110, 2026-10-29) Box skill copy: none (spec only; no protocol or
  template change).
- Standing quota diversity waive for reviewer engines: prefer available,
  cheap DeepSeek before reset, else allow Codex for one round's verdict
  under the documented risk, identity and recording rules.
  (issue #104, 2026-10-29) Box skill copy: eng-crew-roles (roles) and
  eng-pr-pipeline (protocol) need mirror (coordinator mirrors before merge;
  `crew:needs-mirror` holds the PR until then).
- Coordinator soft-finding follow-up after squash: file and dispatch a
  `crew:ready` issue in the same awake window, unless the user parked softs
  for a named cut; includes an issue template and duplicate check. Softs
  never block §7 squash. (issue #105, 2026-10-29) Box skill copy:
  eng-pr-pipeline (protocol §6) needs mirror (coordinator mirrors before
  merge; `crew:needs-mirror` holds the PR until then).
- Deploy secret sync AC for new deploy milestones: compare shared secrets
  across consuming hosts with safe fingerprints and name the GitHub secret
  store the workflow reads. New-repo wiring records secret names and hosts.
  (issue #103, 2026-10-29) Box skill copy: eng-pr-pipeline (protocol §3)
  needs mirror (coordinator mirrors; `crew:needs-mirror` until mirrored).
- Mutation evidence rule: behaviour-changing PRs that add or change a
  user-visible create, update or complete (or equivalent) mutation paste an
  inline happy-path snippet (create an entity, progress/complete it, then
  delete it: item and/or list delete with cascade, where the snippet also
  shows the child items are gone) in `## Test Output` and
  `## Acceptance Evidence`; the reviewer-validator checks it and reproduces
  where possible, else `disagrees`. Docs-only and non-CRUD PRs unchanged.
  (issue #100, 2026-10-29) Box skill copy: eng-pr-pipeline (protocol §3)
  needs mirror (coordinator mirrors before merge; `crew:needs-mirror` holds
  the PR until then).
- Inline evidence rule for PR bodies: `## Test Output` and `## Acceptance
  Evidence` must paste command → output snippets and/or screenshots;
  path-only `evidence/` pointers are insufficient; `evidence/` stays the
  durable audit trail. Example in protocol §3; roles PR template and
  verification builder duty updated. (issue #98, 2026-10-29) Box skill copy:
  eng-pr-pipeline (protocol §3) needs mirror (coordinator mirrors after
  merge).
- README rewritten for first-time readers: what and why, plain-words how it
  works with the diagram, who it is for, what you get, and the v1 cut block
  kept. (issue #96, 2026-10-29) Box skill copy: no box skill change.
- Product-repo README seed `templates/product-readme.md`, a README install
  step in `docs/runbook-new-repo.md` (Step 6) and a normative README rule in
  `docs/protocol.md` section 8. (issue #96, 2026-10-29) Box skill copy: needed
  for `docs/protocol.md` and `templates/` (`crew:needs-mirror` until mirrored).
- README Status / v1 cut section: M1–M12 closed, in-cut vs out-of-cut (#80
  hold, product prove-its), Notion brief as gap-table north star. (#95,
  issue #94, 2026-10-29) Box skill copy: no box skill change.
- Root `AGENTS.md` thin review/build posture (blocking only for failed ACs,
  stage 7 gate, CI or security; wording and script edge cases are yellow
  follow-ups), required reading in the B1, B2, V1 and V2 templates, and a
  findings entry for the #74/#77/#88 round-burners (#93, issue #92,
  2026-10-29) Box skill copy: eng-pr-pipeline and eng-crew-roles get the "read
  AGENTS.md" line (coordinator mirrors after merge).
- Self-improve intake (M11): `docs/self-improve.md` (triggers, candidate card,
  accept/close, lesson path, `repo:` vs `crew:` scope, risks),
  `templates/intake-candidate.md`, the offline `scripts/intake-sweep.py` helper
  with `scripts/test-intake-sweep.py` (CI step), a weekly intake note in the
  stuck-PR sweeper template, coordinator/builder notes in `docs/protocol.md`
  and `docs/roles.md`, lesson `2026-10-29-self-improve-intake.md` and a
  findings entry. (#90, issue #89, 2026-10-29) Box skill copy:
  eng-pr-pipeline and eng-crew-roles (coordinator mirrors after merge).
- Metrics to decisions: `docs/metrics/decisions.md` (latency and rework
  sensors, windows, tunable thresholds, rollup vs per-repo, the `metrics-gate`
  issue, hold/waiver/lift), `scripts/metrics-decide.py` with fixture tests and
  a CI step, `templates/metrics-regression-issue.md`, gate notes in protocol
  section 6, `docs/roles.md` and the coordinator, builder, reviewer-validator
  and synthesizer templates, lesson `2026-10-29-metrics-to-decisions.md` and a
  findings entry. (#88, issue #86, 2026-10-29) Box skill copy:
  eng-pr-pipeline and eng-crew-roles (Ash mirrors before merge:
  `crew:needs-mirror` blocks the squash until the mirror comment is posted,
  protocol sections 6 and 7).
- Step-summary observe protocol (M8): `docs/observe.md` (when to write a step
  line, fields, `.crew/runs/` paths, promote the short summary onto the PR,
  what reviewers skim, risks), helper `scripts/step-summary.py` with
  `scripts/test-step-summary.py` (run in CI), `templates/step-summary.md`,
  builder, reviewer and synthesizer template notes, protocol §3 and roles
  pointers, `.gitignore` for raw step logs, lesson
  `2026-10-29-step-summary-observe.md` and a findings entry. (#87, issue
  #85, 2026-10-29) Box skill copy: eng-pr-pipeline and eng-crew-roles
  (coordinator mirrors before merge; `crew:needs-mirror` holds the PR until then).
- Verification protocol: typed runtime evidence as a merge gate. New
  `docs/verification.md` (shape table for web, CLI, service, API and mobile;
  docs-only N/A; fail-open), role duties in `docs/roles.md`, protocol §3, §7
  and Gate registry, and the B1, V1, V2 and synthesizer templates; starter
  adapters `templates/evidence/` (CLI exit/stdout, web screenshot); lesson
  `2026-10-29-typed-verify-evidence.md`, findings entry, required-docs pins and
  a `check-repo.py` `verification-shapes` rule with tests. (#84, issue #83,
  2026-10-29) Box skill copy: eng-pr-pipeline and eng-crew-roles (the mirror comment must land and clear `crew:needs-mirror` before merge).
- Synthesizer merge blockers: an open coordinator hold-until-X (or crew hold
  command) overrides standing doc-only merge-ok, and an open `steer cmd=rereview`
  at the current head blocks squash until a fresh `pass=verdict` lands on a
  different engine; protocol §7 and Gate registry, `templates/synthesizer.md`,
  lesson `2026-10-29-synthesizer-hold-race.md`, findings entry, and a
  `check-repo.py` static guard. (#82, issue #81, 2026-10-29) Box skill copy:
  eng-pr-pipeline (Ash mirrors before merge: `crew:needs-mirror` blocks the squash
  until the mirror comment is posted, protocol sections 6 and 7).
- Correction hierarchy in `docs/lessons/README.md` (architecture, types, lint, CI,
  prose last; "prose only, because ..." exception; new `encoded` status) and the
  first encoded lesson: `check-repo.py` rule `marker-sha` fails a `crew:v1` marker
  whose `sha=` is not a full 40-char SHA, with tests. (#77, issue #69,
  2026-10-28) Box skill copy: no box skill change.
- Merge-enforcement runbook with target rules, plan blocker, application,
  verification, rollback and fail-open; protocol §7 and onboarding pointers.
  (#67, 2026-10-28) Box skill copy: mirror needed (docs/protocol.md §7 pointer).
- Cycle-time and rounds metrics artifact: `docs/metrics/` (README, `prs.md`,
  `prs.csv`), `scripts/metrics-refresh.py` and its offline test, and a metrics
  refresh note in the stuck-PR sweeper template. (#75, issue #63,
  2026-10-28) Box skill copy: not mirrored here; templates/ note to be mirrored
  by the coordinator.
- Owner-SLA drill plan: `docs/metrics/owner-sla-drill.md` (synthetic hold, expected
  timestamps, checks, results table; coordinator owns the clock). (#71, issue #66,
  2026-10-28) Box skill copy: no mirror needed (no protocol or template change).
- Gardening findings buffer: `docs/findings/README.md` (how to append a smell,
  when to batch, ownership, entry template) and `docs/findings/buffer.md`
  seeded with the recurring builder B2 watch smell (PRs #35, #38, #41); lessons
  README points to it. (#78, issue #68, 2026-10-28) Box skill copy: no box
  skill change.
- Lessons log: `docs/lessons/README.md` (entry format and index) and
  `docs/lessons/2026-10-19-bottlenecks.md`. Added `CONTRIBUTING.md` (iteration
  process) and this changelog. (#15, 2026-10-20) Box skill copy: no box skill
  change.
- Architecture overview and docs index. (#8, 2026-10-20) Box skill copy: no box
  skill change.
- Crew collaboration-flow diagram. (#10, 2026-10-19) Box skill copy: no box skill
  change.
- Crew protocol doc: `docs/protocol.md` ports the eng-pr-pipeline protocol into
  the repo. (#14, 2026-10-20) Box skill copy: no box skill change.
- Roles, tiers and engines: `docs/roles.md` ports the `eng-crew-roles` box skill.
  (#13, 2026-10-20) Box skill copy: not edited (the doc is a port with no new
  policy).
- Routine and listener templates per role (`templates/`) and AgentConnect
  examples. (#16, 2026-10-20) Box skill copy: no mirror needed (new files only).
- Crew-flow diagram embedded in `docs/architecture.md`. (#22, 2026-10-20) Box skill
  copy: no box skill change.
- Onboarding runbook for a new repo: `docs/runbook-new-repo.md`. (#26, 2026-10-20)
  Box skill copy: no box skill change.
- CI repo guard: `scripts/check-repo.py` checks for secrets, required docs and
  sections, and relative links, with fixture tests. (#17, 2026-10-20) Box skill
  copy: no box skill change.
- Protocol: evidence a reviewer's verdict relies on is committed on the PR head,
  never a side branch; evidence-only changes get a rereview steer
  (`docs/protocol.md` §3, §6). New lessons entry
  `docs/lessons/2026-10-20-evidence-on-pr-head.md`. (#23, issue #19, 2026-10-20)
  Box skill copy: Ash (coordinator) updated the box eng-pr-pipeline skill in
  sync with this change.
- Lesson statuses use one vocabulary (`applied` / `superseded` / `open`) and were
  re-verified against `main`; new drift check `scripts/check-skill-drift.py`
  (with `scripts/test-check-skill-drift.py`) compares `docs/protocol.md` and
  `docs/roles.md` to the box skills, run by the coordinator on
  `crew:needs-mirror` and after protocol/template PRs. (#74, issue #70,
  2026-10-28) Box skill copy: not mirrored here; mirror by the coordinator if
  protocol/templates changed (this change touches neither).

### Changed

- `crew` CLI split per command (structural, no behaviour change):
  `scripts/crew` is a thin entry point that loads `scripts/crew.d/<cmd>.py`
  in sorted order (each module has `register(subparsers)` and `run(args)`),
  with the shared helpers in `scripts/crew.d/_shared.py`.
  `scripts/test-crew.py` is split into one `scripts/test-crew-<cmd>.py` per
  command, with its fixtures in `scripts/crew_testlib.py`; CI runs them by
  glob. `scripts/README.md` has one row per module and test file, and
  `docs/runtimes/tmux.md` one `### crew <cmd>` section per command with its
  usage line. No flag, output, exit code or file written changes, and
  `crew --help` lists the same 16 commands, now in sorted order. Adding a
  command now adds files only. (issue #224, PR #254, 2026-10-30) Box skill
  copy: none.
- Spec sync, part 2 of 2 (the #259 closing slice for M14 and M14.1),
  status-only: `docs/specs/portable.md` §5 marks 14.10 (#139), 14.1e
  (#234), 14.1h (#255) and 14.1i (#257) `done` from live issue state
  (#140 and #219 stay `open`); the README Status section lists `v1.0.0`
  (released, linked), M13 done except #140, M14 and M14.1 done, and R1 in
  progress with `v2.0.0` next; `docs/runtimes/README.md`,
  `docs/runtimes/tmux.md` (H1, intro) and the `docs/README.md` index drop
  "design" for shipped wording, with the pinned H1 updated in
  `scripts/required-docs.txt`; and the tmux placeholder-refusal paragraph
  now states the shipped #268 behaviour (resolved value, per command key).
  No requirement, rule or gate wording changes. Status-only spec edit under
  the owner's standing grant (#111). Refs #259, #110. (PR #271, 2026-10-30)
  Box skill copy: none.
- Post-R1 / M14.1 cleanups: `docs/release.md` drops "Nothing here is
  implemented yet" and the "R1.3 adds the row" wording, and names the merged
  workflow, bundle build and bundle attach PRs and the hand-released
  `v1.0.0`; `docs/interfaces.md` single-identity Scope allows an owner
  standing merge grant (the #111 grant) as an alternative to a per-change
  merge-ok, with no gate change; `docs/runtimes/tmux.md` documents
  `paths.eng_crew` next to the other profile paths; and
  `.github/workflows/release.yml` adds `scripts/release-bundle.py` and
  `scripts/test-release-bundle.py` to its `pull_request.paths` filter only.
  `crew:sensitive`: the owner approves the merge. Refs #110, #145, #233.
  (PR #252, 2026-10-30) Box skill copy: none.
- tmux briefs work in any repo (14.1d): every brief cites eng-crew docs as
  `<eng-crew>/docs/...` (new optional profile key `paths.eng_crew`), runs
  `crew` as `$CREW_BIN` and adds `-R <owner>/<repo>` to every `gh` command.
  The builder writes step summaries with `scripts/step-summary.py` to
  `.crew/runs/issue-<n>/build/summary.md` (fix rounds `pr-<pr>/fix-<k>/`).
  The coordinator drains with `crew drain`, arms the watcher with a
  one-shot `crew poll --once` source, starts validation only after the
  review pass says `pass`, and spawns the next round when a builder `done:`
  comes at the round's verdict head. The reviewer's idempotency check is per
  round, and a failing review pass posts the `changes` verdict itself. The
  synthesizer uses `crew land-lock acquire/release` and reads two new tmux
  options: `merge_grant` (standing grant scope, default `"none"`: per-PR
  merge-ok) and `hold_label_blocks` (default `true`); a grant gives
  permission only. Golden render fixtures and tests updated; `scripts/crew`
  docstring marks `--inputs` optional. Grok Bot templates unchanged. Refs
  #139. (issue #233, PR #244, 2026-10-30) Box skill copy: deferred to #140.
- Mirror hold gate is a drift check (#128): for a change touching
  `docs/protocol.md` or `templates/`, the coordinator's mirror comment counts
  only if it records the rendered output deployed to the live dir and
  `check-skill-drift.py --project` (plus `--only pipeline` when
  `docs/protocol.md` changed) exiting 0 at the last touching commit, with the
  commands and output inline. Who, label, lighter-lane exemption and
  fail-open are unchanged. Protocol §6, §7 and Gate registry, Grok Bot
  mirror hold gate, `CONTRIBUTING.md` "Two copies", portable spec P4 and §8,
  `scripts/README.md`, and a lesson. (issue #128, PR #227, 2026-10-30) Box
  skill copy: deferred to #140.
- Protocol preamble, §6, protocol freeze, gate contract, gate registry and §7
  reworded in glossary terms (`docs/concepts.md`): change, change head,
  verdict, narrative post, state tag, CI signal, wake event, tracker item /
  board, land, owner channel, backend. The gate registry gains a **Binding**
  column (core / runtime / backend). Builder watch and mirror hold become
  runtime gates in §7; their Grok Bot satisfaction rules move verbatim to
  `docs/runtimes/grok-bot.md` (Runtime gates). `docs/architecture.md` role
  table column "GitHub identity" is now "Identity", linked to the GitHub
  backend. Lesson hygiene note in the merge-gate watch-race lesson. Anchors
  and the `synthesizer-blockers` guard text are unchanged. No rule, gate, cap,
  marker field or label changes meaning. Closes M13 Phase A. (issue #119,
  PR #155, 2026-10-30) Box skill copy: deferred to #140.
- Protocol hard rules and §1–§5 reworded in glossary terms
  (`docs/concepts.md`): change, change head, verdict, narrative post, state
  tag, marker, CI signal, wake event, tracker item / board, land, owner
  channel, backend. GitHub and Grok Bot specifics stay only where the
  sentence links `docs/backends/github.md` or `docs/runtimes/grok-bot.md`;
  wake event names, labels, marker fields and `APPROVE` / `REQUEST_CHANGES`
  are kept. §1 is now "Roles and identities" (column "Identity"), with the
  old `#1-roles-and-github-identities` anchor kept; §2 stage 3 points to the
  runtime binding for the per-change watch. Lesson statuses re-checked;
  hygiene notes in the evidence-on-head and validation-gate lessons. No rule,
  gate, cap, marker field or label changes meaning. (issue #118, PR #153,
  2026-10-30) Box skill copy: deferred to #140.
- Routine templates moved under `templates/runtimes/grok-bot/` (`git mv`,
  contents unchanged apart from relative-link depth): B1, B2, V1, V2, S1,
  A1–A3, `wiring.md` and `reviewer-engines.md`. Runtime-neutral templates
  (evidence adapters, `step-summary.md`, `product-readme.md`,
  `intake-candidate.md`, `metrics-regression-issue.md`) stay in
  `templates/`. `templates/README.md` indexes both trees; links in docs,
  examples and lessons, `scripts/required-docs.txt` and the
  `synthesizer-blockers` guard path updated. The `crew:needs-mirror` rule
  keys on the `templates/` prefix and still covers the moved files; no rule,
  gate, cap, marker field or label changes meaning. (issue #117, PR #151,
  2026-10-30) Box skill copy: deferred to #140.

- Grok Bot runtime binding (`docs/runtimes/grok-bot.md`): routine-only
  mechanics moved verbatim out of the core. From protocol §6: per-PR watches,
  the verified B2 hand-off, comment-listener wakes and the lighter-lane
  routing paragraph; from the protocol: the pilot notes; from
  `templates/README.md`: event to consuming role, the lighter-lane routing
  note and routine limits. Each source spot keeps a one-line pointer; no
  rule, gate, cap, marker field or label changes meaning. Pinned in
  `scripts/required-docs.txt`, indexed in `docs/README.md`; lesson status
  paths updated. (issue #114, PR #147, 2026-10-30) Box skill copy: deferred
  to #140.

- Builder heartbeat and stuck-PR sweeper watchdog: builder workers refresh a
  `heartbeat:` line in their claim file every 5 min; the sweeper's `builder-silent`
  row flags a claim silent for 15 min and messages the builder. Bottleneck lesson
  #2 marked documented. (#72, issue #65, 2026-10-28) Box skill copy: not mirrored
  here; mirror by the coordinator.
- Templates match the lighter lane's B2/watch and mirror exemptions; reviewer
  verdict-pass messages route REQUEST_CHANGES, and sweeper/coordinator messages
  route red CI and close-out to the builder. Lane membership uses the full
  diff at head; fixes leaving the lane attach B2. Follows up the lighter-lane
  notes (Refs #55). (issue #57, 2026-10-25)
  Box skill copy: not mirrored here; mirror by the coordinator.

- The coordinator owns triage: a window at least once per awake half-day, and
  every open issue leaves it `crew:ready`, `crew:spec`, `crew:needs-md`,
  deferred to the next milestone, or closed with a reason. The stuck-PR sweeper
  promotes `crew:hold` / `crew:escalated` items waiting on the user for more
  than 2h (awake, PT) to `crew:needs-md`, routes nudge-cap escalations through
  the coordinator, skips held and needs-md PRs for stall nudges but lists them,
  and reports open issues with no `crew:*` state label older than one awake
  day. A reviewer-validator that holds its verdict for a user decision adds
  `crew:needs-md` and posts a `pass=hold` COMMENT review with `verdict=n/a`
  naming the open item (folds in #48). (#56, issue #51, 2026-10-25)
  Box skill copy: not mirrored here; mirror by the coordinator.

- Protocol and templates change in milestone batches, with a blocking-gate
  exception governed by a gate contract and registry. The lighter lane for
  non-protocol docs skips B2 and the mirror hold, keeps CI and review/validation,
  and routes fixes to the builder by message. (#55, issue #50, 2026-10-25)
  Box skill copy: not mirrored here; mirror by the coordinator.

- Owner decisions have a 2h awake-hours PT SLA, `crew:needs-md` escalation,
  timed defaults, and asks only through the coordinator. Standing doc-only
  merge-ok (excluding code, `.github/`, `templates/`, and `docs/protocol.md`)
  preserves all other merge gates. Onboarding requires Milestones and a
  Project board; closed milestones are frozen. (#54, issue #49, 2026-10-25)
  Box skill copy: not mirrored here; mirror by the coordinator.

- Merge gate requires the builder's `pass=watch` marker (full 40-char `sha=` of
  any commit on the PR, same rule as the reviewer cross-check) in protocol §7
  and the synthesizer template; a PR without it is held and the synthesizer
  pings the builder with priority. The reviewer's first verdict pings the
  builder with priority (still never creating B2). New lessons entry
  `docs/lessons/2026-10-23-merge-gate-watch-race.md` for the PR #41 hand-off
  race. A PR changing `docs/protocol.md` or `templates/` gets a
  `crew:needs-mirror` label from the reviewer's verdict pass; the merge gate
  refuses to merge while it is present, and the coordinator removes it on
  posting the box-skill mirror comment, then pings the synthesizer (new label in
  the runbook, architecture, wiring and role templates). The gate's external and
  cutover exemptions are now explicit with reasons, plus a third for
  coordinator-opened `crew:spec` PRs (no builder, no B2; merge on `/crew
  merge-ok`). A cutover PR is gated again as soon as its builder posts its watch
  review or any `crew:v1` marker after the cutover (by post time, covering B2
  attached at the unchanged cutover SHA), independent of the marker. The
  reviewer adds `crew:needs-mirror` before posting the verdict, but skips it
  when the coordinator's mirror comment is newer than the last
  protocol/template-touching commit (a later such commit needs a fresh mirror
  comment); the synthesizer uses the same freshness rule, and the synthesizer derives the
  hold from the changed paths, not only the label. (#45, issue #43, 2026-10-23) Box
  skill copy: not mirrored here; mirroring the box eng-pr-pipeline skill is for
  Ash.
- Reviewer watch cross-check accepts a `pass=watch` marker whose full 40-char
  `sha=` is any commit on the PR, not only the head (the marker is posted once
  per PR, so a CI-fix push before the first verdict must not look like a missing
  watch); `<sha7>` wording in the protocol now includes review headers; the
  "Stale known-gap bullet" lessons entry gains its status and linked-issue
  fields. (#44, issue #42, 2026-10-23) Box skill copy: mirror of the box
  `eng-pr-pipeline` skill is for the coordinator (Ash).
- Watch hand-off: the routine folder id is the single identifier written to
  `watches/pr-<n>.b2`; the B1 run only requests the hand-off and the parent turn
  alone verifies, writes the marker file and posts `pass=watch`; every marker's
  `sha=` is the full 40-char head SHA and the reviewer cross-check matches on it.
  Stale #19 known-gap bullet updated. New lessons entry
  `docs/lessons/2026-10-23-watch-handoff-first-run.md`. (#41, issue #39,
  2026-10-23) Box skill copy: mirror of the box `eng-pr-pipeline` skill is for
  the coordinator (Ash).
- `docs/protocol.md` links `docs/roles.md` (and its worktree isolation section)
  directly instead of calling it planned; removed the resolved #29 entry from the
  runbook's known gaps. `docs/README.md` moves `scripts/` to Available now, and
  the Planned section now says nothing is planned. (#40, issue #29, 2026-10-23)
  Box skill copy: no box skill change.
- Aligned the live `crew:needs-md` label description on eng-crew with the runbook
  ("Blocked on an owner decision (recommended default + deadline)") and removed
  the resolved #28 entry from the runbook's known gaps. (#38, issue #28, 2026-10-23)
  Box skill copy: no box skill change.
- Engine-steer example uses the actual-builder-engine wording and links
  `docs/roles.md#actual-builder-engine`. (#35, issue #34, 2026-10-23) Box skill
  copy: no box skill change.
- Merge-ups use no review round: a clean merge-up after an APPROVE gets a formal
  merge-up re-approve with the same round; after CHANGES it gets an ack with no
  round and no verdict; a conflict resolution that changes behavior is a normal
  round. The #16 ack-based merge-gate exception is removed from the reviewer,
  synthesizer and sweeper templates. (#32, 2026-10-21) Box skill copy: the box
  eng-pr-pipeline skill already has this rule; the repo mirrors it.
- Actual builder engine: a round's builder engine is the engine that actually
  wrote its commits, named in the fix note, an `Engine:` commit trailer and the
  builder marker; the reviewer must differ from it. If the builder marker and the
  fix note or commit trailer disagree on the engine, the note or trailer wins,
  and before merge the reviewer re-checks at head (fresh review + validation) on
  an engine different from the actual builder engine, triggered by the
  coordinator's rereview steer. (#33, 2026-10-21) Box skill copy:
  the box eng-pr-pipeline skill already reads the engine that actually wrote the
  round; the eng-crew-roles box skill still needs the mirror (flagged to the
  coordinator).
- Builder per-PR watch B2 attachment is verified and observable: builder parent
  turn lists routines, confirms the four events, records `watches/pr-<n>.b2`
  and posts a `pass=watch` marker; sweeper `no-builder-watch` row and
  detection-window note; reviewer first-verdict cross-check; protocol event
  list and runbook B2 creation point corrected. New lessons entry
  `docs/lessons/2026-10-23-builder-watch-attach.md`. (#37, issue #36,
  2026-10-23) Box skill copy: the box `eng-pr-pipeline` skill mirror (the `watch`
  pass value in §4, B2 events `ci-failed`, `review-changes-requested`,
  `pr-merged`, `pr-closed` in the §6 builder line, and the attach-verification
  step) is applied by the coordinator before merge per R4. AC1 dry run on PR #37
  recorded in the lessons entry.

### Fixed

- tmux crew placeholder paths (#139 N1): `crew` now checks the **resolved**
  `paths.*` value, whichever layer set it, so a project `crew.toml` that
  omits `paths.state_dir` (falling back to `<state-dir>` in
  `profiles/default.toml`) is refused, exit 1, instead of putting the land
  lock under `<cwd>/<state-dir>/`. Each command checks only the keys it
  uses: every command checks `state_dir`; `spawn`, `kill`, `down` and
  `restart` also check `worktree_root`; only `spawn builder`, whose brief
  pins `<toolchain-bin>`, checks `toolchain_bin`. Tests in
  `scripts/test-crew.py` cover an omitted key, an explicit placeholder and
  real paths. Also (#139 N6): `crew kill` of a validate run removes the
  round's `verdicts/pr<n>-<sha7>-r<k>-verdict.md`, and kill removes the run's
  `runs/**/<window>[.-]*` files, including subdirectories such as
  `runs/body/`, never another window's. Roadmap 14.1j. (issue #265, refs
  #139, PR #268, 2026-10-30) Box skill copy: none.
- tmux verdict state tags and owner asks from the #139 live run (N5, N4):
  the reviewer pass that posts the verdict then sets the state tags per
  protocol §4 (`pass`: add `crew:approved`, remove `crew:in-review` and
  `crew:changes`; `changes`: add `crew:changes`, remove `crew:in-review` and
  `crew:approved`). The coordinator's `pr-merged` close-out also removes
  `crew:in-review` and `crew:changes` if present. The coordinator posts and
  closes owner asks on a PR as COMMENT reviews (`[<CoordinatorBot>/ask]`)
  with a `pass=steer cmd=ask` / `cmd=ask-closed` marker, never as plain PR
  comments. Golden fixtures under `scripts/fixtures/render/tmux/` updated.
  Roadmap 14.1k. (issue #266, refs #139, PR #267, 2026-10-30) Box skill
  copy: deferred to #140.
- tmux briefs from the #139 live run (F4, F5 brief side, F6): the
  coordinator brief renders the profile `merge_grant`; a merge-ok ask never
  carries an auto-apply merge default (its deadline default is `hold` or an
  escalation), and a merge-ok is recorded only from the owner's own words or
  a profile `merge_grant` that covers the PR, never from a repo-specific
  grant in eng-crew's protocol prose such as §6's standing doc-only
  merge-ok. The synthesizer brief agrees: with `merge_grant = "none"` it
  lands only with a per-PR owner merge-ok marker at head. Both briefs pass
  `--project "$CREW_PROJECT"` (the absolute project `crew.toml`), never a
  relative `crew.toml`. On `pr-merged` the coordinator removes
  `crew:approved` and `crew:hold` from the PR and `crew:ready` from the
  closed issue, and deletes the merged head branch only for a merged
  same-repo PR, using its `headRefName`, never the default or base branch
  (else it skips and says why). Golden fixtures under
  `scripts/fixtures/render/tmux/` updated; Grok Bot renders unchanged.
  Roadmap 14.1h. (issue #255, refs #139, PR #256, 2026-10-30) Box skill
  copy: deferred to #140.
- tmux crew restart, hooks dialog and state fixes from dry run 2 (#234 N2,
  N3 code side, N4, N5, N7, N8, F15) and the #139 live run (F5, F7):
  `crew restart` of a builder whose last line is `done: #n #pr sha` restarts
  as `--pass fix --pr <pr>`, never a second build pass; the watcher queues a
  `dialog` wake (action `escalate`) on the next scan when a run shows a
  trust or Codex hooks-review dialog, instead of after `--stale`; every
  Codex pass runs `-s workspace-write --add-dir <state-dir>/<owner>__<repo>`,
  so review and validate can write `$CREW_STATUS` and `verdicts/`; `crew
  spawn` adds `.crew/` to the worktree's `info/exclude`; every window gets
  `CREW_PROJECT`; the watcher handles SIGHUP like SIGTERM; the stale wake
  key ignores the liveness class; commands refuse a profile whose
  `state_dir`, `worktree_root` or `toolchain_bin` is still a placeholder;
  `crew kill` removes all of the run's `runs/<window>.*` files. Tests in
  `scripts/test-crew.py`; `docs/runtimes/tmux.md` updated. Roadmap 14.1f.
  (issue #250, refs #139, PR #260, 2026-10-30) Box skill copy: none.
- tmux briefs from dry run 2 (#234 N1, N2 and N3, brief side): the
  coordinator brief never types into a role window on a `dialog` wake or an
  `ambiguous` `stale:` wake; it kills and respawns the window once when its
  launch options should have prevented the prompt, else asks the owner with
  the window name and `crew attach WINDOW --rw`. The builder build pass looks
  for an open PR that closes the issue and adopts it as a fix round instead
  of opening a duplicate. The builder branch is `builder/<n>-<slug>`, not an
  unrendered `<role>/`. Golden fixtures under `scripts/fixtures/render/tmux/`
  updated; Grok Bot renders unchanged. Roadmap 14.1g. (issue #251, refs #139,
  PR #253, 2026-10-30) Box skill copy: deferred to #140.
- tmux crew review rounds, claims and probes from the #139 dry run (B2 code
  side, F3, F4, F7, F17, F18, F20, F21, `verdicts/` cleanup): `crew poll`
  emits `fix-at-head` (to the reviewer, with round `k`) when a builder fix
  note lands at the head of a `verdict=changes`, so an evidence-only fix no
  longer deadlocks round 2, and `ci-passed` records carry the round `k`;
  reviewer claims (`reviewer-pr<n>-<sha7>-r<k>-<pass>`) and worktrees carry
  the round and pass, so review and validate run in parallel; `done:` is
  terminal (no restart, skipped by the watcher) only for reviewer and
  synthesizer runs, so a builder that dies after `done:` is detected and
  restartable; Codex's `Hooks need review` dialog probes `ambiguous`; the
  synthesizer takes the tier's first engine as is; a dead pane reads `dead`
  at spawn, not `export`; `crew kill` removes a reviewer run's verdict
  files. Tests in `scripts/test-crew.py`; `docs/runtimes/tmux.md` updated.
  Roadmap 14.1c. (issue #232, refs #139, PR #247, 2026-10-30) Box skill
  copy: none.
- tmux crew process, env and safety fixes from the #139 dry run:
  `crew kill` and `crew down` SIGTERM the pane's process group, SIGKILL
  what is left after 2 s and check it is gone (Codex ignores the SIGHUP of
  `kill-window`); `crew guard` is a no-op unless `CREW_ROLE=coordinator`,
  so the project Stop hook no longer blocks role windows; a Codex
  coordinator is pre-trusted for the project, and a Claude Code trust
  dialog is documented and probes `ambiguous` in `crew status`, which now
  has a coordinator row; `CREW_SANDBOX_ENV` reaches every window, not only
  Codex role windows; `crew up` prints render output only on failure; every
  window gets `CREW_BIN`, the absolute path of this checkout's
  `scripts/crew`. (issue #231, refs #139, PR #240, 2026-10-30) Box skill
  copy: none.
- `crew kill` refuses to remove unlanded work: before removing a run's
  worktree it lists uncommitted and untracked paths and commits not
  contained in a fresh fetch of the default branch, the run's branch or the
  run's PR head; if any, it still stops the window but keeps the worktree
  and state files, prints the items and exits 1. `crew kill --discard
  --reason "<why>"` removes anyway after posting the reason on the run's PR
  or issue; `--discard` without `--reason` is refused. `crew down` keeps the
  session and names the windows holding unlanded work. Tests with a temp git
  repo and a bare remote in `scripts/test-crew.py`; `docs/runtimes/tmux.md`
  kill section updated. (issue #172, PR #221, 2026-10-30) Box skill copy:
  none.
- Crew-flow diagram: builder engine order and escalation arrow. (#12, 2026-10-20) Box
  skill copy: no box skill change.
- A failed validation pass never becomes an APPROVE: protocol (stage 7 and merge
  gate) and templates now say so; AC4 consumers and a stale live claim corrected.
  (#25, 2026-10-20) Box skill copy: the gate rule and the AC4 exception are both in
  the box skill; the repo mirrors them.

## Bootstrap (2026-10-19)

### Added

- Framework spec (`docs/specs/framework.md`), README and CI (markdownlint and an
  offline link check). Direct commit to main (no PR). Box skill copy: no box skill change.
