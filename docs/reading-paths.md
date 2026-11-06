# Reading paths

Where each role finds its static instructions: what to read at start, what to
re-read every wake and what to load when a trigger fires. Navigation only:
every rule lives in the linked doc, and a role's rendered brief stays its
operating instruction. This page adds, removes and reorders no duty. A linked
doc is not optional because it is linked; load it before its trigger is
handled.

Every operating role still runs the wake duties in
[protocol §6](protocol.md#6-duties-on-wake-all-roles) (ownership, live state,
holds, idempotency). A reading path changes where static text is found, not
when live state is re-read. For maintainer navigation and the full doc
catalog, see the [docs index](README.md).

The briefs named below are the tmux templates under
`templates/runtimes/tmux/`; the Grok Bot equivalents are listed in
[runtimes/grok-bot.md](runtimes/grok-bot.md).

## Start

Read once on session start or recovery, and again after an instruction-version
change.

| Role | Start reading |
|---|---|
| Coordinator | Rendered `coordinator.md` brief; [roles.md, Owner communication](roles.md#owner-communication-coordinator); [protocol §7](protocol.md#7-merge-gate-synthesizer) landing authority; the runtime binding ([runtimes/tmux.md](runtimes/tmux.md)) |
| Builder | Rendered `builder.md` brief; the repo's `AGENTS.md`; [roles.md, Worker brief template](roles.md#worker-brief-template) and [PR conventions](roles.md#pr-conventions); the assigned issue's acceptance criteria |
| Reviewer-validator | Rendered `reviewer.md` brief for the assigned pass; the repo's `AGENTS.md`; [roles.md, Reviewer engine selection](roles.md#reviewer-engine-selection) and [Actual builder engine](roles.md#actual-builder-engine) |
| Synthesizer | Rendered `synthesizer.md` brief; [protocol §7](protocol.md#7-merge-gate-synthesizer) including the [gate registry](protocol.md#gate-registry), [verdict portability](protocol.md#verdict-portability-and-delta-re-review) and [land rules](protocol.md#land-rules-and-merge-trains) |
| Researcher | Rendered `researcher.md` brief; the latest signed request; [roles.md, Researcher](roles.md#researcher-riley) |
| Builder and reviewer leads | Rendered `builder-lead.md` or `reviewer-lead.md` brief; [runtimes/tmux.md, Builder lead](runtimes/tmux.md#builder-lead) or [Reviewer lead](runtimes/tmux.md#reviewer-lead); [scheduling.md](scheduling.md) |
| Owner | No wake duty. [../README.md](../README.md), then [flavors.md](flavors.md) and [protocol §9](protocol.md#9-steering-crew-commands) for steering |
| Adopter | [../README.md](../README.md), then [runbook-new-repo.md](runbook-new-repo.md) by chosen runtime, [bootstrap.md](bootstrap.md) and the runtime binding |
| Pack author | No wake duty. [concepts.md](concepts.md), [interfaces.md](interfaces.md), [runtimes/README.md](runtimes/README.md), [profile.md](profile.md), [roles-registry.md](roles-registry.md), [packs.md](packs.md), then the selected binding |

## Every wake

Live state the brief's guards re-read on each wake, per
[protocol §6](protocol.md#6-duties-on-wake-all-roles). Static docs are not
reloaded unless a trigger below fires.

| Role | Re-read every wake |
|---|---|
| Coordinator | Ownership, inbox and drain, live control, item and head state, holds |
| Builder | Ownership, the current issue, PR and head, the [change flavor](protocol.md#change-flavor), inbox, holds |
| Reviewer-validator | Ownership, the live head, change flavor, holds and existing pass records ([markers](protocol.md#4-marker-conventions)) |
| Synthesizer | On every land: ownership, control, head, CI, holds, permission and the evidence and verdict refs the [§7 gate](protocol.md#7-merge-gate-synthesizer) names |
| Researcher | Before each write: ownership, the live request and its pass record |
| Builder and reviewer leads | Pending and in-flight refs, live pool, item and head state |

## Triggers

Load the linked doc before handling the trigger.

| Role | Trigger | Load |
|---|---|---|
| Coordinator | Owner ask, away or return | [roles.md, Owner communication](roles.md#owner-communication-coordinator); [protocol, Owner away mode](protocol.md#owner-away-mode) |
| Coordinator | Owner feedback | [self-improve.md, Owner-feedback recipe](self-improve.md#owner-feedback-recipe) |
| Coordinator | Crew defect that blocks or slows the run | [self-improve.md, Runtime-blocker recipe](self-improve.md#runtime-blocker-recipe) |
| Coordinator | Triage window or flavor suggestion | [roles.md](roles.md) Coordinator triage and Flavor suggestions; [flavors.md, Owner accept path](flavors.md#owner-accept-path) |
| Coordinator | Metrics gate | [metrics/decisions.md](metrics/decisions.md) |
| Coordinator | Milestone close | [self-improve.md, Triggers](self-improve.md#triggers); [triage.md, Triggers and cadence](triage.md#triggers-and-cadence) |
| Coordinator | CI and findings handoff | [runtimes/tmux.md, crew route](runtimes/tmux.md#crew-route) |
| Coordinator | Runtime handoff | [handoff.md](handoff.md) |
| Builder | Pre-review check enabled | [protocol, Builder pre-review check](protocol.md#builder-pre-review-check) |
| Builder | Behaviour change needing proof | [verification.md, Builder](verification.md#builder), the [shape](verification.md#shapes) and [../templates/evidence/](../templates/evidence/README.md) |
| Builder | Fix or CI-fix round | [roles.md, Fix note](roles.md#fix-note-crew-and-solo-builders); [protocol §5](protocol.md#5-rounds-and-escalation) |
| Builder | Express change | [express-lane.md, Self-gate loop](express-lane.md#self-gate-loop) |
| Builder | Any step, test or lint run | [observe.md](observe.md#when-to-write-a-step-line) |
| Reviewer-validator | Review pass | [protocol §3](protocol.md#3-evidence-requirements) and [§4](protocol.md#4-marker-conventions) |
| Reviewer-validator | Validation pass | [verification.md, Reviewer-validator](verification.md#reviewer-validator) for the touched shapes and ACs |
| Reviewer-validator | Recheck after a new head | [protocol, Verdict portability and delta re-review](protocol.md#verdict-portability-and-delta-re-review) |
| Synthesizer | Train composition or failure, direct land | [protocol, Land rules and merge trains](protocol.md#land-rules-and-merge-trains); [runtimes/tmux.md, crew train](runtimes/tmux.md#crew-train) |
| Synthesizer | Release cut | [release.md](release.md) |
| Researcher | Request names source docs | Only the docs the request names |
| Researcher | Docs pass (`riley-docs`) | [project-docs.md, Docs pass](project-docs.md#docs-pass) and [project-doc-set.md](project-doc-set.md) |
| Researcher | Triage sweep (`riley-sweep`) | [triage.md](triage.md): [Skip rules](triage.md#skip-rules), [Learning lookup](triage.md#learning-lookup), [Outcomes](triage.md#outcomes) and [Triage record](triage.md#triage-record) |
| Builder and reviewer leads | Spawn, reclaim, terminal or recovery | [runtimes/tmux.md, Role leads](runtimes/tmux.md#role-leads-proposed-521) |
| Any role | Sensitive path in the diff | [protocol, Sensitive class](protocol.md#sensitive-class) |
| Any role | Ownership refused | [protocol, Ownership record](protocol.md#ownership-record); [runtimes/tmux.md, Ownership fallback](runtimes/tmux.md#ownership-fallback) |
