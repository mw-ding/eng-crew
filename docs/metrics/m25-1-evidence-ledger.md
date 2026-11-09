# M25.1 evidence ledger: #157/#158 AC audit and the #716 case index

**Last updated:** 2026-11-09

Item [#1445](https://github.com/mw-ding/mdstack/issues/1445), from
[Riley's plan](https://github.com/mw-ding/mdstack/issues/1438#issuecomment-6729592128).
An audit of what already exists, not a design: it adds no rule, gate, label
or product code. Repository citations are `path:line` at Base `aa9d26c`;
issue states were read on 2026-11-08.

## TL;DR

- **#157 AC1, AC2, AC4 and #158 AC1, AC2, AC4: met.** Each design section
  the criteria name exists, with alternatives in its Decisions table, and the
  build issues are filed. Citations in [#157](#157-runtime-handoff) and
  [#158](#158-multi-device).
- **#158 AC3: met on a simulated host** (2026-11-09, [#158 AC3](#158-ac3-record)):
  #1442's A30 run in
  [PR #1492](https://github.com/mw-ding/mdstack/pull/1492), under the owner's
  simulated-host acceptance. Real-device proof stays with #716.
- **Still open, as #1445 AC3 requires:** #157 AC3 (dry run, for
  [#1441](https://github.com/mw-ding/mdstack/issues/1441)).
- **#716:** none of cases 1–5 is closed yet; each row below names the run that
  will close it. All five may close on a run labelled "simulated host"
  ([#985 c6728250591](https://github.com/mw-ding/mdstack/issues/985#issuecomment-6728250591)).
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
| 3. Two-host dry run, recorded (builder remote, coordinator local) | Met, simulated host | #1442's A30 run R1 in [PR #1492](https://github.com/mw-ding/mdstack/pull/1492) (merged `a679007`), linked on [#158](https://github.com/mw-ding/mdstack/issues/158#issuecomment-6735001992). See [#158 AC3 record](#158-ac3-record) |
| 4. Follow-up build issues filed | Met | `docs/runtimes/multi-device.md:760`: #204, #205, #206, #208, #349, #726–#729 (closed); #207, #209, #345–#348 (open). The forge relay row `:784` is conditional and correctly unfiled |

### #158 AC3 record

The run is labelled "simulated host" and closes AC3 under the owner's
acceptance
([#985 c6728250591](https://github.com/mw-ding/mdstack/issues/985#issuecomment-6728250591));
it adds no new Docker run. All facts are from PR #1492's Acceptance
Evidence, proof R1 (`scripts/evidence-cli.py` at source
`d40e460e0dd1b691fcbdc2562917d1a702c8e697`, lab run `laba30`,
2026-11-09T07:49Z to 07:50Z).

- **Builder remote:** `mdstack spawn` placed `ben-1` on lab host `lab-a`
  (placement `capability`, `remote: True`) over the hardened `-F none` SSH call.
- **Coordinator local:** the primary's watcher pulled `ben-1`'s status lines
  into its mirror, and `mdstack send --wait-ack` to `ben-1` returned
  `acked 20261109T074919Z-861cd5 by ben-1` through that mirror.
- **Failure and recovery:** behind `docker network disconnect`, one
  `unreachable` escalate wake, no respawn; reconcile on return found
  `ben-1 alive`, 94 mirror lines once and in order. An owner abandon wrote a
  tombstone; on return the run stopped and kept its unlanded file.
- **Hashes and comparison:** bundle `85ceb8d4…f98b` is the same on host and
  client; remote exits `[0, 0]` match local `[0, 0]`.
- **Teardown:** 2 removed, sentinel unchanged, 0 lab containers left.

Physical limits, as stated in the record:

- one machine: the host is a Linux container on the primary, with no
  independent power, sleep or hardware;
- the SSH path is a loopback-published Docker port, not a private overlay;
- a disconnect is a Docker network control, not a real link loss between
  devices;
- the placed builder's engine and the host's `gh` are stubs: no engine login,
  quota or model runs on the host;
- the forge is the sandbox's fake: the host never reaches a real forge.

Real-device proof of these limits stays with #716 (owner-run).

## #716 case index

Each case stays open until its run is recorded and linked here or on #716.
A run on the Docker lab is labelled "simulated host" and proves lifecycle
and transport only: **physical sleep, power loss, overlay-network loss and
attached hardware stay unproven** (owner acceptance,
[#985 c6728250591](https://github.com/mw-ding/mdstack/issues/985#issuecomment-6728250591);
lab scope `docs/runtimes/multi-device.md:691`).

| # | Case | Closing run | Waits on | Stated physical limit |
|---|---|---|---|---|
| 1 | Forge-less runner: seed, job, result at a head, parity with a local run, no forge contact | Lab F [#1360](https://github.com/mw-ding/mdstack/issues/1360) scenarios, recorded by lab G [#1361](https://github.com/mw-ding/mdstack/issues/1361) | #1357 (lab C, open), then #1360, #1361 | Container on the primary, loopback-published SSH; no real overlay or second machine |
| 2 | Two-host dry run, linked from #158, follow-ups filed | [#1442](https://github.com/mw-ding/mdstack/issues/1442) (#209's A30 journey) | #207, #345, #346, #347, #1361 (all open) | Simulated second host; no physical power or overlay loss |
| 3 | Partition: both alive, `unreachable`, no respawn, reconcile on return | [#347](https://github.com/mw-ding/mdstack/issues/347) with [#346](https://github.com/mw-ding/mdstack/issues/346), recorded in #1442 AC2 | #345, #346, #347, #1360 | Container network disconnect stands in for a real drop (`docs/runtimes/multi-device.md:743`); laptop sleep is not proven |
| 4 | Remote attach and log tail over the hardened call | [#348](https://github.com/mw-ding/mdstack/issues/348) on lab hosts | #345, #348, lab F/G | Container pane, not a real host; runner-job logs alone do not count (`:744`) |
| 5 | Unreachable runner falls back locally, fallback recorded | Lab F #1360 (fallback scenario, its AC3), recorded by #1361 | #1357, #1360, #1361 | Injected unavailability (disconnect or pause), not a real host going away |

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
   runner job. **Met by the record (2026-11-09):** R1 shows `ben-1` placed by
   `mdstack spawn` and acking a message, not only a runner job
   ([#158 AC3 record](#158-ac3-record)). The `multi-device.md:749` wording is unchanged here.
