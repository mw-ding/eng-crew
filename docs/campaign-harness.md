# Campaign harness contract

**Status:** level-a contract, built by #783 (M25 item 25.01). The scenario
runner (25.02, #784) is `scripts/campaign-run.py`; the disposable sandbox
setup (25.03, #785) is `scripts/campaign-sandbox.py`. Design:
the M25 integration campaign proposal on
[#782](https://github.com/mw-ding/eng-crew/issues/782).

Every M25 run touches only a recorded disposable sandbox: its own repo (a
local repo with a bare origin at level a), state root, worktree root, live
directory and tmux session. It never touches the live crew's session or
state, or the production repo. This page is the contract a run follows
before, during and after it mutates anything.
`scripts/campaign-guard.py` enforces its first two parts.

## Run manifest

Before any mutation the harness writes a run manifest with
`campaign-guard.py manifest`. It resolves the sandbox profile and pins:

- **repo:** the sandbox profile's `owner/name`;
- **profile:** the sandbox profile's absolute path and sha256, plus the
  production profile's path (the reference the guard compares against);
- **source:** the mdstack checkout under test and its full `HEAD` SHA;
- **release:** the installed release id the run exercises;
- **target:** the tmux session and the absolute `paths.state_dir`,
  `paths.worktree_root` and `paths.live_dir`;
- **sentinel:** an outside-sandbox file and its sha256;
- **run:** the run id and the scenario IDs (Axx) it covers.

The manifest is written only when the refusal check below passes and
`--out` resolves, symlinks followed, inside a sandbox root; any other
destination is refused with `refused: out:`. Raw run
logs stay under the sandbox state root; results are promoted to the run
issue as inline proof, never committed.

## Refusal before mutation

`campaign-guard.py check MANIFEST` runs before every mutating step (setup,
`mdstack up`, spawn, teardown). It re-resolves both profiles and exits 2,
printing one `refused: <reason>` line per problem, when:

- the sandbox names the production repo;
- the sandbox session is the production session;
- a sandbox root equals, contains or sits inside a production root;
- a sandbox root is still a `<placeholder>`;
- the sandbox profile changed since the manifest, its resolved repo, session
  or roots differ from the pins, or the source checkout moved off the pinned
  SHA.

Exit 0 prints `ok: run <id> targets <repo> (session <name>)`. A refusal
stops the run; never edit the manifest to get past one. Write a new
manifest for a new run instead.

Every child the harness starts gets the sandbox project file explicitly
(`--project` and `CREW_PROJECT`), so an inherited production `CREW_PROJECT`
or `CREW_STATE` cannot select the target. Use session-targeted tmux
operations only: never `kill-server` or global options.

An inherited `$TMUX` beats `TMUX_TMPDIR`: from a crew pane, a bare
`TMUX_TMPDIR=<sandbox> tmux kill-server` kills the owner's default server
([#817](https://github.com/mw-ding/eng-crew/issues/817)). So every harness
tmux call pins the sandbox socket, `<state>/tmux/tmux-<uid>/default`, with
`-S` and drops `TMUX` and `TMUX_PANE`. Scenario steps get the same pin from
the `<state>/bin/tmux` shim. It refuses any `-L`, and any `-S` naming
another socket, with exit 2. When debugging from a crew pane, run
`unset TMUX TMUX_PANE` first and call tmux only through the shim or with
`-S` on a throwaway socket.

## Scenario runner and results

`campaign-run.py MANIFEST --scenarios DIR --out FILE` runs the guard check
first; a refusal writes nothing and exits 2. It reruns the check before
every `run` step; a refusal there marks the scenario `BLOCKED`, the rest
`NOT RUN`, stops the run and exits 2. Select scenarios with
`--scenario Axx` (default: every manifest scenario); an ID outside the
manifest is refused. Each `DIR/<Axx>.json` lists public-CLI `run` steps with
an expected exit, and explicit `wait` steps that poll a file for a match up
to a deadline instead of sleeping a fixed time. `{source}` expands to the
pinned mdstack checkout, so a step calls its CLIs.

The committed specs live in `dev/tests/scripts/fixtures/campaign/`, one line per
scenario in ID order:

- A01 from #786
- A02 from #786
- A03 from #787
- A04 from #787
- A05 from #787
- A06 from #788
- A07 from #788
- A08 from #789
- A09 from #789
- A10 from #789
- A13 from #792
- A14 from #793
- A15 from #794
- A16 from #794
- A17 from #795
- A18 from #795
- A19 from #797
- A21 from #798
- A22 from #799
- A23 from #802
- A24 from #803
- A25 from #804
- A26 from #804
- A27 from #800
- A31 from #804

Profile changes a run needs, such as precheck on, path classes or a role
engine order standing in for a quota steer, go in an `--org-profile` file
under the sandbox state root. The pinned sandbox profile never changes, so
the guard check still passes.

Children get the sandbox profile as `CREW_PROJECT`, no other inherited
`CREW_*` variable, no `TMUX` or `TMUX_PANE`, no forge token (`GH_TOKEN`,
`GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN`), no SSH
agent (`SSH_AUTH_SOCK`, `SSH_AGENT_PID`), `GH_CONFIG_DIR` set to
`<state>/gh-config`, `<state>/bin` first on `PATH`,
the stub logs `<state>/stub.log` and `<state>/gh.log`, the fake forge
directory `<state>/gh` as `CAMPAIGN_GH_DIR`, and the run seed as
`CAMPAIGN_SEED`.

Scenarios that change crew state each run in a fresh sandbox: one `setup`,
`campaign-run.py --scenario Axx` and `teardown` per scenario. They are, one
line per scenario in ID order:

- A03
- A04
- A05
- A06
- A07
- A08
- A09
- A10
- A13
- A14
- A15
- A16
- A17
- A18
- A20
- A21
- A22
- A23
- A25
- A26
- A27
- A31

When tmux is installed, the runner starts a decoy session on a throwaway
socket outside the sandbox and exports it as `TMUX`. If the decoy is gone
after a scenario, that scenario is `FAIL` (`decoy: ...`), the rest are
`NOT RUN` and the run stops: an inherited `TMUX` reached a server outside
the sandbox.

Results keep five statuses apart:

- `PASS`: every step met its expected exit or match;
- `FAIL`: a command exit differed or a wait hit its deadline;
- `BLOCKED`: a tool the scenario requires is missing;
- `LIMITATION`: the scenario declares a known gap and is not run; only the
  owner can accept it;
- `NOT RUN`: a manifest scenario not selected or without a spec.

Each step records the command's own exit, stdout and stderr apart from the
capture outcome, so a working capture never reads as a pass. The results
file is rewritten atomically after each scenario, only inside a sandbox root.
The seed (random unless `--seed` is given) fixes the scenario order and
`CAMPAIGN_SEED`; `--rerun RESULTS` replays the same selection and seed, so
the same events and failure recur. The runner exits 0 only when every
result is `PASS`.

Each scenario's notes follow under its own heading, in ID order.

Contributor note: `.gitattributes` marks this page `merge=union` (#1112).
A local merge-up of two campaign PRs that each add a list line or a notes
section at the same place keeps both sides, with no manual resolution. Union
merge suits append-only edits only. A reorder or rewrite of existing text can
merge into duplicated or garbled text with no conflict to flag it, so such a
change still needs a normal review of the merged result. Two lines added at
one place can land out of ID order; restore the order in the merge-up commit.
GitHub's server-side mergeability check is not documented to honour the
attribute, so a PR may still show as conflicting there and still needs the
builder's local merge-up.

### A06 and A07

The stubs take no model turns, so A06 and A07 play the worker's and the
lead's part through public CLIs. A step writes a reviewer's section file and
terminal status line, and runs `mdstack reviewer-pool` with
`CREW_POOL=reviewer`, as the reviewer lead does on a nudge. A07 seeds
`schedule/target.json` so the reviewer cap, not the ramp, is the limit it
exercises.

### Scheduler scenarios (A08 to A10)

A08 to A10 drive `mdstack schedule decide`, `release`, `snapshot` and
`summary`, and `mdstack watch`, the way the leads and the watcher call them.
They read each decision back from the call's JSON and from
`schedule/decisions-*.jsonl`, which keeps the walk order and the
`lead-down` drops. Leads get demand through `mdstack lead handoff`, and
busy builders come from `mdstack spawn`. Machine signals and time are
injected as follows:

- **Thresholds and caps:** a small org profile under `<state>/` sets the
  load watermarks, `schedule_ramp`, `max_load`, `stuck_after` or the
  present caps (`--org-profile`). The sandbox profile stays pinned.
- **Memory pressure:** a `sysctl` stub on `PATH` answers macOS levels 1, 2
  or garbage (unknown). So the memory steps assume a macOS host.
- **Gateway errors:** the stub builder prints a declared Codex 429 or 503
  line on its pane, and `mdstack watch` records it.
- **Time:** a step backdates `schedule/target.json` (`changed`, `starts`),
  `errors.jsonl` timestamps or a reservation's `time`, instead of waiting
  out `schedule_interval`, the 10-minute error window or `reservation_ttl`.
- **Zero cap:** a fake signed away record with `cap`, behind
  `away-control.json`.

| Build issue | Shipped behaviour | Scenario steps |
| --- | --- | --- |
| S1 caps-only admission | No load gate by default; the optional `max_load` ceiling defers | A10 `memory-load-high-unknown-holds` (high load moves only T), `floor-passes-target-ramp-signal-ceiling` |
| S2 snapshot | Every input or `unknown` | A08 `up-tracker-milestones-and-leads`, A10 `up-three-busy-builders`, `memory-load-high-unknown-holds` |
| S3 gateway errors | Declared pane text, one record per source and text | A10 `declared-429-503-pane-text-recorded-once` |
| S4 ranking | Classes 1 to 8; milestone, critical path, then age | A08 `rank-finish-first-caller-only-grants`, `red-default-branch-fix-ranks-class-1` (open `main-red` issue, #1072) |
| S5 target | Watermarks, interval, hysteresis, ramp, floor of 1 | A10 `errors-high-drop-to-floor-busy-drain`, `between-holds-clear-grows`, `memory-load-high-unknown-holds`, `ramp-bounds-other-starts` |
| S6 builder decide | Caller-only reservations, holds, `lead-down`, release, TTL, floors | A08 every step |
| S7 reviewer decide | Reviewer floor under builder load; a held review granted on the next reviewer call | A08 `builder-first-hold-then-reviewer-grants`, A10 `floor-passes-target-ramp-signal-ceiling` |
| S8 overlap dispatch | Excluded: closed unbuilt (owner decision 2026-11-03, D + S9) | none |
| S9 overlap trains | Clean overlap lands in one train | A14 (25.xx train runs), not A08 to A10 |
| S10 summary and stuck alarm | Summary line, on watcher wakes too; one `schedule-stuck` wake for finishing work | A09 summary checks, A10 `stuck-alarm-finishing-work-once` |
| S11 consolidation | `mdstack lead capacity` removed | A08 `up-tracker-milestones-and-leads` |

A09 covers held demand (#639, #712): a held item is never granted, held or
deferred, and never counts as demand for T.

### A11 and A32

A11 and A32 (from #790) take the same approach as A06 and A07 for the
standard PR loop and engine routing. A step pushes a commit with its
`Engine:` trailer and writes the PR view, CI and verdict markers. A11 seeds
red CI and a bad precheck report, then repairs both.

### A12

A12 (from #791) pushes a sample CLI, service and API from
`dev/tests/scripts/fixtures/campaign/A12-sample/` and captures each with
`evidence-cli.py`. Its `repro.py` plays the validator: it refuses a capture
whose SHA is not the head of a fresh clone, reruns the `sh` block there and
compares exit, stdout and stderr. `mdstack train check` then reads scripted PR
bodies and fix reviews for the evidence gate.

### A13

A13 (from #792) plays the tool merge-up, the builder's conflict repair and
the reviewer's delta verdict through git and scripted PR views. It runs
`mdstack content` on the four pinned SHAs, `mdstack train check`, `build` and
`close` (which routes the dropped members), and stands in for each squash
land with a direct push to the sandbox origin's `main`.

### A14

A14 (from #793) runs `mdstack train build`, `wait`, `land` and `land-lock` on
the sandbox repo. `a14/gh`, first on `PATH`, plays the forge: `pr create`
answers PR 49+N for `crew/train-N`, `pr checks N` is red while `gh/red-N`
exists, and `pr merge` squashes onto the sandbox origin's `main` only while
the PR head is still the `--match-head-commit` SHA. Every other call goes
to the campaign `gh` stub.

### A15 and A16

A15 and A16 (from #794) play the synthesizer's §7 check through
`mdstack train check` and `mdstack train land`, and its direct land through
`mdstack land-lock` and the `a14/gh` forge's head-bound `pr merge`.
`a15/view.py` writes a PR view that passes every scripted gate at its
head; each argument injects one miss. Profile changes (`lone_pr_land`,
`merge_grant` and its scope, a control item) go in `--org-profile` files.
Each §7 row is exercised, or names why the run does not:

| §7 row | Where |
| --- | --- |
| Ownership record | A15: unreadable record refuses check and land |
| Approval at head | A15: stale verdict, failed validate, changes verdict |
| Later changes request | A15: changes verdict; rework steer and formal review in `test-crew-train.py` (#1118) |
| Merge permission | A15: none or stale merge-ok; A16: grant, head-scoped merge-ok |
| Sensitive, spec | A15: no merge-ok; A16: grant never covers sensitive, spec needs scope |
| Hold, escalation, coordinator hold | A15: labels, hold-until; A16: hold posted after approval |
| Project landing stop | A16: close, restart, moved head, stop-id resume |
| Rereview | A15: open rereview blocks; engine comparison is the synthesizer's (A32) |
| Pre-review check | Not in `train check`; the synthesizer runs `crew-precheck.py` (A11) |
| Evidence | A15: missing proof; capture and reproduction in A12 |
| Runtime gates | A15: `crew:needs-mirror`; builder watch is Grok Bot only (M15.1) |
| Tested with default branch | A15: lone direct waiver, two ready train; train state in A14 |
| CI, draft, mergeable, base | A15 |
| Linkage | Manual in `train check`; the synthesizer's read |
| Post-land main CI | Synthesizer brief step 4, checked as rendered; red-main rank in A08 |

Express self-gates are A17's (#795). The asynchronous land alternative
needs an async change backend, which the sandbox profile does not declare.
The lone-or-train choice, inbox holds and the post-land CI read are model
steps with no CLI, so A15 checks the rendered synthesizer brief for them.

### A17 and A18

A17 and A18 (from #795) play the express and solo lanes through the CLIs
that read them: `item-flavor.py`, `crew-config.py class-flavor --express`,
`crew-precheck.py --pass selfgate`, `mdstack poll`, `mdstack route` with
`mdstack reviewer-pool`, `mdstack train check` and `land`, and `mdstack spawn`,
`mdstack lead handoff` and `mdstack send` for solo. The stubs take no model
turns, so the builder's self-gate sub-session and the owner's solo session
are played by the selfgate record and commits they would post.
`a17/view.py` writes a PR that passes the express gate at its head: the
coordinator's express item record on the linked issue, a signed selfgate
pass, the changed files and owner merge-ok. Each argument injects one
change. A solo PR drops `crew:express` and adds `crew:solo`.

The pinned sandbox profile keeps the default `selfgate_engine`
(`different`). Same mode runs only with an `--org-profile` file under the
sandbox state, so it never reaches the default. A tightening class for the
rename case comes from another such file. After a reviewer is killed, a step
runs `mdstack schedule release` for its PR, because the reaped grant would hold
a reviewer slot until `reservation_ttl`
([#1070](https://github.com/mw-ding/eng-crew/issues/1070)). The attended
owner session for A18 at level b needs a forge sandbox and stays with
level b.

### A19

A19 (from #797) replays every declared operation without a live session.
`a19/replay.py` discovers the shipped harness and session backend adapters
and reads the declared rows from the
[adapter modules](runtimes/harness-adapters.md#adapter-modules) table and the
session backend [Operations](runtimes/session-backends.md#operations) and
capability tables. `a19/ledger.json` must name exactly those adapters and
rows. Each entry is one of:

- `oracle`: the adapter declares the row, and the named tests replay it on
  fake binaries;
- `default`: the row is absent, and the spec's default is what the tests
  prove;
- `gap`: a quote from the adapter's spec section, or an undocumented
  `finding`;
- `unsupported`: the row is absent, with a quote saying why.

Refusal and ambiguous cases, and the Grok Bot runtime gaps (C1, C2, C3 and
C5 accepted under #150), carry the same spec link. Every anchor, quote and
test is checked, and each test file runs once. A gap is never counted as
conformant.

Installed CLIs and live Grok mirror or watch proof need their own
environment, so A19's scripted steps do not run them (#1439).
`a19/smoke.py` runs once per installed harness and session backend
binding, from an operator shell, never from CI. It drives one disposable
run through the runtime's own code: launch, a `ready` line, the `mdstack
send` doorbell, the inbox `ack:`, the C5 probe and the pane stop. tmux uses
a dedicated server named for the run. herdr uses its local server and
closes only the run's own workspace. Each JSON line pins the source SHA,
both adapter files' sha256 and the harness and backend versions.
A binding that is not installed, has no interactive launch or is skipped by
policy (`--skip`) is reported as blocked.

The ledger's `live` section names every harness and backend binding, plus
each runtime's mirror and watch. Each entry is one of:

- `evidence`: the source SHA, the versions and a link to the smoke capture;
- `fail`: the same for a run that did not finish, plus the finding filed for
  it, so a failure is never recorded as a gap or a block;
- `block`: the installation, version, account and sandbox facts, with a
  link to the capture that shows them;
- `unsupported`: a quote from the adapter's spec section.

A documented gap stays a gap even when its binding passes the smoke. Docker
cannot supply live Grok mirror or watch proof.

### A20

A20 (from #796) installs from a local bundle. It builds two releases with
`release-bundle.py` into a `mirror` source under the sandbox state root, and
its org pack profile and `manifest.toml` pin carry `paths.mdstack`, the
source, the identities and the control item. `a20/forge.sh` answers a ready
repo for `mdstack doctor`. Steps set `HOME` to the sandbox, so doctor reads no
host config.

### A21

A21 plays Riley with `state/riley.py`, typed into a researcher window: it
answers only the newest signed coordinator request with question, scope,
deliverable and source issue, else writes `blocked: #<n> request unclear`.
Its finding goes through the fake forge and is copied to
`state/gh/posted-<n>.md` for the oracles.

### A22

A22 enables triage through an `--org-profile` file and plays Riley's sweep
with `state/triage.py` in the `riley-sweep` window, in shadow mode only.
`state/forge.py` plays the forge's issue store and the owner's `triage:`
replies in `state/gh/issue-list-open.json` and `issue-list-closed.json`,
which keep each post. After each sweep is reaped, a step runs `mdstack drain`
as the coordinator would, so the next sweep is not reaped by the previous
`done:` wake.

### A23

A23 (from #802) runs `mdstack runner` from the sandbox checkout against
forge-less hosts in an `--org-profile` file. `a23/ssh`, installed as
`<state>/bin/ssh`, loops each call back to the real `crew-remote.py`
entrypoint on a host root under the sandbox state, with the caller's whole
environment, so only the entrypoint's scrub keeps tokens out of a job. A
`<state>/a23/faults` line `HOST VERB down|lost` drops one call before or
after the host acts. A host running an older entrypoint copy gives the
refusal, and a host without the entrypoint gives the failure.

### A24

A24 (from #803) cuts a release in a bare clone of the source under
`state/a24`: a fragment, the cut PR head and its merge commit on the
clone's `main`. It runs `release-trigger.py`, `release-check.py` and
`release-bundle.py` as `release.yml` does, with the `GITHUB_*` variables
set. `a24/forge.py` writes the merged cut PR, its merge-ok markers and the
`ci.yml` runs into `api.json`. The publish job's tag and Release writes are
never run, and a step checks `gh.log` holds reads only.

### A25

A25 (from #804) plays the coordinator's away and away-return records into
the fake forge (`state/rec.py`) and the Slack webhook with a loopback server
(`state/hook/hook.py`, mode `ok`, `reject` or `hang`). It backdates a pending
message's `next` instead of waiting out the retry, and writes an owner ask's
`asks/<n>.json` a few seconds ahead in a PT offset.

### A26

A26 (from #804) pauses by not running the watcher or `mdstack poll` while it
moves the forge, backdates the triage slot, and plays a sweep's end with
`state/played-sweep.py` and a `done:` line.

### A27

A27 runs `mdstack feedback` against the fake forge and reads each posted card
from `state/gh/bodies.log`. It caps the researchers with two deep dives so
the milestone-close sweep queues, then plays that sweep with
`state/sweep.py`. The sweep reads the closed milestone's issues from
`issue-list-all.json`, and a number in `state/refuse` stands in for a
provider safety refusal. Each played model call is logged in
`state/model.log`.

### A28

A28 (from #801) runs two sandbox teams on the one repo: the second team's
checkout, profile and roots sit inside the sandbox, and each team's
`runtime.instance` and control item come from its `--org-profile` file. A
step types the outgoing team's `mdstack handoff stopped` into that team's
window 0 as a short `sh <script>` line (a terminal line over about 1 KiB is
never read), so the detached actor must outlive the session it tears down.
Teardown kills only the pinned session, so A28's last step takes the second
team down.

### A31

A31 (from #804) puts a scenario `gh` (`state/m31/bin/gh`) first on `PATH`
for `metrics-refresh.py` only, answering from a two-repo history in
`state/m31/history.json`. The metrics-gate hold, waiver and intake
acceptance are the coordinator's judgement, so steps play them as labels
and records. The report from actual campaign records is
`scripts/campaign-report.py` ([metrics README](metrics/README.md#campaign-history-report)).

## Cleanup checks

After teardown the run records both checks below in its result:

1. **Sentinel:** `campaign-guard.py sentinel MANIFEST` re-hashes the
   outside-sandbox file. Exit 0 prints `sentinel unchanged`; exit 1 (changed
   or missing) is a P0 isolation finding.
2. **Retained work:** teardown uses `mdstack kill` and `mdstack down`, which keep a
   worktree with uncommitted or unlanded work and record it. The run lists
   every retained worktree and its unlanded commits. A discard happens
   only with an explicit recorded discard, which is the owner's choice and is
   never part of an automatic cleanup. Evidence and logs under the sandbox
   state root stay until the run's results are posted.

A run whose cleanup checks were not recorded counts as `NOT RUN`, not as a
pass.

## Sandbox setup and runbook

`scripts/campaign-sandbox.py` (25.03) sets up and tears down the disposable
sandbox. Level a is built; level b is a print-only plan; level c reuses the
owner-run issues.

### Level a: local repo and bare origin

```sh
python3 scripts/campaign-sandbox.py setup --root "$SANDBOX" --run-id "$RUN" \
  --production config.toml --source . --release "$RELEASE" \
  --sentinel "$OUTSIDE_FILE" --scenario A01
python3 scripts/campaign-run.py "$SANDBOX/state/manifest.json" \
  --scenarios "$SCENARIOS" --out "$SANDBOX/state/results.json"
python3 scripts/campaign-sandbox.py teardown "$SANDBOX/state/manifest.json"
```

`setup` refuses before any write when `$SANDBOX` exists and is not empty
or overlaps a production root. It then creates:

- `origin.git`, a bare origin, and `repo`, its clone seeded on `main` with
  `ci.sh`, the local CI fixture (a scenario sets `CI_RESULT` to replay a red
  run);
- `repo/crew.toml`, the sandbox profile, excluded from git because
  `mdstack spawn` takes the repo from the profile's checkout: repo
  `campaign/sandbox-<run>`, tmux session `crew-campaign-<run>`, `state`,
  `wt` and `live` roots under `$SANDBOX`, and `toolchain_bin` set to
  `state/bin`;
- `state/bin/claude` and `state/bin/codex`, engine stubs with no model.
  Each runs bash under the engine's name, so the liveness probe sees that
  harness. It acks each `inbox: <id>` line in `$CREW_STATUS` and runs a
  typed `campaign-exec: <sh>` line. `state/bin/gh` is the fake forge: it
  logs every call and answers from `$CAMPAIGN_GH_DIR/<cmd>-<sub>[-<arg>].json`
  (for example `pr-list.json` or `pr-view-5.json`), written by the scenario.
  A `--label L` query reads `<cmd>-<sub>-label-L.json` first, so held
  items (`issue-list-label-crew:hold.json`) differ from the open issue list.
  A call with `--state S` reads `<cmd>-<sub>-S.json` next, so open and closed
  issue lists can differ. A `--body-file -` call's body is appended to
  `$CAMPAIGN_GH_DIR/bodies.log` after a `--- gh <args>` line.
  Once the scenario writes `$CAMPAIGN_GH_DIR/api.json`, a map from paths below
  `repos/<owner>/<name>/` to answers, `gh api` reads from it and keeps each
  posted comment, so a control item holds its handoff record. Its `fail`
  count fails the next posts, with `fail_mode: lost` landing them first, and
  a `post-probe` script's output is kept on each comment it posts;
- `state/sandbox.json`, the control item (number 1, label
  `integration:run`), the ten crew labels plus `integration:finding` and
  `integration:run`, the fixture identities and the CI fixture;
- `state/manifest.json`, the guarded run manifest above;
- when tmux is installed, `state/bin/tmux`, the socket-pinning shim, with
  its socket under `state/tmux/` (recorded as `tmux` in `sandbox.json`).

`teardown` runs the guard check first and refuses on drift. It kills only
the exact sandbox session on the sandbox socket
(`tmux -S <socket> kill-session -t =<session>`), lists every
repo or worktree with uncommitted or unpushed work, and checks the sentinel.
It records all three in `state/cleanup.json`. Exit 1 means the sentinel
changed: a P0 isolation finding. After the results are posted,
`teardown --remove` deletes `$SANDBOX`, but only when nothing is retained,
the sentinel is unchanged and `state/sandbox.json` marks it as a sandbox.
Otherwise it keeps the tree for the owner's recorded discard.

### Level b: forge sandbox (blocked, owner account access)

Level b needs a disposable forge repo and accounts from the owner. Never
create one yourself, and never use the production repo. To print the
operations the owner's setup performs, without running any of them:

```sh
python3 scripts/campaign-sandbox.py plan-forge --repo OWNER/NAME --production config.toml
```

The plan covers the private repo, the ten crew labels and the two
`integration:*` labels, collaborator invitations for the builder and
reviewer identities, the seed push with `.github/workflows/ci.yml` copied from
the source, and the control issue. Once the owner has provided the repo:

1. Run the plan's operations as the owner, or have the owner approve them.
2. Write a sandbox profile naming that repo, its identities, its own session
   and absolute roots outside every production root.
3. Write the manifest with `campaign-guard.py manifest`, then follow
   [docs/runbook-new-repo.md](runbook-new-repo.md) for the first crew run.
   Each scenario passes only on its recorded markers, heads, CI and cleanup.

### Lab hosts in Docker

`environments/terminal/remote/lab/crew-lab-docker.py` (M20.1 lab C, #1357)
adds role-host containers, built from the [lab image](runtimes/multi-device.md#remote-acceptance-criteria-and-the-local-lab),
to a level-a run. Each command runs the guard check first.

```sh
python3 environments/terminal/remote/lab/crew-lab-docker.py setup "$SANDBOX/state/manifest.json" \
  --image "$LAB_IMAGE" --stage "$BUNDLE_STAGE" --tag "$TAG" [--source-sha SHA] [--n3]
python3 environments/terminal/remote/lab/crew-lab-docker.py n3 "$SANDBOX/state/manifest.json"
python3 environments/terminal/remote/lab/crew-lab-docker.py teardown "$SANDBOX/state/manifest.json"
```

- **Manifest.** `setup` adds a `lab` section to the run manifest: the Docker
  context and its endpoint, the run ID, the owner label, the image ID, the
  staged bundle hashes, and each network, container and volume ID as Docker
  returns it, with each host's published port and activation record (bundle,
  SHA256SUMS and source SHA); a host that activated another bundle or source
  SHA than the staged one stops setup. It refuses before any Docker mutation when the
  manifest already has a `lab` section, an alias is not lowercase, or a
  container or network with a planned name or the run's label exists. A new
  lab run needs a new manifest.
- **Isolation.** Every child gets only `PATH` and locale plus the run's own
  `HOME` and config directories under `state/lab/`: no inherited
  `CREW_*`, forge token, SSH agent, `TMUX` or `TMUX_PANE`. Docker calls go
  to the pinned endpoint. No host gets a mount: not the owner's home, the
  Docker socket or a tmux socket. SSH is published on `127.0.0.1` only, and
  `state/lab/home/.ssh/config` maps each alias to `127.0.0.1:<port>` with
  a per-run key and `known_hosts`.
- **N3.** Each host gets its own network. With `--n3` those networks are
  internal, nothing is published, and a driver container joins all of them.
  `n3` probes from each host to the other hosts, the Mac and the internet,
  with the driver reaching each host as the positive control; with `--n3`
  each host maps `host.docker.internal` to the host gateway, so the Mac
  probe tests routing, not name lookup. It reports `n3: unproved` (exit 1)
  unless every lateral probe is denied; an unresolved name is not denied,
  and a loopback setup is always unproved.
- **Teardown.** It first inspects every recorded ID and refuses, removing
  nothing, when the context now points at another endpoint or a live ID lost
  the run's owner or run label. Otherwise it saves each resource's inspect
  JSON and logs under `state/lab/evidence/`, then removes only those IDs. It
  never prunes, removes by wildcard or kills a tmux server. It records the
  sentinel check and a tmux decoy's survival in `state/lab/cleanup.json`;
  exit 1 means a changed sentinel or a lost decoy.

### Lab runner scenarios

`environments/terminal/remote/lab/crew-lab-scenarios.py` (M20.1 lab F, #1360)
drives `mdstack runner` over the real hardened SSH call to a loopback lab
host, between `setup` and `teardown`:

```sh
python3 environments/terminal/remote/lab/crew-lab-scenarios.py "$SANDBOX/state/manifest.json" \
  --stage "$BUNDLE_STAGE" [--host lab-a] [--only NAME]
```

- **Client.** The primary runs the staged bundle itself, verified by
  `scripts/crew-install.py` into `state/lab/toolkit/` and refused unless
  its digest is the one the hosts activated, so both ends run one version.
  macOS `ssh` reads `~/.ssh/config` from the account's home, never `HOME`,
  so `state/lab/bin/ssh` adds `-F state/lab/home/.ssh/config` to `ssh -G`
  only. Each call still runs the client's own `-F none` argv. The client
  carries a decoy `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK` and `CREW_*`.
- **Sample.** Branch `lab` of the sandbox repo has a `check-repo` that prints
  its OS and any forge, crew or agent variable it sees, and
  `dev/tests/lab/test-lab.py`, which each scenario commits red, green or
  slow.
- **Scenarios.** They start from A23's oracles. `exact-head`: the stored
  result at HEAD matches the same commands run locally, and the host job
  sees a clean env. `red`: a red run, not a fallback. `idempotent`: a
  repeated request ID returns its first reply, and a new one for the job ID
  returns the first job. `stale`: a stale head is refused before any call,
  and an unseeded head by the host.
- **Injections.** Each one is confirmed by a `version` call that fails
  while it holds and answers once it is lifted. `disconnect` is
  `docker network disconnect` mid-job, with the container and runner pids
  kept: the client falls back locally, and after reconnect the same job's
  result is pulled, with no second job at that head. `pause` is the
  unresponsive host: the client falls back, and the job finishes after
  `unpause`. `runner` kills the runner only: the supervisor starts a new
  one, `sshd` keeps its pid, and a job passes. `recreate` replaces the
  container mid-job (label-checked, with a new ID, host key and port, the
  manifest and SSH config updated): the client falls back, the host never
  reports the lost job done, and a fresh job passes. `partition` disconnects
  a role host: over real SSH it is `unreachable`, placement queues a role
  run that needs it rather than placing it elsewhere, and the item's claim
  file is unchanged. Remote role runs and their reconcile wait for #345 and
  #347.
- **Attach (#348).** A run is planted as the runner account in the
  runner's tmux session, since `spawn` needs a forge (#345 proves it on
  fakes). Over real SSH, `capture` shows its pane and `logs` its step
  summary tail. A client on a pty attaches through the `restrict,pty` key
  line, read-only, so typed keys never reach the pane, and detaches with
  exit 0. Attach without a TTY and `version` with one are refused.
- **Report.** Each scenario prints `PASS` or `FAIL`, and
  `state/lab/scenarios.json` keeps what it saw. Exit 1 on any `FAIL`, 2 on
  a refusal.
- **Evidence.** Each run writes `state/lab/runs/<started>.json` and a
  Markdown copy with `crew-lab-evidence.py` (M20.1 lab G, #1361). They
  record lab C, each host's container, network, port, host key and
  activated bundle and source SHA, the image digest, the staged bundle
  hashes, the client bundle, the transport, every injected event with its
  Docker control, and a timeline. The record is `simulated` and never
  `real_device`: the loopback SSH path and each injection are labelled
  simulated, and the sample checks and the partition's claim and identity
  are labelled stubs. A scenario `--only` left out is `skipped` with
  `evidence: false`, so it supplies no evidence for #207 or #345–#348.

### Level c: owner-run devices and second environment

Level c reuses
[#209](https://github.com/mw-ding/eng-crew/issues/209),
[#716](https://github.com/mw-ding/eng-crew/issues/716) and
[#213](https://github.com/mw-ding/eng-crew/issues/213), with the same
scenario IDs and manifest. Record each host's capability, OS, runtime, bundle
and profile fingerprints in the run issue. Loopback counts as simulated. A
real-device criterion stays open until the owner records the run.

### Attended owner-channel and sleep run

`scripts/campaign-attended.py` (#1463, part of #804) runs A26 around an
actual sleep of the owner's Mac, with one real sandbox Slack delivery. It
splits A26 at its first `resume-*` step. Before the sleep it runs the
handled head and the forge moving while paused. It then sends one `ask`
through `mdstack notify` under a sandbox away record, starts builder #3 as
existing work, and snapshots the claims, worktrees and tmux windows. After
the wake it checks the snapshot is unchanged and takes the receipt code. It
then runs the resume steps: the missed head, red CI and one overdue sweep,
each caught up exactly once. The result holds the before-sleep and
after-resume timestamps, the sleep length and each owner unblock.

Rehearsal first, by the crew at any time, with no owner step:

```sh
python3 scripts/campaign-sandbox.py setup --root /tmp/att-r1 --run-id att-r1 \
  --production config.toml --source . --release "$RELEASE" \
  --sentinel "$OUTSIDE_FILE" --scenario A26
python3 scripts/campaign-attended.py /tmp/att-r1/state/manifest.json \
  --scenarios dev/tests/scripts/fixtures/campaign \
  --out /tmp/att-r1/state/attended.json --dry-run
python3 scripts/campaign-sandbox.py teardown /tmp/att-r1/state/manifest.json
```

Keep the root short: the tmux socket path must fit the OS limit. A dry run
posts to a loopback webhook and never sleeps. It prints and records
`rehearsal` and `evidence: false`, so it never counts as #804 evidence.

The owner's part, at a time agreed on #804 with no other lab journey
running on the Mac:

1. Before: create a Slack incoming webhook on a sandbox channel the live
   crew does not use. In the owner's own terminal, not a crew pane, run
   `export CAMPAIGN_WEBHOOK=<url>`. Never paste the URL into the tracker, a
   file or a crew window. The driver refuses a URL that is not https or that
   equals the live crew's own webhook.
2. Start: run the setup and driver commands above, without `--dry-run`,
   in that terminal.
3. Sleep: when the driver prints `owner: sleep this machine now`, choose
   Apple menu > Sleep, or close the lid. Stay asleep for at least `--gap`
   (default 60 s); 10 minutes is better. While asleep, read the receipt
   code from the Slack message on another device.
4. Wake: log in. The driver sees the wall-clock jump and asks for the code.
   Type it.
5. After: the crew posts the result's summary inline on #804, runs
   teardown and records the sentinel and retained-work checks.

Physical test boundary. The run proves:

- a real OS sleep of one Mac with every sandbox process suspended;
- the channel accepted the message and the owner read it on a device;
- the missed state and the overdue sweep catch up once after the wake;
- the claims, worktrees and windows survive the sleep.

It does not prove a forge that moves during the sleep: the forge is local,
and A26 moves it just before the sleep. Nor does it prove overdue time from
the sleep itself (A26 backdates the triage slot), delivery while asleep,
network or power loss, a second device or real GitHub (level b). The sandbox
uses its own profile and session. The live crew's profile is read only to
refuse its webhook; its channels and webhook are never used or changed.
