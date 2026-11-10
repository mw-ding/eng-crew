Usage line (`<mdstack>/docs/roles.md`, Usage line): every post that reports
a pass (build, fix, ci-fix, review, validate, recheck, verdict, merge,
report, status) ends with one line just above its marker and signature, as
printed by `python3 <mdstack>/scripts/run-usage.py --run "$CREW_STATE/runs/$CREW_ID.json"`.
Without a run record pass `--engine <engine> --dir "$PWD" --start <UTC time
the pass began>` instead. Paste it as printed, for example
`Run: 23m 10s · 1.24M in (1.1M cached) / 38.2k out · claude-opus-5-5 (high)`;
`tokens n/a` stays as is, never an estimate. It is informational only: no
gate, verdict, flavor or scheduler decision reads it, and it changes no
marker, signature or effort attribution.
