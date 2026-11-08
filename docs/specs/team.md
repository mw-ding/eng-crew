# Spec: team and modular design

> - **Status:** partly built
> - **Applies to:** this repo's layout, axes, roles, actions and modules
> - **Current rules:** the [protocol](../protocol.md) and its gate registry; each requirement's **Delivered by** issues
> - **Built:** M29–M33 (roles, connectors, environments, harnesses, core, cli and dev modules; the dependency lint; the actions CLI in part; the `mdstack` rename)
> - **Design only:** the `protocols/` and `install/` modules ([§4](#4-target-module-layout)) and the rest of the actions implementation
> - **Last checked:** 2026-11-07 at `02ca805`

Status: v0.1 (2026-11-07). Owner: coordinator. Changes land through
`crew:spec` PRs (review pass only, merge on the owner's merge-ok). Tracking:
[#1180](https://github.com/mw-ding/eng-crew/issues/1180). Issue:
[#1216](https://github.com/mw-ding/eng-crew/issues/1216).

## 1. Goal

Turn mdstack from one engineering crew into a **team of portable
employees**: roles that keep their identity and procedures wherever they are
deployed, built from four independent axes, coordinated through generic
actions, and laid out as modules with enforced dependency rules. This repo
uses its own protocol, so this spec is the source of truth for its shape
([REQ-24](#req-24-self-hosted-specs)).

The requirements come from the owner's design discussion of 2026-11-07,
recorded on #1180:
[decoupling plan](https://github.com/mw-ding/eng-crew/issues/1180#issuecomment-6702507670),
[session backends per host](https://github.com/mw-ding/eng-crew/issues/1180#issuecomment-6703445339),
[modular structure](https://github.com/mw-ding/eng-crew/issues/1180#issuecomment-6703508949),
[self-hosted specs](https://github.com/mw-ding/eng-crew/issues/1180#issuecomment-6703556457)
and the [roadmap](https://github.com/mw-ding/eng-crew/issues/1180#issuecomment-6703873341).

This spec builds on [portable.md](portable.md) and does not restate it.
[§6](#6-relation-to-portablemd) maps its P1–P8 onto the requirements here.
This spec changes no live gate or marker rule; the protocol and its gate
registry stay authoritative until a later change edits them.

## 2. Requirement format

Each requirement has a stable ID, `REQ-01` to `REQ-24`. An ID is never
reused or renumbered; a dropped requirement keeps its ID and is marked
dropped. Each one has five fields:

- **Applies when:** the situation or artifact the requirement governs.
- **Obligation:** what must hold, in MUST / MUST NOT terms.
- **Acceptance criteria:** numbered, checkable statements.
- **Verification:** the proof a change claiming the requirement needs:
  a lint, a test, a review check or a recorded owner decision.
- **Delivered by:** the roadmap issue(s) that implement it. Until those
  land, the requirement is a target, not a description of today.

The key words MUST, MUST NOT and MAY are used as in RFC 2119.

## 3. Requirements

### Roles as portable employees

#### REQ-01. Runtime-neutral role package

- **Applies when:** a role is defined or changed.
- **Obligation:** a role MUST be defined as a runtime-neutral package that
  says who the employee is, what it owns, its procedures, refusals and
  handoffs. The same package MUST work unchanged in every supported
  environment and harness, so the role keeps its identity wherever it runs.
- **Acceptance criteria:**
  1. Every role has one package directory under `roles/` ([§4](#4-target-module-layout)).
  2. Deploying a role in a different environment or harness changes no file
     in its package.
- **Verification:** the runtime-word lint of REQ-11; a render test that
  renders one role package into two environments.
- **Delivered by:** #1184, #1221, #1222.

#### REQ-02. One canonical definition per role

- **Applies when:** role policy is written or edited.
- **Obligation:** each piece of role policy MUST be authored once, in the
  role's canonical files. Runtime-specific operating text MUST live in an
  environment fragment, never in a copy of the role policy.
- **Acceptance criteria:**
  1. No role policy paragraph appears in more than one runtime template.
  2. Changing a role rule edits one file plus, at most, its tests.
- **Verification:** a duplication check over rendered briefs; reviewer
  check that a role-policy diff touches only canonical files.
- **Delivered by:** #1184, #1221.

#### REQ-03. Role metadata as data

- **Applies when:** a role's identity defaults, authority, lifecycle or
  skill index is declared.
- **Obligation:** these MUST be declared as data in the role's `role.toml`,
  not encoded in shared orchestration code. Review, validation and land
  stay explicit core contracts and MUST NOT become role-configurable.
- **Acceptance criteria:**
  1. Each role package has a `role.toml` with identity defaults, authority,
     lifecycle and skill index.
  2. Orchestration code reads lifecycle from the registry and has no
     per-role branches for it.
- **Verification:** registry schema validation in `check-repo`; a test that
  a registered role with an existing lifecycle spawns with no code edit.
- **Delivered by:** #1185.

#### REQ-04. Agent Skills format

- **Applies when:** a role skill is written.
- **Obligation:** role skills MUST use the Agent Skills format: one entry
  `SKILL.md` per role and one `skills/<skill>/SKILL.md` per procedure.
  A harness-specific delta MAY live under `variants/<harness>/` only where
  the harness needs it.
- **Acceptance criteria:**
  1. Every skill file has the format's front matter (name, description).
  2. Each `variants/<harness>/` file states why the shared skill cannot
     serve that harness.
- **Verification:** a format lint over `roles/**/SKILL.md`.
- **Delivered by:** #1184, #1221.

#### REQ-05. Adding a role is cheap

- **Applies when:** a new role is added whose lifecycle already exists.
- **Obligation:** adding it MUST take one role package plus its tests, with
  no edits to environments, harnesses or connectors.
- **Acceptance criteria:**
  1. A conformance test adds a fixture role and runs it in the terminal
     environment with no change outside `roles/` and tests.
- **Verification:** that conformance test in CI.
- **Delivered by:** #1185, #1224.

### Four axes

#### REQ-06. Four independent axes

- **Applies when:** a deployment is configured or a module is added.
- **Obligation:** a deployment MUST be the product of four independent
  axes: **roles** (who), **connectors** (the tools of record),
  **environments** (where and how the team runs) and **harnesses** (how an
  agent launches and loads). Changing the choice on one axis MUST NOT
  require editing a module on another.
- **Acceptance criteria:**
  1. The profile selects one value or set per axis.
  2. Swapping one harness or session backend in a profile changes no file
     under `roles/`, `connectors/` or another axis's module.
- **Verification:** the dependency lint of [§5](#5-dependency-rules); a
  profile matrix test.
- **Delivered by:** #1217, #1222, #1224.

#### REQ-07. Connectors

- **Applies when:** the team reads or writes a tool of record.
- **Obligation:** each tool concern MUST be reached through a connector
  that implements that concern's interface. Connectors are separate from
  environments: an environment never talks to a tool of record except
  through a connector.
- **Acceptance criteria:**
  1. GitHub access lives only in `connectors/github/`.
  2. The `knowledge` concern ([REQ-17](#req-17-knowledge-in-external-services))
     is a connector concern like the others.
- **Verification:** dependency lint rule D6 ([§5](#5-dependency-rules)).
- **Delivered by:** #1217, #1223.

#### REQ-08. Environments

- **Applies when:** a team is run somewhere: a terminal, a hosted bot
  platform, a single session.
- **Obligation:** an environment MUST implement the generic actions
  ([REQ-12](#req-12-actions-contract)) with its own tools and MUST run the
  team machinery (wake, spawn, teardown, delivery, liveness). Roles MUST NOT
  depend on which environment runs them.
- **Acceptance criteria:**
  1. Each environment has a mapping from every generic action it supports
     to its implementation, and declares the ones it lacks
     ([REQ-10](#req-10-declared-capabilities)).
- **Verification:** an environment conformance test per supported
  environment.
- **Delivered by:** #1183, #1222, #1232.

#### REQ-09. Harnesses

- **Applies when:** an agent is launched, briefed or resumed in a coding
  harness.
- **Obligation:** everything harness-specific (launch flags, trust, hooks,
  skill loading, resume) MUST live in one adapter per harness. Adding a
  harness MUST mean adding an adapter and its tests, with no edits to its
  consumers.
- **Acceptance criteria:**
  1. Shared plumbing has no branch on a harness name.
  2. Each adapter supplies the complete recipe its consumers need.
- **Verification:** adapter contract tests; a lint for harness names in
  shared code (D7).
- **Delivered by:** #1182.

#### REQ-10. Declared capabilities

- **Applies when:** an environment, connector or harness cannot do
  something a role or invariant needs.
- **Obligation:** it MUST declare the gap. Consumers MUST branch on declared
  capabilities, never on a module's name. A combination that cannot keep a
  [portable.md invariant](portable.md#3-invariants) is unsupported and MUST
  be rejected at profile validation, never silently weakened.
- **Acceptance criteria:**
  1. Each module ships a capability declaration.
  2. Profile validation rejects a combination with a missing required
     capability, and names it.
- **Verification:** validator tests with a fake module that lacks a
  capability.
- **Delivered by:** #1183, #1217, #1236.

### Generic actions

#### REQ-11. Role text uses generic actions only

- **Applies when:** role or protocol text needs an operation such as
  notifying a role, waiting for an event, claiming work, recording a
  heartbeat or reporting done.
- **Obligation:** it MUST name the generic action, never the runtime
  command, file, window or variable that implements it.
- **Acceptance criteria:**
  1. Canonical role and protocol files contain no runtime words (session
     backend names, inbox, window, runtime environment variables, CLI
     subcommands of an environment).
- **Verification:** a `check-repo` runtime-word lint over `roles/` and
  `protocols/` (D5).
- **Delivered by:** #1185, #1221.

#### REQ-12. Actions contract

- **Applies when:** a generic action is added, changed or implemented.
- **Obligation:** the vocabulary MUST be defined once, in `actions/`, with
  each action's arguments, semantics, result and failure behaviour. Roles,
  protocols and environments MUST use only actions the contract defines.
- **Acceptance criteria:**
  1. Every action has a stable name, arguments, result, failure behaviour
     and the invariant it protects.
  2. Each environment mapping covers the contract or declares the gaps.
- **Verification:** a contract lint that every action named in `roles/` or
  `protocols/` exists in `actions/`.
- **Delivered by:** #1218 (vocabulary from #1213).

#### REQ-13. CLI as the terminal implementation

- **Applies when:** the terminal environment implements generic actions.
- **Obligation:** it MUST expose them as CLI subcommands with stable names,
  arguments, exit codes and JSON output, as the actions contract specifies.
  A tool-server protocol MAY come later and is not required.
- **Acceptance criteria:**
  1. Each supported action has a subcommand whose exit codes and JSON match
     the contract.
  2. Today's terminal behaviour is preserved underneath.
- **Verification:** CLI contract tests asserting exit code, stdout JSON and
  stderr.
- **Delivered by:** #1232.

#### REQ-14. Durable record over ephemeral delivery

- **Applies when:** an action delivers a message or changes work state.
- **Obligation:** ephemeral delivery (a prompt typed into a session, a
  push notification) MUST NOT be the only record. The durable copy MUST
  stay in the environment's replayable queue and the audit trail in the
  tool of record ([portable.md invariant 5](portable.md#3-invariants)).
- **Acceptance criteria:**
  1. Every state-changing action names its durable record in the contract.
- **Verification:** contract review; a replay test after a lost delivery.
- **Delivered by:** #1218, #1232.

### Terminal fast lane

#### REQ-15. Terminal environment is the owned fast lane

- **Applies when:** the team runs locally in terminal sessions.
- **Obligation:** the terminal environment is this project's own,
  lowest-latency environment and its reference implementation of the
  generic actions. Speed MUST come from orchestration (waking without
  model turns, parallel sessions, local checks), never from skipping a
  gate the protocol requires.
- **Acceptance criteria:**
  1. Every protocol gate holds in the terminal environment.
  2. Other environments are tested against the same actions contract.
- **Verification:** the existing campaign and regression suites at each
  release.
- **Delivered by:** #1222, #1232.

#### REQ-16. Session backend chosen per host

- **Applies when:** the terminal environment starts sessions on a host.
- **Obligation:** the session backend MUST be chosen per host: an enhanced
  backend where it is installed and healthy, and a universally available
  default (tmux) as the fallback. Installing a backend MUST NOT be required.
  Roles MUST NOT change with the backend.
- **Acceptance criteria:**
  1. The profile or auto-detection picks a backend per host and falls back
     to the default when the preferred one is missing or unhealthy.
- **Verification:** backend selection tests with fake backends.
- **Delivered by:** #1183.

### Personal knowledge

#### REQ-17. Knowledge in external services

- **Applies when:** a role needs the owner's personal knowledge or memory.
- **Obligation:** personal knowledge MUST live in an external service and be
  reached through a `knowledge` connector concern. It MUST NOT be committed
  to any repository the team works on, this one included.
- **Acceptance criteria:**
  1. The concern table in portable.md lists `knowledge`.
  2. No personal knowledge content is tracked in git.
- **Verification:** the secret and denylist scans; reviewer check.
- **Delivered by:** #1217, #1229.

#### REQ-18. Read and propose-edit

- **Applies when:** a role reads or changes knowledge.
- **Obligation:** the connector MUST offer `knowledge-read` and
  `knowledge-propose-edit`. A role MUST NOT change knowledge except as a
  proposal the owner or the backend's review step accepts. The first
  backend is a hosted notes service (Notion).
- **Acceptance criteria:**
  1. Both actions are in the actions contract.
  2. Backend tests use fakes with no network.
- **Verification:** connector tests with fakes.
- **Delivered by:** #1229.

#### REQ-19. Private source pointers

- **Applies when:** a deployment configures where knowledge lives.
- **Obligation:** source pointers and credentials MUST come only from
  private or local config, never from committed files. Each role MUST
  declare the knowledge sources it needs.
- **Acceptance criteria:**
  1. Committed config holds only source names, never locations or
     credentials.
  2. A role that uses knowledge declares its sources in `role.toml`.
- **Verification:** the secret scan; a config test that rejects a committed
  pointer; sensitive-class review.
- **Delivered by:** #1229.

### Seats, staff and team heads

#### REQ-20. Role classes

- **Applies when:** a role is registered.
- **Obligation:** each role MUST declare its class: an **owner-facing seat**
  (directly addressable by the owner) or **internal staff** (never faces the
  owner). Internal staff MUST declare their owning seat and escalation path.
- **Acceptance criteria:**
  1. `role.toml` carries class, owning seat and escalation path.
  2. Registry validation rejects internal staff without an owning seat.
- **Verification:** registry schema tests.
- **Delivered by:** #1227.

#### REQ-21. Only seats face the owner

- **Applies when:** a role needs an owner decision or reports to the owner.
- **Obligation:** only owner-facing seats MUST deliver owner asks and
  reports. Internal staff MUST escalate to their owning seat, which decides
  or carries the ask. Technical matters go to the technical seat (CTO).
- **Acceptance criteria:**
  1. The protocol states the rule.
  2. No internal staff brief tells the role to ask the owner directly.
- **Verification:** a brief lint for owner-ask wording in internal roles;
  reviewer check.
- **Delivered by:** #1227, #781.

#### REQ-22. Team heads and seat placeholders

- **Applies when:** a team of roles is defined.
- **Obligation:** each team MUST have one head that coordinates it, as the
  coordinator does today. The engineering team's head maps to the technical
  seat. Seat content MAY be authored elsewhere; this repo MUST provide seat
  packages in the role-package shape, with no personal data.
- **Acceptance criteria:**
  1. Each team declares its head in metadata.
  2. Seat placeholder packages and a seat template exist.
- **Verification:** registry tests; denylist and personal-data review.
- **Delivered by:** #1227, #1228, #781.

### Modules and self-hosting

#### REQ-23. Modular layout with enforced dependency rules

- **Applies when:** a file is added or moved, or a module references
  another.
- **Obligation:** the repo MUST follow the layout in [§4](#4-target-module-layout)
  and the rules in [§5](#5-dependency-rules), enforced by a lint. The
  reorganisation MUST land as move-only changes kept apart from behaviour
  changes, with compatibility shims at old paths for one major version.
- **Acceptance criteria:**
  1. The dependency lint passes on `main` and fails a fixture that breaks
     each rule.
  2. Old entry points keep working for one major version.
- **Verification:** the lint's tests; the release smoke test of an
  extracted bundle.
- **Delivered by:** #1222, #1224, #1226.

#### REQ-24. Self-hosted specs

- **Applies when:** a change alters how this project is shaped (layout,
  axes, roles, actions, gates).
- **Obligation:** it MUST be specified in `docs/specs/` first and land
  through a `crew:spec` PR on the owner's merge-ok, as for any project the
  crew runs. `docs/specs/` is this repo's source of truth.
- **Acceptance criteria:**
  1. Each shape-changing roadmap issue cites the spec requirement it
     implements.
- **Verification:** reviewer check against the cited `REQ-` ID.
- **Delivered by:** this spec; #1219 and #1225 extend the rule to every
  project.

## 4. Target module layout

The layout is the target of the M31 move-only reorganisation (#1222). Each
row names today's sources.

| Module | Holds | Today |
|---|---|---|
| `roles/<team>/<role>/` | Portable role packages: `role.toml`, entry `SKILL.md`, `skills/<skill>/SKILL.md`, `routines/<routine>.toml` (recurring jobs, [routines](../routines.md), #1247), rare `variants/<harness>/` | `roles/eng.toml`, `templates/runtimes/*` |
| `roles/seats/<seat>/` | Owner-facing seat packages (placeholders) | none |
| `protocols/eng/` | Stages, markers, rounds, gates, flavors, evidence | `docs/protocol.md`, `docs/flavors.md`, `docs/verification.md`, `docs/express-lane.md` |
| `protocols/conventions/` | Signatures, owner communication, decision log, triage | `docs/triage.md`, protocol sections |
| `actions/` | Generic action vocabulary and CLI contract | none (#1213 research) |
| `connectors/<tool>/` | Tool concerns: change, review, tracker, labels, markers, CI, events, knowledge | `packs/github/`, `docs/backends/github.md`, `templates/backends/` |
| `environments/terminal/` | Watcher, router, leads, scheduler, spawn and kill, inbox bus; `sessions/<backend>/`; `remote/` | `scripts/crew`, `scripts/crew.d/*`, session backend scripts, `docs/runtimes/multi-device.md` |
| `environments/<platform>/` | Hosted-platform and single-session bindings | `templates/runtimes/grok-bot/`, `docs/runtimes/session.md` |
| `harnesses/<harness>/` | Launch, trust, hooks and skill loading per harness | `scripts/crew.d/_shared.py`, `docs/runtimes/harness-adapters.md` |
| `core/` | Shared libraries only: config schema and resolver, renderer, state store | `scripts/crew-config.py`, `scripts/crew-render.py` |
| `cli/` | The `mdstack` entry point, dispatching actions to the active environment | `scripts/crew` |
| `profiles/` | Install-time profiles and presets | `profiles/` |
| `install/` | Bootstrap, upgrade, release bundle | install and release scripts |
| `dev/` | Repo QA: check-repo, markdown, changelog, campaign harness, metrics, tests and fixtures | `scripts/check-*.py`, `scripts/test-*.py` |
| `docs/` | Narrative only: architecture, concepts, specs, runbooks, lessons, findings, pointing into the modules | `docs/` |

## 5. Dependency rules

A lint in `dev/` enforces these (#1224). "References" means imports, path
references and, for text modules, naming the other module's concepts.

| ID | Rule |
|---|---|
| D1 | `roles/` references only `protocols/` and `actions/`. |
| D2 | `protocols/` references only `actions/`. |
| D3 | `connectors/`, `environments/` and `harnesses/` implement `actions/` and may use `core/`; none of them references another of the three except through `actions/` or a declared capability. |
| D4 | `core/` depends on no module above it. |
| D5 | Only `environments/terminal/` names session backends, inboxes, windows or the terminal's environment variables. |
| D6 | Only `connectors/` names a tool of record's CLI or API. |
| D7 | Only `harnesses/` names harness launch flags, hooks or trust settings. |
| D8 | `cli/` dispatches to environments through `actions/`; it holds no role policy. |
| D9 | `docs/` may reference any module; no module depends on `docs/`. |

## 6. Relation to portable.md

This spec cites [portable.md §2](portable.md#2-requirements) and does not
restate it. #1217 updates portable.md to v0.4 with the harness axis, the
`knowledge` concern and the extension mechanism.

| portable.md | Used here by |
|---|---|
| P1 runtime abstraction | REQ-01, REQ-08: environments are the runtime bindings |
| P2 tool abstraction per concern | REQ-07, REQ-17: connectors implement concerns; `knowledge` joins them |
| P3 minimum backend contract | REQ-10: capability declarations extend to environments and harnesses |
| P4 install-time profile | REQ-06: the profile selects one value per axis |
| P5 config layers | REQ-19: knowledge pointers sit only in private or local layers |
| P6 no org-internal names | REQ-22 and this spec's own wording; packs supply org specifics |
| P7 default profile stays complete | REQ-06: the default profile picks a complete value on every axis |
| P8 keeps working after every merge | REQ-23: move-only and behaviour changes never share a PR |

## 7. Open questions

| Question | Settled in |
|---|---|
| Q1. Are team heads themselves seats, or internal staff with a seat above them? | #1227: either; a head facing the owner is its team's seat (the eng head holds `cto`), a head under another seat is internal staff ([roles-registry.md](../roles-registry.md#role-classes)) |
| Q2. Which actions are required for every environment, and which are optional capabilities? | #1218 |
| Q3. Does `knowledge-propose-edit` land through the owner's review in the service, or through a team proposal record? | #1229 |
| Q4. Does the runtime-word lint (D5) run before the reorganisation, against today's paths? | #1185 |
| Q5. How long do the compatibility shims at old paths stay: one major version, or until packs confirm? | #1226 |
| Q6. Do role classes and seats belong in `docs/specs/` of every project, or only here? | #1219 |

## 8. Out of scope

- Org-specific connectors, environments or seat content (packs; P6).
- Adapters for further hosted platforms, and a session backend driven by an
  agent-state API (dropped for now by the owner, 2026-11-07).
- The CLI and repo rename (M33), beyond keeping the layout rename-ready.
- Any change to a live merge gate or marker rule.
