# M55 learning record

**Last updated:** 2026-11-13

L1 ([#1813](https://github.com/mw-ding/mdstack/issues/1813)) keeps one
milestone-close card as a bounded record. The failure was repaired before
merge. This record changes no product, gate, template or live installation,
and it does not extend the completed [M53 batch](m53-learning.md).

## Reconciliation

- One row, one failure class, one reported occurrence. It counts once,
  however many reviews, comments or triage passes mention it.
- Source and repair are the same PR, so the repair happened before that PR
  merged. This is a near-miss caught by CI, not an escaped defect.
- Retained files were read at builder base
  `d337fd77ab7815a9ac137a8a847fa131523e7329`. The local check-repo run below
  is the only fresh capture. Producer and release test results are as the
  source reports them, not reruns.
- The disposition uses the
  [lesson status vocabulary](../lessons/README.md#status-vocabulary).

## Card

| Card / failure class | Finding and impact | Source / repair PR | Retained prevention | Occurrences | Uncertainty | Disposition |
|---|---|---|---|---|---|---|
| [#1813](https://github.com/mw-ding/mdstack/issues/1813) `personnel-template-placeholder-link` | The personnel source template had a link whose destination held a `<role>` placeholder. The offline links CI job read it as a missing source file and [failed](https://github.com/mw-ding/mdstack/actions/runs/43391407556/job/131771954579). | [#1805](https://github.com/mw-ding/mdstack/pull/1805) / same ([signed CI fix](https://github.com/mw-ding/mdstack/pull/1805#pullrequestreview-5888026687)) | Whole-link composition: [brief.md](../../templates/personnel/brief.md) line 3 carries the text token `{{policy-entry}}`, and [personnel-bundle.py](../../scripts/personnel-bundle.py) line 159 inserts the complete link. Coverage: [test-personnel-bundle.py](../../dev/tests/scripts/test-personnel-bundle.py), `test_fake_host_load_and_idempotency`, resolves every relative link in each emitted brief. [test-release-bundle.py](../../dev/tests/scripts/test-release-bundle.py), `test_current_repo_builds_and_install_cli_runs`, builds the real distribution. | 1 | No fresh offline link run (lychee is not installed locally) and no runtime reproduction. The two test results are reported by the source. | applied: composition and both tests are on `main` at the base above. Not `encoded`; see below. |

## Why not encoded

Status `encoded` needs a check in `scripts/check-repo.py` or lint that
enforces this exact condition. Neither local link guard does.
`check-repo.py`'s `links` check and `release-bundle.py`'s link rewrite both
skip a destination that matches the documented placeholder form `<name>`
(`PLACEHOLDER` in `core/secret-patterns.py`). With the old `<role>`
destination put back into the template at the base above,
`python3 scripts/check-repo.py --only links` printed `check-repo: OK (links)`
and exited 0. The template was then restored. Only CI's offline lychee job
caught the original failure, and it is a workflow job, not a check-repo or
lint rule.

The prevention is therefore the composition rule. A source template that
needs a role-specific link carries a text token, and the producer writes the
whole link. Do not put a `<placeholder>` in a link destination. Keep the
producer test that resolves emitted links, and keep the release build test.

Possible follow-up, outside L1: make the local link guards treat a
placeholder in a link destination the way lychee does, which would let this
condition become `encoded`.
