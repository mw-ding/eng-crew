# Step summary

- Ref: `issue-<n>`
- Run: `<run-id>`
- Started: <UTC timestamp>

## Steps

- **build** · ok · 42s
  > built 3 targets
- **unit-tests** · fail · 3m04s
  > 1 failed: test_x
  > AssertionError: expected 3, got 2
  log: `steps/unit-tests.log`
- **unit-tests (retry)** · ok · 2m58s
  > 120 passed
