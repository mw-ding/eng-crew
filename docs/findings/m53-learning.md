# M53 repaired learning batch

**Last updated:** 2026-11-13

L1 ([#1793](https://github.com/mw-ding/mdstack/issues/1793)) captures 24 cards
in one batch under [When to batch](README.md#when-to-batch). The title of L1
names M45–M50; its explicit card list also includes M35–M40 incidents, all
retained here. This records repairs and prevention already present, without
changing a product, gate, template or live installation.

## Reconciliation

- One row per card and distinct failure class; 27 occurrences in total.
  Count an incident once, regardless of repeated reviews, comments or triage.
- Source/repair lists PR numbers in that order. When they are the same PR,
  the repair happened before that PR merged. Source cards link the original
  findings and repair records; later occurrences are reconciled below.
- Retained tests/procedures were inspected at builder base
  `660b62045c29030b1475b0529ab39bfcad8e479e`, where the listed files exist.
  These are source/history reads, not fresh runtime captures or test results.
- Each row is its findings disposition, using the
  [lesson status vocabulary](../lessons/README.md#status-vocabulary).
  `applied` identifies a retained repair/test or procedure; it does not mean
  a general guard prevents every future recurrence. No separate lesson file
  is needed for these bounded records.
- Coordinator: after this batch merges, close only settled source cards with
  a link to their row. This PR closes L1 alone. No missing requested
  prevention was found in this inspection; if review finds one, keep its
  card open as a separate work unit and name it on the PR.

## Cards

Test paths below are relative to the repo root; named cases identify what
must be retained. The uncertainty column bounds each row's claim.

| Card / failure class | Finding and impact | Source / repair PR | Retained regression or procedure | Occurrences | Uncertainty | Disposition |
|---|---|---|---|---|---|---|
| [#1381](https://github.com/mw-ding/mdstack/issues/1381) `default-layout-inactive` | Commented-out shipped paths left the default layout inactive; a test injecting paths missed it. | [#1338](https://github.com/mw-ding/mdstack/pull/1338) / same | [test-crew-layout.py](../../dev/tests/environments/test-crew-layout.py), `test_shipped_tmux_profile_defaults_to_the_one_root_layout`: resolve shipped profile without injecting desired paths. | 1 | No fresh install run. | applied: shipped default and direct-profile regression retained. |
| [#1382](https://github.com/mw-ding/mdstack/issues/1382) `bootstrap-default-config-parent-missing` | Fresh-home proposal succeeded, but confirmed write failed ENOENT because the config parent was absent. | [#1338](https://github.com/mw-ding/mdstack/pull/1338) / same | [test-crew-bootstrap.py](../../dev/tests/environments/test-crew-bootstrap.py), `test_user_level_proposal_takes_the_repo_from_the_current_checkout`: absent home config, dry run, then confirmed write. | 1 | No fresh bootstrap run. | applied: parent creation and confirmed-write case retained. |
| [#1383](https://github.com/mw-ding/mdstack/issues/1383) `upgrade-legacy-served-project-discovery` | Older install records lacked the project field; upgrade could switch current without upgrading served projects. | [#1349](https://github.com/mw-ding/mdstack/pull/1349) / same | [test-crew-user-install.py](../../dev/tests/environments/test-crew-user-install.py), `test_a_prior_format_install_is_recovered_and_upgraded_before_current` and `test_an_unrecoverable_prior_format_install_keeps_current`. | 1 | Historical-format coverage does not claim arbitrary manifest recovery. | applied: discovery and unknown-project refusal retained. |
| [#1384](https://github.com/mw-ding/mdstack/issues/1384) `config-writer-path-omitted` | Doctor fix, schedule and watch wrote selected state without printing the resolved config path. | [#1354](https://github.com/mw-ding/mdstack/pull/1354) / same | [WRITES/dispatcher](../../environments/terminal/crew.d/_shared.py); assertions in [doctor](../../dev/tests/environments/test-crew-doctor.py), `test_missing_state_dir_is_read_only_until_fix`, [schedule](../../dev/tests/environments/test-crew-schedule.py), `DecideCommand.call`, and [watch](../../dev/tests/environments/test-crew-watch.py), `test_watch_reexecs_when_crew_code_changes`. | 1 | Registry still needs review when commands are added. | applied: all three attribution paths retained. |
| [#1446](https://github.com/mw-ding/mdstack/issues/1446) `evidence-capture-stale-after-merge-up` | Correct behavior had stale inline output after merge-up; later template trimming repeated the mismatch. | [#1368](https://github.com/mw-ding/mdstack/pull/1368) / same; [#1527](https://github.com/mw-ding/mdstack/pull/1527) / same | [Evidence-only refresh procedure](../roles.md#fix-note-crew-and-solo-builders), [claim scope](../verification.md#claim-scope), and [capture helper](../../scripts/evidence-cli.py): re-capture changed output at clean current head. | 2 | Process cause unconfirmed; no automated proof-content equivalence claim. | applied: prose only, because comparison depends on live PR evidence/output; both repairs recorded below. |
| [#1466](https://github.com/mw-ding/mdstack/issues/1466) `credential-redaction-after-truncation` | Truncating before redaction exposed a synthetic credential prefix in a forge diagnostic. | [#1450](https://github.com/mw-ding/mdstack/pull/1450) / same | [test-crew-feedback.py](../../dev/tests/environments/test-crew-feedback.py), `test_unreadable_card_list_or_bad_slug_files_nothing`: synthetic credential crosses the 120-character boundary; redact complete line first. | 1 | Synthetic near-miss; real credential exposure not established. | applied: redaction ordering and boundary regression retained. |
| [#1561](https://github.com/mw-ding/mdstack/issues/1561) `reflection-unobserved-window-counted-zero` | Unobserved windows yielded invented zero counts and unrelated sample refs. | [#1528](https://github.com/mw-ding/mdstack/pull/1528) / same | [test-reflection-measures.py](../../dev/tests/scripts/test-reflection-measures.py), `test_windows_outside_capture_stay_unknown` and `test_stall_counts_only_stalls_inside_the_covered_window`. | 1 | No production measurement re-evaluated. | applied: outside-coverage nulls and covered-window filtering retained. |
| [#1562](https://github.com/mw-ding/mdstack/issues/1562) `reflection-effect-period-mismatch` | A growing 28-day total compared with a 14-day baseline produced a false revert recommendation. | [#1556](https://github.com/mw-ding/mdstack/pull/1556) / same | [test-reflection-effects.py](../../dev/tests/scripts/test-reflection-effects.py), `test_counter_windows_stay_equal_length`. | 1 | No production revert established. | applied: equal-length completed windows retained. |
| [#1563](https://github.com/mw-ding/mdstack/issues/1563) `reflection-effect-cohort-unenforced` | Unrelated repo/class input contributed to a recommendation labelled as the proposal cohort. | [#1556](https://github.com/mw-ding/mdstack/pull/1556) / same | [test-reflection-effects.py](../../dev/tests/scripts/test-reflection-effects.py), `test_recommendations_on_the_repo_and_class_cohort` and `test_cohort_not_established_is_insufficient`. | 1 | No live cohort replay. | applied: filtering and insufficient-identity result retained. |
| [#1564](https://github.com/mw-ding/mdstack/issues/1564) `reflection-effect-coverage-omitted` | Non-null counters hid known partial coverage in the sidecar. | [#1556](https://github.com/mw-ding/mdstack/pull/1556) / same | [test-reflection-effects.py](../../dev/tests/scripts/test-reflection-effects.py), `test_coverage_shown_for_each_side`. | 1 | Display coverage does not establish observation completeness. | applied: coverage beside both values retained. |
| [#1565](https://github.com/mw-ding/mdstack/issues/1565) `script-help-usage-omitted` | Three new script help formatters omitted Usage, causing repo-guard failures. | [#1528](https://github.com/mw-ding/mdstack/pull/1528), [#1592](https://github.com/mw-ding/mdstack/pull/1592), [#1719](https://github.com/mw-ding/mdstack/pull/1719) / each same | Full-docstring help in [reflection-measures](../../scripts/reflection-measures.py), [run-usage](../../scripts/run-usage.py), [check-pr-linkage](../../scripts/check-pr-linkage.py); [test-check-repo.py](../../dev/tests/scripts/test-check-repo.py) invokes each script's `--help` and checks Usage. | 3 | A source docstring alone does not prove rendered help. | encoded: existing help-output regression retained; no new guard. |
| [#1601](https://github.com/mw-ding/mdstack/issues/1601) `mosh-proxy-remote-ip-discovery` | Custom ProxyCommand displaced mosh remote-IP discovery and broke the connection contract. | [#1587](https://github.com/mw-ding/mdstack/pull/1587) / same | [test-crew-connect.py](../../dev/tests/environments/test-crew-connect.py), `test_alias_proxy_options_and_passthrough`: proxy adds `--experimental-remote-ip=remote`. | 1 | No live mosh/network replay. | applied: proxy-specific option and command regression retained. |
| [#1602](https://github.com/mw-ding/mdstack/issues/1602) `usage-reader-error-path-disclosure` | An unreadable-log OSError escaped as a traceback naming the log path. | [#1592](https://github.com/mw-ding/mdstack/pull/1592) / same | [test-run-usage.py](../../dev/tests/scripts/test-run-usage.py), `test_unreadable_log_is_na_without_path`: print `tokens n/a` without path. | 1 | Path-disclosure near-miss; secret exposure not established. | applied: unreadable-log fallback retained, distinct from #1466. |
| [#1696](https://github.com/mw-ding/mdstack/issues/1696) `test-class-after-unittest-main` | SessionServer's three cases were defined after script exit, so a passing normal run omitted them. | [#1681](https://github.com/mw-ding/mdstack/pull/1681) / same | [test-crew-doctor.py](../../dev/tests/environments/test-crew-doctor.py), `SessionServer` before `unittest.main()`; [normal-runner retention instruction](#normal-runner-discovery-retention). | 1 | Existing test-layout check does not enforce definition ordering; live owner journey is separate. | applied: ordering and explicit discovery procedure retained; no new general guard. |
| [#1732](https://github.com/mw-ding/mdstack/issues/1732) `memory-snapshot-subdirectory-pathspec` | Render from a subdirectory succeeded without injecting committed memory. | [#1703](https://github.com/mw-ding/mdstack/pull/1703) / same | [crew-memory.py](../../core/crew-memory.py), `ls-tree --full-tree`; [test-crew-render.py](../../dev/tests/core/test-crew-render.py), `test_core_memory_for_a_profile_below_the_git_root`. | 1 | No live memory deployment replay. | applied: repository-relative listing and below-root regression retained. |
| [#1733](https://github.com/mw-ding/mdstack/issues/1733) `bootstrap-sibling-first-link-owner` | Installing the second repo first failed doctor against the not-yet-installed link owner. | [#1706](https://github.com/mw-ding/mdstack/pull/1706) / same | [test-crew-bootstrap.py](../../dev/tests/environments/test-crew-bootstrap.py), `test_the_repo_paths_mdstack_does_not_name_installs_first` plus `test_apply_keeps_the_reference_and_targets_the_selected_clone`: both orders, warning until owner ready. | 1 | Warning does not waive ownership refusals. | applied: owner-readiness handling and both-order coverage retained. |
| [#1734](https://github.com/mw-ding/mdstack/issues/1734) `upgrade-wait-mock-global-clock` | Global sleep patch counted unrelated subprocess polling: reported 410 calls. | [#1703](https://github.com/mw-ding/mdstack/pull/1703) / same | [test-crew-upgrade.py](../../dev/tests/environments/test-crew-upgrade.py), `test_waits_then_applies_and_reloads`: replace upgrade's module-local time reference with wrapping mock. | 1 | Historical call count, not remeasured; product code unchanged by repair. | applied: isolated wait mock retained; distinct from detached-child cleanup. |
| [#1782](https://github.com/mw-ding/mdstack/issues/1782) `resume-retained-work-before-live-eligibility` | Cached holds allowed retained work to restart under a new hold or moved reviewer head. | [#1767](https://github.com/mw-ding/mdstack/pull/1767) / same | [resume.live_block](../../environments/terminal/crew.d/resume.py); [test-crew-resume.py](../../dev/tests/environments/test-crew-resume.py), `test_live_hold_moved_reviewer_head_and_failed_read_keep_runs_stopped`. | 1 | No live resumed campaign proof. | applied: live eligibility before restart retained. |
| [#1783](https://github.com/mw-ding/mdstack/issues/1783) `paused-down-cleans-remote-work` | Plain down bypassed the pause boundary and could delete retained remote work. | [#1767](https://github.com/mw-ding/mdstack/pull/1767) / same | [test-crew-pause.py](../../dev/tests/environments/test-crew-pause.py), `test_plain_down_refuses_while_paused_and_keeps_remote_work`; preserve explicit `down --preserve`. | 1 | No live remote shutdown run. | applied: pause guard and retention regression retained. |
| [#1784](https://github.com/mw-ding/mdstack/issues/1784) `primary-checkout-stale-success-receipt` | Failed prepare at the same path left the prior success receipt reporting ready. | [#1756](https://github.com/mw-ding/mdstack/pull/1756) / same | [test-crew-host.py](../../dev/tests/environments/test-crew-host.py), `test_primary_command_checkout`: success → failed prepare → refused check → repair. | 1 | No real primary host preparation. | applied: receipt invalidation before prepare and sequence retained. |
| [#1785](https://github.com/mw-ding/mdstack/issues/1785) `watcher-stop-process-exit-race` | Main CI hit a watcher exiting between PID read and signal. | Incident [#1757](https://github.com/mw-ding/mdstack/issues/1757) / [#1761](https://github.com/mw-ding/mdstack/pull/1761) | [test-crew-down.py](../../dev/tests/environments/test-crew-down.py), `StopWatcherRace`: exited watcher counts as stopped; other signal errors still raise. | 1 | #1753 preceded the failure but is test-only, not established escaped-defect source. | applied: narrow ProcessLookupError handling and error-propagation control retained. |
| [#1786](https://github.com/mw-ding/mdstack/issues/1786) `session-triage-fixture-omits-researcher-opt-in` | New zero researcher default rejected NativeTriage before its binding assertion, making CI red. | [#1759](https://github.com/mw-ding/mdstack/pull/1759) / same | [test-crew-poll.py](../../dev/tests/environments/test-crew-poll.py), `NativeTriage`: explicit `researchers = 1`; include dependent poll coverage when session defaults change. | 1 | Intentional no-opt-in refusal remains; no live triage run. | applied: fixture opt-in and dependent-test procedure retained. |
| [#1787](https://github.com/mw-ding/mdstack/issues/1787) `stack-submit-fixture-ignores-lost-ack` | Fake submit-stack returned zero despite configured lost acknowledgement, so the scenario was false. | [#1766](https://github.com/mw-ding/mdstack/pull/1766) / same | [test-crew-land.py](../../dev/tests/environments/test-crew-land.py), `SessionRevisionStackLand.test_lost_acknowledgement_lands_with_exactly_one_request`: fake reads `land-exit.txt`; assert nonzero ack, landed readback and one request. | 1 | Synthetic backend proof, not a live stack land. | applied: configured fake exit and three-member regression retained. |
| [#1788](https://github.com/mw-ding/mdstack/issues/1788) `session-bootstrap-migration-unowned-render` | Documented manual-install migration refused unowned targets and created no install record. | [#1762](https://github.com/mw-ding/mdstack/pull/1762) / same | [Session Upgrading](../runtimes/session.md#upgrading): preserve render/state targets, run release-bundle bootstrap, verify `install.json`, compare backup. | 1 | Session-adoption implementation remains deferred; no fresh migration. | applied: prose only, because operator preservation and comparison depend on live install state; repaired procedure retained. |

## Later occurrences and distinct classes

### Evidence refresh: two incidents

Card #1446 keeps both #1368's config-attribution stderr change and #1527's
coordinator-pointer output change. The [#1368 refresh](https://github.com/mw-ding/mdstack/pull/1368#pullrequestreview-5819777468)
re-captured R1–R5 at the unchanged head; the [#1527 finding](https://github.com/mw-ding/mdstack/pull/1527#pullrequestreview-5831337676)
and [replacement R1](https://github.com/mw-ding/mdstack/pull/1527#pullrequestreview-5831369321)
record the second incident and repair. Multiple merge-up notes or verdicts
about the same mismatch do not add sightings. Retain the existing signed
evidence-only fix route; do not edit an already posted PR body.

### Script help: three incidents

Card #1565 keeps #1528's reflection-measures ([repair](https://github.com/mw-ding/mdstack/pull/1528#pullrequestreview-5826228009)),
PR #1592's run-usage ([repair](https://github.com/mw-ding/mdstack/pull/1592#pullrequestreview-5841237588))
and #1719's check-pr-linkage ([repair](https://github.com/mw-ding/mdstack/pull/1719#pullrequestreview-5868509413)).
Each is one help-formatting failure, including the later occurrences in
the card's comments. #1592's A19 ledger correction is not a fourth help
incident. The existing test-check-repo help-output checks are the retained
prevention; adding another guard is outside L1.

### Shared source is not a duplicate class

Cards #1562's window lengths, #1563's cohort identity and #1564's displayed
coverage remain separate despite sharing #1556. #1561's unknown-value
semantics are separate from #1564's display omission. #1466's synthetic
credential prefix and #1602's error-path disclosure are distinct privacy
mechanisms, neither establishing real secret exposure. #1732's production
pathspec and #1734's test mock share #1703 but have different causes.
Cards #1782's restart eligibility and #1783's shutdown boundary likewise remain
separate findings from #1767.

## Normal-runner discovery retention

For #1696, keep new test classes/cases before the script's `unittest.main()`
invocation. When adding or moving cases, run their file through
`python3 scripts/run-tests.py test-crew-doctor.py` (substitute the changed
file), the normal isolated runner used by CI. Inspect normal-run output and
the discovered-case count to confirm the new cases are included; imported
class selection alone cannot establish script-entrypoint discovery.
The runner suppresses successful file output. For the discovery check,
retrieve its captured transcript through the same isolated `run_one` path:

```sh
python3 - <<'PY'
import runpy
runner = runpy.run_path('scripts/run-tests.py')
path, code, seconds, output = runner['run_one']('dev/tests/environments/test-crew-doctor.py')
print(output, end='')
raise SystemExit(code)
PY
```

Compare the reported test count with the expected cases, including the
three SessionServer cases; a file-level `ok` alone is insufficient.

The repaired doctor file defines `SessionServer` and its three cases before
main. This instruction preserves the card's requested discovery check;
`check-repo.py`'s test-layout check does not enforce that ordering. It is
prose only, because confirming the intended new cases requires comparing
the change with normal-run discovery. This batch adds no discovery guard
and claims no new live owner-shell proof.
