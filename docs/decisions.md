# Decisions

Dated project decisions for eng-crew, newest first: what was decided, why,
and the options rejected. It is eng-crew's own decisions doc in the
[essential doc set](project-doc-set.md#essential-doc-set). Seeded on
2026-11-07 ([#1219](https://github.com/mw-ding/eng-crew/issues/1219)) from
the [decision log on #985](https://github.com/mw-ding/eng-crew/issues/985);
decisions before 2026-11-05 are on the closed
[#110](https://github.com/mw-ding/eng-crew/issues/110).

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
