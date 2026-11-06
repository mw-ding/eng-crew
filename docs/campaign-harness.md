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
- **source:** the eng-crew checkout under test and its full `HEAD` SHA;
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
`crew up`, spawn, teardown). It re-resolves both profiles and exits 2,
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
pinned eng-crew checkout, so a step calls its CLIs.

The committed specs live in `scripts/fixtures/campaign/`, one line per
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
- A21 from #798
- A22 from #799
- A23 from #802
- A24 from #803
- A27 from #800

Profile changes a run needs, such as precheck on, path classes or a role
engine order standing in for a quota steer, go in an `--org-profile` file
under the sandbox state root. The pinned sandbox profile never changes, so
the guard check still passes.

Children get the sandbox profile as `CREW_PROJECT`, no other inherited
`CREW_*` variable, no `TMUX` or `TMUX_PANE`, `<state>/bin` first on `PATH`,
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
- A20
- A21
- A22
- A23
- A27

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
terminal status line, and runs `crew reviewer-pool` with
`CREW_POOL=reviewer`, as the reviewer lead does on a nudge. A07 seeds
`schedule/target.json` so the reviewer cap, not the ramp, is the limit it
exercises.

### Scheduler scenarios (A08 to A10)

A08 to A10 drive `crew schedule decide`, `release`, `snapshot` and
`summary`, and `crew watch`, the way the leads and the watcher call them.
They read each decision back from the call's JSON and from
`schedule/decisions-*.jsonl`, which keeps the walk order and the
`lead-down` drops. Leads get demand through `crew lead handoff`, and
busy builders come from `crew spawn`. Machine signals and time are
injected as follows:

- **Thresholds and caps:** a small org profile under `<state>/` sets the
  load watermarks, `schedule_ramp`, `max_load`, `stuck_after` or the
  present caps (`--org-profile`). The sandbox profile stays pinned.
- **Memory pressure:** a `sysctl` stub on `PATH` answers macOS levels 1, 2
  or garbage (unknown). So the memory steps assume a macOS host.
- **Gateway errors:** the stub builder prints a declared Codex 429 or 503
  line on its pane, and `crew watch` records it.
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
| S11 consolidation | `crew lead capacity` removed | A08 `up-tracker-milestones-and-leads` |

A09 covers held demand (#639, #712): a held item is never granted, held or
deferred, and never counts as demand for T.

### A11 and A32

A11 and A32 (from #790) take the same approach as A06 and A07 for the
standard PR loop and engine routing. A step pushes a commit with its
`Engine:` trailer and writes the PR view, CI and verdict markers. A11 seeds
red CI and a bad precheck report, then repairs both.

### A12

A12 (from #791) pushes a sample CLI, service and API from
`scripts/fixtures/campaign/A12-sample/` and captures each with
`evidence-cli.py`. Its `repro.py` plays the validator: it refuses a capture
whose SHA is not the head of a fresh clone, reruns the `sh` block there and
compares exit, stdout and stderr. `crew train check` then reads scripted PR
bodies and fix reviews for the evidence gate.

### A13

A13 (from #792) plays the tool merge-up, the builder's conflict repair and
the reviewer's delta verdict through git and scripted PR views. It runs
`crew content` on the four pinned SHAs, `crew train check`, `build` and
`close` (which routes the dropped members), and stands in for each squash
land with a direct push to the sandbox origin's `main`.

### A14

A14 (from #793) runs `crew train build`, `wait`, `land` and `land-lock` on
the sandbox repo. `a14/gh`, first on `PATH`, plays the forge: `pr create`
answers PR 49+N for `crew/train-N`, `pr checks N` is red while `gh/red-N`
exists, and `pr merge` squashes onto the sandbox origin's `main` only while
the PR head is still the `--match-head-commit` SHA. Every other call goes
to the campaign `gh` stub.

### A20

A20 (from #796) installs from a local bundle. It builds two releases with
`release-bundle.py` into a `mirror` source under the sandbox state root, and
its org pack profile and `manifest.toml` pin carry `paths.eng_crew`, the
source, the identities and the control item. `a20/forge.sh` answers a ready
repo for `crew doctor`. Steps set `HOME` to the sandbox, so doctor reads no
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
which keep each post. After each sweep is reaped, a step runs `crew drain`
as the coordinator would, so the next sweep is not reaped by the previous
`done:` wake.

### A23

A23 (from #802) runs `crew runner` from the sandbox checkout against
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

### A27

A27 runs `crew feedback` against the fake forge and reads each posted card
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
step types the outgoing team's `crew handoff stopped` into that team's
window 0 as a short `sh <script>` line (a terminal line over about 1 KiB is
never read), so the detached actor must outlive the session it tears down.
Teardown kills only the pinned session, so A28's last step takes the second
team down.

## Cleanup checks

After teardown the run records both checks below in its result:

1. **Sentinel:** `campaign-guard.py sentinel MANIFEST` re-hashes the
   outside-sandbox file. Exit 0 prints `sentinel unchanged`; exit 1 (changed
   or missing) is a P0 isolation finding.
2. **Retained work:** teardown uses `crew kill` and `crew down`, which keep a
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
  --production crew.toml --source . --release "$RELEASE" \
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
  `crew spawn` takes the repo from the profile's checkout: repo
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
python3 scripts/campaign-sandbox.py plan-forge --repo OWNER/NAME --production crew.toml
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

### Level c: owner-run devices and second environment

Level c reuses
[#209](https://github.com/mw-ding/eng-crew/issues/209),
[#716](https://github.com/mw-ding/eng-crew/issues/716) and
[#213](https://github.com/mw-ding/eng-crew/issues/213), with the same
scenario IDs and manifest. Record each host's capability, OS, runtime, bundle
and profile fingerprints in the run issue. Loopback counts as simulated. A
real-device criterion stays open until the owner records the run.
