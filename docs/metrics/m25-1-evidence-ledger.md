# M25.1 evidence ledger: #157/#158 AC audit and the #716 case index

**Last updated:** 2026-11-09

Item [#1445](https://github.com/mw-ding/mdstack/issues/1445), from
[Riley's plan](https://github.com/mw-ding/mdstack/issues/1438#issuecomment-6729592128).
An audit of what already exists, not a design: it adds no rule, gate, label
or product code. Repository citations are `path:line` at Base `aa9d26c`;
issue states were read on 2026-11-08. The [#716 case index](#716-case-index)
was refreshed for #716 at `a679007` on 2026-11-09.

## TL;DR

- **#157 AC1, AC2, AC4 and #158 AC1, AC2, AC4: met.** Each design section
  the criteria name exists, with alternatives in its Decisions table, and the
  build issues are filed. Citations in [#157](#157-runtime-handoff) and
  [#158](#158-multi-device).
- **Still open, as #1445 AC3 requires:** #157 AC3 (dry run, for
  [#1441](https://github.com/mw-ding/mdstack/issues/1441)) and #158 AC3
  (two-host run, for [#1442](https://github.com/mw-ding/mdstack/issues/1442)).
- **#716:** cases 1–5 each have a recorded **simulated host** run on the
  M20.1 Docker lab (lab C), linked in the [case index](#716-case-index).
  Physical sleep, power loss and overlay-network loss stay unproven.
- **Four wording contradictions, reported and not fixed here** (no new design):
  see [Contradictions](#contradictions).

## #157 runtime handoff

| AC | Verdict | Evidence |
|---|---|---|
| 1. `docs/handoff.md`: pause/drain, manifest schema, ownership marker, resume and reconcile, return path, alternatives | Met | Ownership record `docs/handoff.md:102`; pause and drain `:174`; manifest `:223` with its template `:268`; resume and reconcile `:318`; prompt stop `:376`; return path `:391`; alternatives in the Decisions table's "Alternatives considered" column `:62` |
| 2. Runtime contract gains the handoff capability, or explain why core | Met | C9 in the contract table `docs/runtimes/README.md:32` and its section `:157`; the core/capability split is argued in `docs/handoff.md:654` and the Decisions row "Core or runtime contract (AC2)" `:62` |
| 3. Manifest template plus a recorded dry run | Open (template half present) | Template `templates/handoff-manifest.md:1`. The dry run is #213, open, for #1441 |
| 4. Follow-up build issues filed (commands, guards per runtime, manifest generator) | Met | `docs/handoff.md:666`: #210 guard (closed), #211 manifest generator (closed), #212 prompt stop and resume (closed), #637 commands (closed), #638 session guard (closed), #639 doctor (closed), #640 quota suggestion (closed), #936–#939 control item (closed), #213 dry run (open). Row E is unfiled, but its content shipped: see [Contradictions](#contradictions) 2 |

## #158 multi-device

| AC | Verdict | Evidence |
|---|---|---|
| 1. Design doc: overlay assumptions, host inventory schema, placement, C1–C8 across hosts, failure/partition, security, alternatives | Met | Overlay N1–N6 `docs/runtimes/multi-device.md:56`; host inventory `:67`; placement `:135`; contract across hosts `:355` (C1–C8, plus C9 at `:371`); failure and partition `:373`; security `:390`; alternatives in the Decisions table `:24` |
| 2. Profile schema extension proposal (on #122) | Met | Host inventory proposal `docs/runtimes/multi-device.md:67`, built by #204 (closed) |
| 3. Two-host dry run, recorded (builder remote, coordinator local) | Open | #209 open; the run is #1442. See [Contradictions](#contradictions) 4 |
| 4. Follow-up build issues filed | Met | `docs/runtimes/multi-device.md:760`: #204, #205, #206, #208, #349, #726–#729 (closed); #207, #209, #345–#348 (open). The forge relay row `:784` is conditional and correctly unfiled |

## #716 case index

Every case below has a recorded run on lab C, the M20.1 Docker lab: a Linux
container on the primary, reached by the hardened `-F none` SSH call over a
loopback-published port. Each run is labelled **simulated host**. The owner
accepted that label as closing evidence for cases 1–5
([#985 c6728250591](https://github.com/mw-ding/mdstack/issues/985#issuecomment-6728250591)).
The runs prove lifecycle and transport only.
**Physical sleep, power loss, overlay-network loss and attached hardware
stay unproven.** Every run also shares these limits:

- it ran on one machine, the owner's Docker Desktop daemon;
- the SSH path was a loopback port, not an overlay;
- an outage was a Docker control (`docker network disconnect`, `pause`,
  container recreate), not a lost link;
- the engine, `gh` and the forge were stubs.

The lab scope is in the multi-device
[lab section](../runtimes/multi-device.md#remote-acceptance-criteria-and-the-local-lab)
and the [lab runner scenarios](../campaign-harness.md#lab-runner-scenarios).
Lab G ([#1361](https://github.com/mw-ding/mdstack/issues/1361),
[PR #1485](https://github.com/mw-ding/mdstack/pull/1485)) writes each run's
evidence record: hosts, image digest, bundle and source hashes, transport,
injected events and the timeline. It labels simulated controls and stubs, and
a skipped scenario supplies no evidence.

| # | Case | Recorded run (simulated host) | What the run shows | Still needs a real device |
|---|---|---|---|---|
| 1 | Forge-less runner: seed, job, result at a head, parity with a local run, no forge contact | Lab F [#1360](https://github.com/mw-ding/mdstack/issues/1360), [PR #1472](https://github.com/mw-ding/mdstack/pull/1472) R1; source and bundle hashes in [PR #1492](https://github.com/mw-ding/mdstack/pull/1492) R1 | `exact-head`, `red`, `idempotent` and `stale` run the bundle's `mdstack runner` over real SSH. The host job is `check-repo ok on linux` with `env: clean` of the client's decoy `GH_TOKEN`, `GITHUB_TOKEN` and `SSH_AUTH_SOCK`. Remote exits `[0, 0]` match the local `[0, 0]` | A second machine with no forge route. The loopback lab gives the host no forge credentials, but it does not isolate its network (`n3: unproved` without `--n3`) |
| 2 | Two-host dry run, linked from #158, follow-ups filed | A30 [#1442](https://github.com/mw-ding/mdstack/issues/1442), [PR #1492](https://github.com/mw-ding/mdstack/pull/1492) R1; linked on #716 ([c6735002310](https://github.com/mw-ding/mdstack/issues/716#issuecomment-6735002310)) | `mdstack spawn` places `ben-1` on `lab-a`; its status lines are mirrored by the watcher's pulls; `mdstack send --wait-ack` returns `acked … by ben-1`. The record has the journey, the local comparison and teardown | A real second device on a private overlay, with a real engine logged in on it |
| 3 | Partition: both alive, `unreachable`, no respawn, reconcile on return | [#347](https://github.com/mw-ding/mdstack/issues/347), [PR #1490](https://github.com/mw-ding/mdstack/pull/1490) R1, with [#346](https://github.com/mw-ding/mdstack/issues/346), [PR #1487](https://github.com/mw-ding/mdstack/pull/1487) R1; journey in PR #1492 R1 | A disconnect mid-run gives one `unreachable` escalate wake, no respawn and the same claim (digest unchanged). On return, reconcile reads `ben-1 alive`, and the mirrored status lines arrive once and in order (#1487: none lost or duplicated) | A real network drop or laptop sleep, the host returning, and no duplicate agent |
| 4 | Remote attach and log tail over the hardened call | [#348](https://github.com/mw-ding/mdstack/issues/348), [PR #1488](https://github.com/mw-ding/mdstack/pull/1488) R1 | Over real SSH to `lab-a`, a pty client attaches read-only and detaches with exit 0, typed keys never reach the pane, `capture` reads the pane and `logs` returns the step summary tail (`- build ok`, `- tests ok`). Attach without a TTY is refused. The run is planted with `docker exec`, since `spawn` needs a forge; the record names it a stub | Attaching to and tailing a job on a real host from the primary |
| 5 | Unreachable runner falls back locally, fallback recorded | Lab F [#1360](https://github.com/mw-ding/mdstack/issues/1360) AC3, [PR #1472](https://github.com/mw-ding/mdstack/pull/1472) R1; recorded by lab G | `disconnect`, `pause` and `recreate` each confirm the host `unreachable`, then print `runner: lab-a … ; ran locally` with green local exits. A lost job is refused after recreate (`refused: unknown job`) | A real host going away, rather than an injected outage |

## Contradictions

Reported for the issues that own them; the ledger picks no wording.

1. **#157 AC3 and the 21.5 row name the old runtimes.** #157 AC3 and
   `docs/handoff.md:677`, `:690` describe a Grok Bot → session → Grok Bot run
   blocked on Grok Bot quota and #140. The owner later changed the environment
   to a second crew-controlled team
   ([#213 c6618452050](https://github.com/mw-ding/mdstack/issues/213#issuecomment-6618452050)).
   Owner: #1441 AC2.
2. **Row E is marked proposed but its content exists.** `docs/handoff.md:7`
   and `:682` list the C9 contract tables as design only, yet C9 rows are in
   `docs/runtimes/multi-device.md:371` and `docs/runtimes/session.md:88`.
   Owner: #1441 AC2, or a docs follow-up.
3. **`docs/runtimes/tmux.md:188` still declares C9 unsupported** while the same
   row describes the guard and `mdstack handoff` tooling from #210–#212 and
   #637 as implemented. Not a #157 AC; for a docs follow-up.
4. **#158 AC3 says "builder remote"; #209 is runner first.** The design's
   #209 boundary (`docs/runtimes/multi-device.md:749`) moves the remote builder
   out of #209, while #1442 AC1 puts a placed remote builder back in. #158 AC3
   closes on #1442's record, so #1442 must show the remote builder, not only a
   runner job.
