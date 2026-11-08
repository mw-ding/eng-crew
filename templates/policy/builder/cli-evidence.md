CLI evidence: CLI, service and API proof must come from
`<mdstack>/scripts/evidence-cli.py` or the `templates/evidence/cli-exit-stdout.md`
script, run at the clean head and pasted verbatim with its header; never
hand-write, paraphrase or re-split a capture. Put any fake or temp repo in a
`--setup` file so the `sh` block is executable. Deferred AC evidence (CI runs,
timings) goes in a signed fix review before the next review.
