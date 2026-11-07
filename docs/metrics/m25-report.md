# M25 final regression, coverage and owner report

**Last updated:** 2026-11-07

Item 25.27 ([#806](https://github.com/mw-ding/eng-crew/issues/806)) of the M25
integration campaign. Design and scenario oracles:
[#782](https://github.com/mw-ding/eng-crew/issues/782#issuecomment-6624869508);
harness contract: [campaign-harness.md](../campaign-harness.md); finding
register: [#805](https://github.com/mw-ding/eng-crew/issues/805#issuecomment-6693583068).

## TL;DR and owner asks

- **Final SHA:** `a135a4d56e252b0b81a2651fe20873a71e455f3d`, the `main` head
  when the run started, with CI green there: 69 test files, 0 failed
  ([run 42317388723](https://github.com/mw-ding/eng-crew/actions/runs/42317388723)).
- **Scripted set at that SHA:** 29 committed scenarios, each in its own fresh
  level-a sandbox, seed 806. **28 PASS, 1 FAIL** (A04, a stale fixture, not a
  product defect: [#1174](https://github.com/mw-ding/eng-crew/issues/1174)).
  A22 needs a lowercase run id ([#1177](https://github.com/mw-ding/eng-crew/issues/1177)).
  Every sentinel unchanged; the only retained trees are the three scenarios'
  deliberate dirty worktrees.
- **Owed merged-head reruns:** all run at the final SHA. Each fix's oracle
  passes, the existing workarounds removed (A26 without the milestone trigger,
  A17 without the `schedule release` call, the #814 dependency dispatch).
- **New findings, filed as intake cards, none P0/P1:** two register rows
  confirmed as product gaps (row 34 → [#1175](https://github.com/mw-ding/eng-crew/issues/1175),
  row 36 → [#1176](https://github.com/mw-ding/eng-crew/issues/1176)) and two
  harness fixture issues (#1174, #1177).
- **Open P0/P1 in M25:** none besides #806. The repo's 14 open P1s have no
  milestone and predate M25 ([list](#open-p0p1)).
- **Not proven:** level b (real forge and engines in a sandbox) never ran,
  because no disposable forge repo was provided. Level c (devices, hosts,
  full-team handoff) moved to M25.1 by owner decision. Real-engine evidence
  here is the production crew's own M25 fix loop, observed, not a sandbox run.

**Owner asks:**

1. Accept, or reject one by one, the limitations in
   [Limitations for the owner to accept](#limitations-for-the-owner-to-accept).
2. With those accepted, M25 can close; the M25.1 trackers keep the level b/c
   proof open.

## Run manifest

| Field | Value |
| --- | --- |
| Source | Original run: eng-crew checkout at `a135a4d` (clean). PR-head reproduction (PR #1186 R1/R2): `7af7c39`, which adds only this report and its fixtures, so product code is identical |
| Release | `source-a135a4d` for the original run, `source-7af7c39` for the reproduction: the source checkout in both; A20 builds and installs its own two bundles |
| Profile | per-run sandbox profile written by `campaign-sandbox.py setup`; production reference `crew.toml` of the live crew |
| Level | a: local repo and bare origin, real sandbox tmux on the sandbox socket, engine and forge stubs |
| Seed | 806 (scenario order and `CAMPAIGN_SEED`) |
| Driver | [`scripts/fixtures/campaign/m25-final/run.sh`](../../scripts/fixtures/campaign/m25-final/run.sh): setup, `campaign-run.py --scenario`, teardown per scenario; `run.sh <production crew.toml> auto scripts/fixtures/campaign` reruns the set, `... auto variants` the variants |
| Variants | [`scripts/fixtures/campaign/m25-final/variants.py`](../../scripts/fixtures/campaign/m25-final/variants.py) derives the owed reruns and probes from the committed specs |
| Cleanup | `teardown` per scenario: sentinel re-hash, retained-work list, exact-session kill |
| Engine of this run | claude-code, claude-opus-5-5, effort medium (builder session); scripted steps take no model turns |

## Scripted set at the final SHA

Original run at `a135a4d`, one fresh sandbox per scenario, 2026-11-07
00:24–00:48Z: wall time 1390 s for 29 scenarios (A02 alone 366 s). The PR-head
reproduction at `7af7c39` gave the same results; durations vary per run.

| ID | Result | Notes |
| --- | --- | --- |
| A01 | PASS | |
| A02 | PASS | |
| A03 | PASS | retained: deliberate dirty builder worktree (C6) |
| A04 | FAIL | `merge-missed-while-watcher-down-reconciled`: `KeyError: 'body'` in `route.py` `dependents()`. Same result on a second run. The fixture's `issue-list.json` has no `body`; real `gh --json number,body` always returns it. #1066 (A04) merged 6 minutes before #1063 added the lookup, and CI does not run campaign scenarios, so A04 had not run against it. With `body` added, every step passes (variant below). [#1174](https://github.com/mw-ding/eng-crew/issues/1174) |
| A05 | PASS | retained: deliberate dirty worktree |
| A06 | PASS | |
| A07 | PASS | |
| A08 | PASS | |
| A09 | PASS | |
| A10 | PASS | |
| A11 | PASS | |
| A12 | PASS | |
| A13 | PASS | |
| A14 | PASS | |
| A15 | PASS | |
| A16 | PASS | |
| A17 | PASS | |
| A18 | PASS | |
| A20 | PASS | includes `upgrade-reloads-roles-coordinator-last` |
| A21 | PASS | |
| A22 | PASS | with run id `m25f-a22`. The first run used `m25f-A22` and failed its duplicate-key oracle: the product lowercases source keys, the oracle does not. [#1177](https://github.com/mw-ding/eng-crew/issues/1177) |
| A23 | PASS | includes the decoy-credential checks from #1152 |
| A24 | PASS | |
| A25 | PASS | |
| A26 | PASS | |
| A27 | PASS | |
| A28 | PASS | retained: second team's deliberate worktree |
| A31 | PASS | |
| A32 | PASS | |
| A19 | NOT RUN | no spec; #797 moved to M25.1 (live Grok readiness) |
| A29 | NOT RUN | level c, #213 in M25.1 |
| A30 | NOT RUN | level c, #209/#716 in M25.1 |

## Merged-head reruns owed by the fix loop

From the [#806 steer](https://github.com/mw-ding/eng-crew/issues/806#issuecomment-6695662481)
and the [#805 dispositions](https://github.com/mw-ding/eng-crew/issues/805#issuecomment-6693609168).
All fixes are ancestors of the final SHA.

| Fix PR | Issue | Oracle at the final SHA | Result |
| --- | --- | --- | --- |
| #1148 | #1087 | A20 last step, upgrade reload on sandbox tmux, role windows kept, coordinator last | PASS |
| #1149 | #1098 | A26 variant: empty baseline, issue filed during the pause, **no** closed milestone. First resume scan slot `started`, exactly one sweep | PASS |
| #1150 | #1050, #1070 | A17 variant with every `crew schedule release` after a reaped reviewer removed: the next pass is admitted at once, before the TTL. A07 committed spec | PASS |
| #1152 | #1106 | A23: decoy `GH_TOKEN`/`GITHUB_TOKEN`/`SSH_AUTH_SOCK` absent from the job | PASS |
| #1154 | #1118 | A15 committed spec; the later-changes-request row itself is unit-tested (`test-crew-train.py`, green in CI at the final SHA), not a scenario step | PASS (scenario); row covered by CI only |
| #1162 | #1042 | No campaign scenario (async backend not in the sandbox profile). R1–R3 recorded at `7390ed7` ([comment](https://github.com/mw-ding/eng-crew/issues/1042#issuecomment-6697897071)); unit tests green at the final SHA | CI only |
| #1153 | #1088 | A20 | PASS |
| #1159 | #1089 | A20 | PASS |
| #1163 | #1124 | A09, A27 | PASS |
| #1165 | #818 | A03–A05 and A28 run the crew on the sandbox's own tmux server; no decoy loss | PASS (sandbox). Adoption on the live crew is not part of this run (isolation contract) |
| #1063 | #814 (row 44) | A04 variant `dependency-merge-wakes-coordinator-for-dependent-814`: watch ends `poll: pr-merged`, one queued `pr-merged` with `consumer=coordinator`, `dependents=["#7"]` | PASS |
| #1117 | #743 (row 32) | A23 variant: `crew host check` reaches every host's check verb and classifies it (loop: runner down; skew: refused; gone: failed). A positive automatic pick needs the host runner service, which opens tmux on the default socket; the sandbox shim refuses that by design | check verb PASS; automatic pick BLOCKED at level a |

## Register rows carried to #806

Rows 34–46 of the register, as PASS, FAIL, BLOCKED, NOT RUN or a limitation.

| Row | Class | Result |
| --- | --- | --- |
| 34 | queued sweep slot never reflects the later start | **FAIL, confirmed.** A26 variant: after the dequeued sweep finishes, `sweep.json` still reads `queued`; a newly closed M5 starts no sweep in 3 scans (want 3 sweeps, got 2). Up to `interval_hours` delay. [#1175](https://github.com/mw-ding/eng-crew/issues/1175) |
| 35 | calibration-day proposal counting | NOT RUN: owner semantics decision first (P3) |
| 36 | first lead ack lacks a status directory | **FAIL, confirmed.** After `crew up` there is no `status/`; `crew send builder-lead … --wait-ack 10` exits 3 though the lead received the line. Fresh state roots only. [#1176](https://github.com/mw-ding/eng-crew/issues/1176) |
| 37 | failed A28 leaves team b's session | NOT RUN (needs a forced A28 failure); the session stays on the sandbox socket. Follow-up |
| 38 | solo feedback reaches the builder-lead inbox | NOT RUN; guards hold in A18 PASS. Follow-up P3 |
| 39 | A20 bad-checksum injection can be a no-op | NOT RUN as a separate proof; A20 PASS. Follow-up |
| 40 | A20 dry-run snapshot omits `.git/info/exclude` | NOT RUN; follow-up |
| 41 | A28 stress lacks an `armed == 20` assertion | A28 PASS; assertion not added. Follow-up |
| 42 | A32 argv claim wider than its assertions | A32 PASS; claim not narrowed. Follow-up |
| 43 | committed-scenario index omits specs | still true: the index in campaign-harness.md omits A11, A12, A20, A28, A32. Follow-up P3 |
| 44 | composed dependent-dispatch scenario | **PASS** (above) |
| 45 | real forge/model integration, installed adapters | BLOCKED: no forge sandbox or accounts. Limitation L1 |
| 46 | owner channel, campaign-history report, sleep, hosts, full-team handoff | BLOCKED: owner-run, M25.1 (#804, #209, #716, #213). Limitation L2 |

## Real-engine journeys

No sandbox real-engine run happened (L1). The representative real-engine
journeys are the production crew's own M25 fix PRs: real builders, real
independent reviewer-validators, real CI and synthesizer land. They are
observed records, not sandbox runs.

| PR | Builder | Reviewer-validator | Rounds | Open → land | Path |
| --- | --- | --- | --- | --- | --- |
| #1148 | claude-code, claude-opus-5-5 | codex, gpt-6.1-sol | 1 | 8 m 38 s | direct land |
| #1149 | claude-code, claude-opus-5-5 | codex, gpt-6.1-sol | 1 | 21 m 14 s | verdict carried, `content=identical` |
| #1150 | claude-code, claude-opus-5-5 | codex, gpt-6.1-sol | 1 | 17 m 56 s | verdict carried, `content=identical` |
| #1152 | claude-code, claude-opus-5-5 | codex, gpt-6.1-sol | 1 | 9 m 20 s | thorough flavor; standing grant merge-ok |
| #1159 | claude-code, claude-opus-5-5 | muse, tbh-1005a | 1 | 59 m 07 s | Codex safety refusal, parked, owner rerouted to Muse |
| #1163 | claude-code, claude-opus-5-5 | codex, gpt-6.1-sol | 1 | 50 m 50 s | owner merge-ok ask (gate contract) |
| #1165 | claude-code, claude-opus-5-5 | codex, gpt-6.1-sol | 1 | 13 m 09 s | direct land |
| #1169 | claude-code, claude-opus-5-5 | codex, gpt-6.1-sol | 1 | 6 m 40 s | P0 main-red fix, direct land |

Open → reviewer ack took 2–2.5 minutes on every PR. Median open → land is
15.5 minutes; the two long ones waited on the owner. Every verdict was round 1.

## Cost and usability

- **Scripted set:** zero model turns; 1390 s local wall time; no CI minutes
  beyond the normal PR runs.
- **Real-engine journeys:** about 3 engine sessions per PR (builder,
  reviewer-validator, synthesizer), about 24 across the 8 PRs. Token and quota
  counts are not exposed: `unknown`.
- **This report:** one claude-code builder session (claude-opus-5-5, medium)
  plus one research sub-agent (about 173k tokens).
- **Human unblocks across M25:** owner hold and lift after #817 killed the
  owner's tmux server twice (2026-11-04); the 21:28Z server loss (#1155,
  #1156); seven P1 scope decisions on #985; one provider safety refusal
  rerouted (#1159); one merge-ok ask (#1163); the level a/b scope decision on
  #1101.
- **Flakes:** one, `test-docs-scan.py` on a transient git lock (#1168, fixed in
  #1169). The campaign failures here were deterministic and repeated.
- **Friction seen:** committed scenarios drift silently because CI does not run
  them (#1174); the A22 oracle depends on run-id case (#1177); the campaign
  doc's scenario index lags (row 43).

## Inventory to scenario traceability

Areas from the design's feature-to-spec map. Level a is this run; b and c did
not run.

| Area | Scenarios | Level a at the final SHA |
| --- | --- | --- |
| Configurable core, team and repo settings | A01 | PASS |
| Renderer, notes, drift, budgets | A02 | PASS |
| Packs, interfaces, role registry | A01, A02, A19 | PASS; A19 NOT RUN (M25.1) |
| tmux startup, topology, worker lifecycle | A03, A05 | PASS |
| Wake, poll, watcher, routing | A04, A06, A26 | A04 FAIL (fixture, #1174; variant PASS); A06, A26 PASS |
| Runtime contract C1–C9 | below | |
| Leads, retention, reap | A06, A07 | PASS |
| Scheduler S1–S7, S9–S11 | A08–A10, A14, A25 | PASS |
| Engine routing, overrides, quota | A32 | PASS |
| Standard PR loop, precheck, rounds | A11, A12 | PASS |
| Land policy, merge-ups, trains | A13–A15 | PASS |
| Grants, holds, stops, sensitive, mirror | A15, A16, A19 | PASS; A19 NOT RUN |
| Flavors, express, solo | A11, A17, A18 | PASS |
| Typed evidence, CLI capture | A12, A23 | PASS |
| Bootstrap, doctor, upgrade, uninstall | A20 | PASS |
| Harness and session-backend adapters | A19 | NOT RUN (M25.1, #797) |
| Release cut, bundle, approval | A24 | PASS |
| Researcher Riley | A21 | PASS |
| Triage T1–T7 | A22, A26, A27 | PASS; row 34 FAIL (#1175) |
| Handoff and ownership | A28, A29 | A28 PASS; A29 NOT RUN (M25.1, #213) |
| Hosts, remote call, forge-less runner | A23, A30 | A23 PASS; automatic pick BLOCKED; A30 NOT RUN (M25.1) |
| Observe, metrics, self-improve, notifications | A25, A27, A31 | PASS |

| Contract | Scenarios | Level a |
| --- | --- | --- |
| C1 wake | A04, A26 | A26 PASS; A04 variant PASS |
| C2 one consumer | A04, A07 | A07 PASS; A04 variant PASS |
| C3 acked refs | A06 | PASS; row 36 FAIL on a fresh state root (#1176) |
| C4 terminal status | A03, A05, A21 | PASS |
| C5 external liveness | A05 | PASS (A19 NOT RUN) |
| C6 preserved worktrees | A03, A05, A20 | PASS |
| C7 serial land | A14, A15 | PASS |
| C8 owner SLA | A25 | PASS (real channel: L2) |
| C9 single runtime ownership | A28 | PASS (A29: L2) |

## Open P0/P1

As of 2026-11-07 01:00Z: no open P0. The only open P1 in M25 is #806.
Open P1s with no milestone, all older than M25: #918, #846, #823, #819, #444,
issues #442, #424, #423, #397, #396, #395, #394, #314 and #259. The four new
cards, issues #1174 to #1177, are proposed P2/P3 and await triage.

## Limitations for the owner to accept

Each item names what stays unproved, the residual risk and where it is tracked.
Accepting one changes no merge gate, CI rule or permission.

- **L1. No level b.** No disposable forge repo or accounts were provided, so no
  sandbox run exercised real engines, real reviewer judgement, real CI wiring
  or real head races (register row 45). Compensation: level-a scenarios plus
  the observed production fix loop. Tracked: row 45; reprovision via
  `campaign-sandbox.py plan-forge`.
- **L2. No level c.** Devices, second host, actual sleep, real owner channel,
  campaign-history metric report and full-team handoff are owner-run and moved
  to M25.1 (#804, #209, #716, #213, #157, #158). Their real-device ACs stay
  open there.
- **L3. A19 not run.** Adapter conformance and Grok mirror boundaries wait on
  M15.1 readiness (#797 in M25.1).
- **L4. Automatic runner pick unproved positively.** The check verb works; a
  host pick needs a host runner service outside the sandbox (row 32, #209).
- **L5. Row 34 and row 36 product gaps remain open** as P2 cards #1175 and
  #1176: a milestone-close sweep can wait up to `interval_hours` after a
  queued sweep, and a fresh install's first lead ack fails.
- **L6. Harness drift.** A04's committed fixture fails at `main` until #1174
  lands; the A22 oracle depends on run-id case (#1177). Product behaviour
  passes in the A04 variant.
- **L7. CI-only coverage for #1118 and #1042.** Their fix rows are proven by
  unit tests and recorded proofs, not by a campaign scenario step.
- **L8. Register follow-ups not run:** rows 35 and 37–43 stay proof-quality or
  owner-semantics follow-ups (P2/P3), as listed above.
- **L9. Live adoption of #818** (the crew's own tmux server) is checked on the
  live crew, outside this sandbox run.
