# Campaign harness contract

**Status:** level-a contract, built by #783 (M25 item 25.01). The scenario
runner (25.02, #784) is `scripts/campaign-run.py`; the disposable sandbox setup (25.03) build on it. Design:
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

## Scenario runner and results

`campaign-run.py MANIFEST --scenarios DIR --out FILE` runs the guard check
first; a refusal writes nothing and exits 2. Select scenarios with
`--scenario Axx` (default: every manifest scenario); an ID outside the
manifest is refused. Each `DIR/<Axx>.json` lists public-CLI `run` steps with
an expected exit, and explicit `wait` steps that poll a file for a match up
to a deadline instead of sleeping a fixed time. Children get the sandbox
profile as `CREW_PROJECT`, no other inherited `CREW_*` variable, and the run
seed as `CAMPAIGN_SEED`.

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
