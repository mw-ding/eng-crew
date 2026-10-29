# Evidence for PR 84

Shape: CLI ([adapter](../../templates/evidence/cli-exit-stdout.md)). The change
under test is `scripts/check-repo.py --only shapes`.

- `check-shapes-pass.txt`: the real repo at the PR head passes, exit 0.
- `check-shapes-fail.txt`: a scratch copy of `docs/verification.md` with the
  Mobile row wrapped in an HTML comment fails, exit 1. `<scratch>` stands for
  the scratch directory.

To re-run the failing case, copy `docs/verification.md` into
`<scratch>/docs/`, wrap the `| Mobile |` line in `<!-- ... -->`, and run the
command recorded in the fixture.
