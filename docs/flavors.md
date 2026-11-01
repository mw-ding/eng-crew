# Crew flavors (design)

Named, per-project rigor presets in the profile, a floor that no flavor
crosses, and a metrics feedback loop that suggests when a project's flavor
should change (roadmap 18.1,
[#156](https://github.com/mw-ding/eng-crew/issues/156); umbrella
[#110](https://github.com/mw-ding/eng-crew/issues/110)). Owner decisions:
[#160 row 15](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6532247500)
(rigor presets), [row 8](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6531125583)
(pre-review check) and
[row 9](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6531795606)
(`crew:sensitive`). This page reflects them; it does not re-decide them.

This page adds no rule, gate, cap, marker field or label yet. It proposes
them, and each one lands through the [build issues](#build-issues). A change
to what satisfies a gate lands under the
[gate contract](protocol.md#gate-contract), with the owner's merge-ok. Until
then the [protocol](protocol.md) applies as written.

## Decisions

| Question | Choice | Alternatives considered |
|---|---|---|
| Unit | A named flavor per project, built from [knobs](#knobs). Presets are `thorough`, `standard`, `fast` and `solo`; a custom flavor sets knobs on top of a preset | One rigor level for every project: the problem this solves. A project mode plus an autonomy flag (firstmate): two switches cannot set review, validation, evidence and caps separately |
| Core or binding (#156 Q1) | Rigor knobs are core: each picks how a §3, §5 or §7 rule is met. `lighter_lane`, `parallelism` and `builder` are runtime knobs. `merge` also needs the backend to record a standing grant on the tracker ([single identity](interfaces.md#single-identity-profile)) | All core: the lighter lane exists only because of Grok Bot's per-PR watch limits. All binding: the same project would get different rigor on different runtimes |
| When rigor is decided | The project flavor at install or intake: bootstrap proposes it, the owner confirms, the profile records it ([#191](https://github.com/mw-ding/eng-crew/issues/191), 17.3). The item flavor at triage, recorded on the item | Each role decides on wake: roles guess and disagree. Profile only: no way to lower one item |
| Lowering | An item flavor below its default needs a `Reason:` line in its record. A record that lowers without one is refused, and the default applies | Free lowering: rigor erodes silently. Owner-only lowering: routine items stall, though class rules already cover most of them |
| No setting | No project flavor means `thorough`. `resolve`, `crew doctor` ([#190](https://github.com/mw-ding/eng-crew/issues/190)) and one note on the tracking issue flag the gap. An item with no record is `thorough`, and roles tell the coordinator | The project flavor for an unrecorded item: it rewards skipping triage |
| Granularity (#156 Q2) | The project flavor plus a deterministic path-based [class rule](#class-rule). An owner override is an item record with the owner's words as its reason. Uncertain means stricter | Per project only: docs and scripts get the same rigor. Class labels applied by hand: judgment at merge time, but the synthesizer only reads |
| Combining flavors | Knob-wise strictest: for each rigor knob, the stricter value wins | A total order of presets: custom flavors have no place in it, and a mixed change would lose a strict value |
| Record (#156 Q3) | Item: a coordinator-signed post on the item with a `pass=flavor` marker. Project: the profile diff, by PR, or, for an untracked profile, posted on the tracking issue before it applies | A `flavor:<name>` label: unsigned, carries no reason, and a label change records neither who nor why. Chat: not the tool of record (invariant I5) |
| Default for new projects (#156 Q5) | Bootstrap proposes `standard`; the owner confirms or edits it. An unset flavor stays `thorough` | Proposing `thorough`: safe but heavy for most new projects; unset is `thorough` anyway |
| Feedback loop | Metrics and owner feedback produce a [suggestion issue](#suggestion-issue). It is never auto-applied; the owner accepts or declines | Auto-apply: changes authority without the owner (out of scope in #156). Folding it into the [metrics gate](metrics/decisions.md): that gate is harness-wide and pauses work, while a flavor is per project and changes nothing until accepted |
| Cost levers | Tier and flavor config only (`engines`, `parallelism`, `caps`), never a router model that picks routes (#160 row 7; [#109](https://github.com/mw-ding/eng-crew/issues/109) guardrail) | Routing by quota headroom: deferred by #160 row 7 |
| Upgrade | `thorough` turns on the pre-review check, so the first release with flavors changes unset projects. That entry is `**Breaking:**` ([versioning](deliverables.md#versioning)); its migration step is an explicit `[builder.precheck].enabled = false` | `thorough` exactly as today: then the strictest preset has fewer checks than `standard` |

## Knobs

Values are listed strictest first. "Today" is the protocol as written.

| Knob | Key | Values | Binding | Today |
|---|---|---|---|---|
| Review depth | `review` | `full`: findings ranked per [§3](protocol.md#3-evidence-requirements). `thin`: red only for an AC, a §7 gate, CI or security (the [AGENTS.md](../AGENTS.md) posture). `light`: one light pass | core | `full` |
| Validation | `validation` | `always` · `behaviour` (behaviour-changing changes only) · `off` | core ([stage 6](protocol.md#2-stages), §7 approval) | `always` |
| Engine diversity | `diversity` | `required`: every waive needs the owner's per-change OK. `waivable`: the [quota diversity waive](roles.md#quota-diversity-waive) with its standing grant | core (I2) | `waivable` |
| Round cap / CI-fix cap | `caps` | `[3, 3]` · `[2, 2]` · `[1, 1]`; each entry 1–3 | core ([§5](protocol.md#5-rounds-and-escalation)) | `[3, 3]` |
| Evidence | `evidence` | `typed`: per shape, committed ([verification](verification.md)). `inline`: excerpts in the change body only ([#143](https://github.com/mw-ding/eng-crew/issues/143)) | core (§3, §7 required evidence) | `typed` |
| Merge permission | `merge` | `per-change` · `docs`: today's standing doc-only merge-ok · `auto`: any change once every §7 gate passes | core (§7 merge permission); backend: the grant is recorded on the tracker | `docs` |
| Pre-review check | `precheck` | `on` · `off`. Sets the default of `[builder.precheck].enabled` ([#181](https://github.com/mw-ding/eng-crew/issues/181), 16.2) | core (16.1–16.3) | not built |
| Lighter lane | `lighter_lane` | `off` · `docs` · `docs+tests` | runtime ([Grok Bot](runtimes/grok-bot.md#lighter-lane-routing)) | `docs` |
| Parallelism | `parallelism` | `{ builders = <n>, reviewers = <n> }`, 1 ≤ n ≤ the runtime cap | runtime | 5 / 5 ([roles](roles.md#parallelism)); tmux 5 / 2 |
| Engine routing | `engines` | Per-tier `order` and `effort` overrides, in the shape of `[engines]` ([profile](profile.md#keys)) | core ([tiers](roles.md#tiers)) | `[engines]` |
| Builder | `builder` | `crew` · `solo`: one owner-driven session builds and fixes ([#102](https://github.com/mw-ding/eng-crew/issues/102)) | runtime | `crew` |

- **Rigor knobs** are the first eight. Only they combine knob-wise and count
  as lowering. `parallelism` and `engines` are resource knobs and come from
  the project flavor; `builder` comes from the item record.
- `merge` gives permission only. It never supplies the approval, never skips
  CI, and never covers a `crew:sensitive` ([F7](#floor)) or `crew:spec`
  change.
- Under `validation = behaviour` or `off`, the verdict's validation section
  says `skipped (flavor <name>)`. How §7 reads that is follow-up
  [A](#build-issues).

## Presets

| Knob | `thorough` | `standard` | `fast` | `solo` |
|---|---|---|---|---|
| Use for | Product code, security, releases: every check on | Most work: thin review, validation for behaviour changes | Docs, prototypes, spikes | One owner-driven session builds |
| `review` | `full` | `thin` | `thin` | `thin` |
| `validation` | `always` | `behaviour` | `off` | `behaviour` |
| `diversity` | `waivable` | `waivable` | `waivable` | `waivable` |
| `caps` | `[3, 3]` | `[3, 3]` | `[2, 2]` | `[3, 3]` |
| `evidence` | `typed` | `typed` | `inline` | `typed` |
| `merge` | `docs` | `docs` | `auto` | `docs` |
| `precheck` | `on` | `on` | `off` | `on` |
| `lighter_lane` | `docs` | `docs` | `docs+tests` | `docs` |
| `parallelism`, `engines` | project values | project values | project values | project values |
| `builder` | `crew` | `crew` | `crew` | `solo` |

`thorough` differs from today only in `precheck = on`, once M16 lands.
`solo` keeps the independent reviewer on an engine different from the
session's, the synthesizer and the floor (#102 scope update).

## Floor

No flavor, preset, class rule or item record may cross these. The
[#195](https://github.com/mw-ding/eng-crew/issues/195) validator rejects a
flavor that tries, with a message naming the item.

| # | Floor item | No flavor may | Enforced by | Source |
|---|---|---|---|---|
| F1 | CI never waived | Land with a required check red, pending or skipped | No knob touches CI; the CI-fix cap is at least 1 | [Gate contract](protocol.md#gate-contract) |
| F2 | No secrets | Carry a token-shaped value | The profile secret scan covers the flavor tables | Spec R1 |
| F3 | Only the synthesizer lands | Let another role or session land | No knob names a landing role; `builder = solo` never lands | I4 |
| F4 | Audit trail on the tool of record | Skip the flavor record, the verdict post, a waive record or the `merge` marker | No such value exists; `review` has no `off` | I5 |
| F5 | The owner can always hold | Stop `crew:escalated` or a coordinator hold-until from stopping every role | No flavor knob touches holds | [§5](protocol.md#5-rounds-and-escalation), [§9](protocol.md#9-steering-crew-commands) |
| F6 | Gate-contract changes need the owner | Change what satisfies a gate, or change a project's flavor without the owner | Knob values pick only gate modes the protocol defines; a flavor change lands by the owner's per-change merge-ok | [Gate contract](protocol.md#gate-contract) |
| F7 | `crew:sensitive` needs a per-change merge-ok | Let `merge` cover a `crew:sensitive` change | `merge` does not apply to it | #160 rows 9, 15; [#184](https://github.com/mw-ding/eng-crew/issues/184) |

The rest of [portable spec §3](specs/portable.md#3-invariants) binds every
flavor too, as part of a profile: I1 (author ≠ reviewer, or the
single-identity rule), I2 (so `diversity` has no `off`) and I3 (evidence on
the change head). So do the protocol's hard rules: caps of at most 3, a
serial land, and a per-change merge-ok for `crew:spec` changes. In eng-crew
itself, the gate-defining paths (`docs/protocol.md`, `docs/runtimes/*.md`,
`docs/verification.md`, `docs/flavors.md`, `scripts/crew-config.py`) become
`crew:sensitive` path rules in its own profile (a scope note for #184). That
way F6 holds at merge time through F7.

## Profile schema

Proposed for [#195](https://github.com/mw-ding/eng-crew/issues/195) (18.2)
and [#197](https://github.com/mw-ding/eng-crew/issues/197) (18.4), on top of
the [profile](profile.md) (#122) and its [layers](profile.md#layers-and-precedence) (#123).

```toml
[flavor]
name = "standard"      # a preset or a flavor.custom name; unset: thorough, flagged
goal = "quality"       # quality | speed | cost; read only by the feedback loop

[flavor.custom.docs-site]
base = "fast"          # a preset; no chains
merge = "docs"

[[flavor.classes]]
paths = ["docs/**", "*.md"]
flavor = "fast"
reason = "docs only; markdownlint and the link check run in CI"

[[flavor.classes]]
paths = ["src/auth/**", "migrations/**"]
flavor = "thorough"
```

| Key | Type | Default |
|---|---|---|
| `flavor.name` | string: a preset or a `flavor.custom` name | none: `thorough`, flagged |
| `flavor.goal` | string: `quality`, `speed` or `cost` | `quality` |
| `flavor.custom.<name>.base` | string: a preset | *required* |
| `flavor.custom.<name>.<knob>` | per [Knobs](#knobs) | the base's value |
| `flavor.classes[].paths` | list of globs, non-empty | *required* |
| `flavor.classes[].flavor` | string: a preset or a `flavor.custom` name | *required* |
| `flavor.classes[].reason` | string | none; *required* when the class is below `flavor.name` on any rigor knob |

Validator rules, each with a test:

1. Closed tables and enums per [Knobs](#knobs): an unknown key or value
   fails.
2. Names resolve. A custom name never shadows a preset, and `base` is a
   preset.
3. Each `caps` entry is 1–3; each `parallelism` entry is at least 1 and at
   most the runtime cap; `engines` follows the `[engines]` rules and the
   [hard rules](roles.md#hard-rules).
4. A class below `flavor.name` without a `reason` fails.
5. A key or value that would cross F1–F7 fails as `floor F<k>: <item>`, even
   when it is also an unknown key, so the message names the floor.

Layers: `flavor` and `flavor.custom.*` merge by key; a higher layer replaces
`flavor.classes` whole. `resolve` prints the gap as
`flavor.name = "thorough"  # core (unset: flagged)`.

## Resolution

| Level | When | Who | Result |
|---|---|---|---|
| Project | Install or intake (17.3) | The owner confirms the bootstrap proposal | `flavor` in the profile; unset means `thorough`, flagged |
| Item | Triage window ([§6](protocol.md#6-duties-on-wake-all-roles)) | Coordinator | The item record below. Its default is the class flavor of the paths the item names, or the project flavor when it names none |
| Change | Every builder, reviewer and synthesizer wake, at head | Each role, by program, not by judgment | Knob-wise strictest of the item flavor and the class flavor of the change's paths at head (`change.read-diff-paths`); F7 then applies |

Item record (18.3), posted on the item:

```text
[<CoordinatorBot>/flavor] #<n>: <flavor> (default <default>)
Reason: <one line; required when <flavor> is below <default> on any rigor knob>
<!-- crew:v1 role=coordinator pass=flavor issue=<n> flavor=<flavor> default=<default> -->
```

- The newest record wins. Roles re-read it on every wake (§6 step 1), so a
  later record that tightens applies at once.
- A record that lowers without a `Reason:` is refused: roles use the
  default and tell the coordinator. The `Reason:` line is read with the
  marker, the record's only parsed line besides it.
- No record: `thorough`, and roles tell the coordinator (`flavor-missing`).
- The owner may set any item flavor; the coordinator records the owner's
  words as the reason. Builders and reviewers never lower a flavor; they ask
  the coordinator.

### Class rule

- Globs use the dialect of `scripts/deliverables.txt`: `**` crosses `/`,
  while `*` and `?` stay inside one path segment.
- A path that matches several classes gets the strictest of them. A path
  that matches none gets the project flavor. A change's class flavor is the
  strictest over all its paths.
- A change that touches paths beyond its item's class is raised, never
  lowered, because the change flavor is the strictest of the item and its
  paths.
- `crew:sensitive` path rules (#184) are separate. They only add F7.

## Existing knobs

| Existing knob | Where today | Becomes | Note |
|---|---|---|---|
| Lighter lane | [§6](protocol.md#6-duties-on-wake-all-roles), Grok Bot binding | `lighter_lane` | Code, `.github/`, `templates/**` and `docs/protocol.md` never qualify; `docs+tests` adds test-only paths. The mirror hold stays path-derived |
| Standing doc-only merge-ok (2026-10-25) | §6, §7 | `merge = "docs"` | The owner's grant stays the record that the value cites |
| tmux `merge_grant` | `runtime.options` ([profile](profile.md#keys)) | `merge` | #195 replaces it, or checks that both agree, so there is one source |
| Thin review posture | eng-crew [AGENTS.md](../AGENTS.md) | `review = "thin"` in eng-crew's own profile | Product repos keep their own `AGENTS.md` for repo specifics |
| Quota diversity waive | [roles](roles.md#quota-diversity-waive) | `diversity` | Its trigger, preference, record and per-PR owner OK for HIGH risk stay in roles; `required` removes the coordinator's standing grant |
| Tiers | [roles](roles.md#tiers) | Stay separate | A tier measures difficulty, not rigor. `engines` may override a tier's order or effort; security and release infra work stays deep |
| Round cap, CI-fix cap | Protocol hard rules, [§5](protocol.md#5-rounds-and-escalation) | `caps` | 3 stays the maximum |
| Parallelism ceilings | [roles](roles.md#parallelism); tmux `builders`, `reviewers` | `parallelism` | Land stays serial (C7). `/crew away --cap` ([#199](https://github.com/mw-ding/eng-crew/issues/199)) lowers it while away; the lower value applies |
| Pre-review switch | `[builder.precheck]` (16.2) | `precheck` sets its default | Commands stay in `[builder.precheck]`; an explicit `enabled` wins |
| tmux `hold_label_blocks` | `runtime.options` | Stays separate | A lane-label switch for #110 roadmap PRs; F5 holds through `crew:escalated` and a coordinator hold-until |
| Owner-SLA auto-apply defaults | §6 | Stay separate | Owner-absence handling, not rigor; away mode ([#198](https://github.com/mw-ding/eng-crew/issues/198)) changes no authority |
| Metrics gate | [metrics decisions](metrics/decisions.md) | Stays separate | A harness-wide pause; it blocks relax suggestions while open |

## Feedback loop

### Inputs

| Input | Source on the tool of record | Status |
|---|---|---|
| Cycle time | `open_to_merge_min` | In `prs.csv` ([metrics](metrics/README.md)) |
| Rounds | `changes_verdicts`, `builder_fix_rounds`, `ci_fix_rounds` | In `prs.csv` |
| Rework | `reopened`, or changes verdicts at the cap (the [rework proxy](metrics/decisions.md#rework-proxy-and-its-limits)) | In `prs.csv` |
| Flavor per change | An optional `flavor=<effective>` field on the `pass=verdict` marker | New (follow-up A) |
| Escaped defects | A bug item or intake card with `Escaped from: <owner>/<repo>#<pr>`, which the coordinator adds at triage | New (follow-up C) |
| Quota spend | Engine runs per change: distinct `Engine:` trailers per round, plus the reviewer and validator runs named in verdict signatures. Token and quota-% figures stay local to the runtime, off the record, so they are not inputs | New (follow-up C) |
| Owner feedback | An [intake card](self-improve.md#triggers) with trigger `owner-feedback` and class `too-slow`, `too-costly` or `missed-bug` | New trigger (follow-up D) |

### Thresholds

Initial drafts, tunable like the [metrics gate](metrics/decisions.md#tuning).
Computed per project over changes merged under its current flavor; a change
raised by a class rule counts for that class instead.

| # | Signal | Window | Suggests |
|---|---|---|---|
| T1 | At least 2 escaped defects | Last 30 days | Tighten one step |
| T2 | One `missed-bug` owner card | None | Tighten one step |
| T3 | Rework rate above 20% | Last 20 merged changes, at least 5 | Tighten one step |
| R1 | 20 merged changes with no changes verdict and no escaped defect | Last 20 merged changes | Relax one step |
| R2 | A `too-slow` or `too-costly` owner card, with no escaped defect | Last 30 days | Relax one step |
| R3 | Goal `speed`: median cycle time more than 30% above the project's baseline. Goal `cost`: engine runs per change more than 30% above it. No escaped defect in 30 days | 14 + 14 days, as in the [sensors](metrics/decisions.md#sensors) | Relax one step |

- Any T signal blocks every R signal.
- No relax while a `metrics-gate` issue is open, or within 28 days of the
  last flavor change. A tighten can fire at any time.
- One step means `thorough` ↔ `standard` ↔ `fast` for a preset, and one
  value step on the knobs behind the signal for a custom flavor. `solo`
  steps like `standard` and keeps `builder = solo`.
- `goal` only enables R3; a `quality` project relaxes on R1 and R2 only.
- A suggestion never crosses the floor, and never touches F7 or `crew:spec`.

### Suggestion issue

Title `flavor: <tighten|relax> <owner>/<repo> <from> → <to> (<as-of>)`, with
the plain label `flavor-suggestion` (not a `crew:*` state tag). It is filed in
the control-plane repo, like the metrics gate. At most one is open per
project and scope; a later signal comments on it.

```markdown
## Signal

<T1–T3 or R1–R3> as of <date> (UTC). Scope: project | class `<paths>`. Goal: <goal>.

## Evidence

| Change | Flavor | Changes verdicts | Escaped defects | Cycle time (min) | Engine runs |
|---|---|---|---|---|---|
| <owner>/<repo>#<n> | <flavor> | <k> | <link or 0> | <m> | <r> |

## Proposed change

<from> → <to>. Knobs: <knob> <old> → <new>, ...

~~~toml
[flavor]
name = "<to>"
~~~

Validator: `crew-config.py validate` → <output>.

## Decision

Owner: `accept flavor: <to>` or `decline flavor: <reason>`.
Default if unanswered: keep <from>. A flavor change is never applied by default.
```

### Owner accept path

1. The coordinator files the suggestion, or comments on the open one.
2. The owner answers on the issue, or in chat, which the coordinator records
   verbatim on the issue. The [§6](protocol.md#6-duties-on-wake-all-roles)
   owner SLA applies, and its default is always to keep the current flavor.
   Away words may accept a tighten, never a relax: away mode never changes
   authority (#160 row 19).
3. On accept, the coordinator makes the profile change. For a tracked
   profile it opens a PR with the validator output inline; the PR needs the
   owner's per-change merge-ok, and no standing grant covers it (F6). For an
   untracked profile, the coordinator posts the diff on the issue and applies
   it after the owner's words.
4. Once applied, the coordinator closes the issue with the link. The new
   flavor applies to items triaged after it; after a tighten, the coordinator
   re-records open items that have not merged.
5. On decline, the issue closes as not planned, with the reason. The same
   signal is not filed again within 28 days unless the numbers get worse.

## Build issues

| ID | Issue | Builds | Depends on |
|---|---|---|---|
| 18.2 | [#195](https://github.com/mw-ding/eng-crew/issues/195) | [Profile schema](#profile-schema): presets, custom flavors, validator with a test per floor item, the `resolve` gap line | 18.1, 16.2, 16.5 |
| 18.3 | [#196](https://github.com/mw-ding/eng-crew/issues/196) | Project flavor at intake; item record, default, lowering and refusal; coordinator contract and triage template | 18.2, 17.3 |
| 18.4 | [#197](https://github.com/mw-ding/eng-crew/issues/197) | [Class rule](#class-rule) matcher, knob-wise strictest, change flavor at head | 18.2 |
| 18.5 | [#198](https://github.com/mw-ding/eng-crew/issues/198) | `/crew away`; it changes no flavor and accepts no relax | 16.7 |
| 18.6 | [#199](https://github.com/mw-ding/eng-crew/issues/199) | `/crew away --cap` lowers `parallelism` while away; `--quiet` | 18.5 |
| 18.7 | [#102](https://github.com/mw-ding/eng-crew/issues/102) | The `solo` preset: the `builder = solo` runtime path | 18.2 |
| 18.8 | [#109](https://github.com/mw-ding/eng-crew/issues/109) | The `cost` goal and its levers; its own ACs stay in #109 | 18.2 |

Proposed follow-ups, for the coordinator to file:

| ID | Builds | Depends on |
|---|---|---|
| A | Knobs in the protocol: §3, §5, §7 and gate-registry wording for `review`, `validation`, `evidence`, `caps` and `merge`; the optional `flavor=` verdict marker field; builder, reviewer and synthesizer templates read the change flavor. Gate contract, `crew:needs-mirror`, owner merge-ok; likely two PRs | 18.2, 18.4 |
| B | Renderer: the project flavor's values in the rendered briefs | A |
| C | Metrics: `flavor`, `escaped_defects` and `engine_runs` columns in `metrics-refresh.py`; the `Escaped from:` triage line | A |
| D | The `owner-feedback` intake trigger and its three classes | none |
| E | `flavor-suggest`: T1–T3, R1–R3 and the guards on the CSV, with offline tests; the suggestion issue template; the coordinator's triage duty | C, D |
