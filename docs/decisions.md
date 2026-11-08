# Decisions

Dated project decisions for mdstack, newest first: what was decided, why,
and the options rejected. It is mdstack's own decisions doc in the
[essential doc set](project-doc-set.md#essential-doc-set). Seeded on
2026-11-07 ([#1219](https://github.com/mw-ding/eng-crew/issues/1219)) from
the [decision log on #985](https://github.com/mw-ding/eng-crew/issues/985);
decisions before 2026-11-05 are on the closed
[#110](https://github.com/mw-ding/eng-crew/issues/110).

Entries whose record is **ported in #1235** come from the owner's old
private design repo, whose discussion was never public.
[#1235](https://github.com/mw-ding/eng-crew/issues/1235) carried the
public-safe part over, so for those entries this file is the public record.
They include three older seat decisions, kept at the end.

The coordinator still records each owner decision on #985 first, in the
owner's words and time. This file keeps the ones that shape the project.
A **Why** or **Rejected** line appears only where the record states one.
Short-lived operating state (presence caps, scheduler stopgaps, per-PR
merge-oks, time-boxed grants, away records) stays on #985 only. Each entry
links its record; the record is authoritative.

## 2026-11-07: public docs run and major cut after the roadmap (M34)

- **Decision:** after M29–M33, a docs consolidation for the modular
  structure (#1237), getting-started, pack-author and migration guides
  (#1238) and a major release cut with notes for M29–M34 (#1239).
- **Record:** [#985 comment 6703974863](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6703974863)

## 2026-11-07: roadmap M29–M33 and M28 superseded

- **Decision:** M29 specs and contracts (`fast`, docs only), M30 decouple in
  place (refactor only, `fast`), M31 modular reorganisation with one major
  cutover (`standard`), M32 team beyond engineering (`standard`), M33 rename
  (`standard`). M28 closes as superseded and its issues move to M30. M32
  follows M31.
- **Rejected:** Grok Bot and Hermes adapters and herdr agent-API support,
  dropped for now. M20.1 and M25.1 stay deferred backlogs.
- **Record:** [#985 comment 6703873152](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6703873152)

## 2026-11-07: settle the old private design repo

- **Decision:** the remaining public-safe content of the owner's old private
  design repo moves here (#1235), and the owner archives that repo. Personal
  content goes to the knowledge service, never into git.
- **Why:** the seats are public (owner OK) and personal memory lives in
  external services ([memory](memory.md)), so roles no longer need a
  private git home. Only private install config stays private, in the local
  install.
- **Record:** [#1235 comment 6713290565](https://github.com/mw-ding/eng-crew/issues/1235#issuecomment-6713290565); ported in #1235

## 2026-11-07: generic actions are CLI-backed, MCP only where needed

- **Decision:** generic actions and the terminal's connectors use a local
  CLI (`gh`, `git`, `crew`) with a stable contract
  ([team spec REQ-13](specs/team.md#req-13-cli-as-the-terminal-implementation)).
  An MCP wrapper comes only for an environment that cannot run a CLI.
- **Why:** owner: an MCP server is heavy, and CLIs are lighter than a
  dedicated MCP server for the forge.
- **Not decided:** A2A was assessed and left out of the roadmap. It would
  need an HTTP endpoint and a sidecar per terminal agent and still needs
  the doorbell to reach a running turn, while the file inbox already gives
  durability, replay and dedup. It may fit later behind the generic
  `notify` action, for a handoff between environments that both speak it.
- **Record:** ported in #1235

## 2026-11-07: specialist roles, team heads and front doors

- **Decision:** roles are specialists: a skill bundle plus authority plus
  persona, with clear boundaries. Each team keeps one head that coordinates
  it; for engineering that is the coordinator, holding the `cto` seat. Every
  owner-facing seat is directly addressable: the CEO seat is the general
  front door, technical matters go straight to the CTO seat, and seats do
  not gatekeep each other. Every role can run in the terminal under its own
  lifecycle: always on, a lead with elastic workers, or on demand
  ([lifecycle](roles-registry.md#lifecycle)).
- **Why:** from the evaluation the owner accepted: an independent reviewer
  and validator on a different engine caught real defects (#1164, #1181, #1172, #1186) that self-review would
  miss, and merging needs separation of duties.
- **Rejected:** generalist workers with no role boundaries; a separate
  project-manager role under the CTO (parked as an idea).
- **Record:** ported in #1235

## 2026-11-07: roles are portable employees with continuity

- **Decision:** every role, owner-facing seats and department staff such as
  the engineering crew, is a durable virtual employee of the owner's
  company: defined once in git and deployable in any environment with the
  same identity and knowledge. Knowledge carries over: identity, skills,
  protocols, conventions and core memory. In-flight work moves only on the
  owner's explicit request, through a checkpoint in a repo (a branch, a
  draft PR or a handoff note) that the same role picks up elsewhere. There
  is no live session migration.
- **Why:** the owner moves between platforms and wants the same team on
  each.
- **Record:** ported in #1235

## 2026-11-07: a role and protocol layer with one owned environment

- **Decision:** this project is the role and protocol layer. The native
  terminal (tmux or herdr) is the one environment it owns, the fast lane
  for building. Hosted platforms are borrowed through thin adapters; a
  runtime is built only where none exists, which today is the gated
  multi-agent coding loop.
- **Why:** rebuilding a general agent platform alone would duplicate mature
  projects. What is distinctive is a governed multi-role team and employees
  as reviewed git assets. Terminals finish building work faster than
  turn-based chat wakes, so portability must never slow the terminal.
- **Outcome:** the repo arrangements discussed (a separate private role
  repo, a monorepo, a fresh private repo) gave way to the roadmap: this
  repo grows into the layer and is renamed in M33.
- **Record:** ported in #1235

## 2026-11-07: specs are every project's source of truth

- **Decision:** `docs/specs/` joins the essential project doc set, and
  eng-crew adopts its own doc set (this file, the runbook entry point).
- **Why:** owner: specs are every project's source of truth, including this
  repo.
- **Record:** [#1219](https://github.com/mw-ding/eng-crew/issues/1219)

## 2026-11-07: finish M25, then freeze execution for the roadmap

- **Decision:** land the M25 report (#1186) as it is and close M25; no new
  execution, including the post-M25 release cut, until the roadmap is
  settled. M28 paused.
- **Why:** the owner was discussing the roadmap and could change it.
- **Record:** [#985 comment 6702399811](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6702399811)

## 2026-11-06: a grant's wording can satisfy gate-contract merge-ok

- **Decision:** while a recorded, time-boxed owner grant explicitly names
  gate changes, a coordinator-recorded merge-ok at head that cites it
  satisfies per-change permission for a gate-contract change. Sensitive,
  spec and release-cut rules are unchanged.
- **Why:** it matched what the owner had granted and made earlier landings
  consistent.
- **Follow-up:** protocol text alignment, #1167.
- **Record:** [#985 comment 6699129743](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6699129743)

## 2026-11-06: explicit holds block dispatch

- **Decision:** `hold_label_blocks = true` in the live profile, so an
  explicit `crew:hold` stops dispatch; #1124 retires the old lane-label
  meaning.
- **Record:** [#985 comment 6696969590](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6696969590)

## 2026-11-06: M25 register P1 rows fixed in M25

- **Decision:** the seven P1 rows from the #805 finding register (#1118,
  #1124, #1088, #1089, #1042, #1106, #818) are fixed inside M25; gate and
  sensitive ones run `thorough`.
- **Rejected:** closing M25 on the earlier set and moving them to a
  follow-up milestone.
- **Record:** [#985 comment 6695225753](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6695225753)

## 2026-11-06: owner-environment work moves to M25.1

- **Decision:** level-a coverage lands as `Refs #804`; the #805 finding
  register loop is activated; items that need the owner's environment
  (#797, #716, #209, #213, #157, #158, #1028) move to M25.1 so M25 can close.
- **Record:** [#985 comment 6693415281](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6693415281)

## 2026-11-05: defer #646 permission approval

- **Decision:** #646 leaves M27.1 and v5.2.0 ships without it; #1039 stays
  held.
- **Why:** the #1039 review hit a provider safety refusal. The standing rule
  forbids retrying or rewording to get past one, so the PR is parked for the
  owner.
- **Rejected:** a partial release, or retrying the review.
- **Record:** [#985 comment 6668478516](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6668478516)

## 2026-11-05: a follow-up milestone instead of a new one (M27.1)

- **Decision:** finish config-only packs in M27.1 (#926, #914, #646, the
  v5.2.0 cut #1030) before the docs milestones; every item stays backward
  compatible, and a Breaking fragment means stop and ask.
- **Rejected:** opening M28 for them.
- **Record:** [#985 comment 6665974423](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6665974423)

## 2026-11-05: triage runs in apply mode

- **Decision:** `[triage] mode = "apply"`. The researcher applies only
  low-risk, reversible outcomes (type, priority band, scope labels, default
  flavor); closes, milestone changes and active-milestone placement other
  than an owner P0 stay proposals. Triage also dedupes similar issues.
- **Why:** the recalibration sample scored 9/10 accepted as is.
- **Record:** [#985 comment 6650833193](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6650833193)

## 2026-11-05: triage priority bands and owner P0 calls

- **Decision:** priority bands get explicit criteria, and an explicit owner
  P0 call settles P0.
- **Why:** half of a sampled set had priorities set too high.
- **Not decided:** a cap of P0 to issues confirmed on the project's own
  backend.
- **Record:** [#985 comment 6650468084](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6650468084), [comment 6650510545](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6650510545)

## 2026-11-05: triage checks an item still applies

- **Decision:** before proposing, triage checks whether an item is already
  built or no longer applies (#987).
- **Why:** owner spot-check 1 rejected stale and superseded items.
- **Record:** [#985 comment 6650080658](https://github.com/mw-ding/eng-crew/issues/985#issuecomment-6650080658)

## 2026-11-01: seats are content that runs on this machinery

- **Decision:** the seats are role content that runs on this repo's
  machinery (sessions and waking, rendering, release). Seat content never
  reimplements machinery, and the engineering team's roles and protocol stay
  here; the CTO seat links to them rather than defining a parallel crew.
  Seat file shapes and action names stay compatible with this repo's roles.
- **Record:** ported in #1235

## 2026-10-31: contexts as packs, and a seat action vocabulary

- **Decision:** a shared core of roles and general skills, plus one pack per
  context (personal, employer, others) that binds actions to concrete tools,
  adds context-only skills and declares the environment's constraints. An
  employer's pack lives in that employer's environment, never here. Each
  context runs its own coordinator instance from the same definitions, with
  no shared memory; crossing contexts goes only through an owner-approved
  summary. Config lives in packs, never in a skill.
- **Carried forward:** a starting vocabulary for seat actions, with read and
  write kept apart: `calendar.read`, `calendar.write`, `mail.read`,
  `mail.send`, `chat.send`, `reminders.write`, `docs.read`, `docs.write`,
  `finance.read`. These are candidates for the [actions](../actions/README.md)
  contract once seats gain skills; none is implemented.
- **Record:** ported in #1235

## 2026-10-30: six owner-facing seats

- **Decision:** the owner's company has six seats. Each seat's content is
  written by the owner's seat team elsewhere and dropped into the
  [seat placeholders](../roles/seats/TEMPLATE.md); this is the decided
  starting point.

  | Seat | Persona | Owns |
  |---|---|---|
  | CEO | 🏔 Sol | Strategy, decisions, delegation and coordinating the seats; the owner's general front door |
  | CTO | 🔥 Ash | Engineering: architecture, building, debugging; heads the engineering team |
  | CPO | 🧭 Sage | Product strategy, research, PRDs, plus marketing and public presence |
  | COO | 🌊 Kai | Operations: calendar, reminders, email, logistics, tracking execution |
  | CDO | 🎨 Iris | Design: UI/UX, visuals, prototypes, branding, design-system coherence |
  | CFO | ⚖️ Rune | Finance: budgeting, investments, tax, equity, cost-benefit of life decisions |

- **Hand-offs:** the CEO coordinates across seats. Peers work directly where
  their domains meet: CFO with COO on subscriptions, CFO with CPO on the ROI
  of product and marketing spend, CDO with CPO on brand. Engineering
  operations go to the engineering team under the CTO.
- **Limits for every seat:** no model, provider or reasoning settings;
  nothing org-internal; irreversible, financial or external actions need the
  owner's approval.
- **Rejected:** a separate CMO seat (marketing sits with the CPO).
- **Record:** ported in #1235
