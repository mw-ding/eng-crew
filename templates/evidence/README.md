# Evidence adapters

How to capture typed runtime evidence for a PR. The rules (when evidence is
required, who checks it, when the synthesizer may merge) are in the
[verification protocol](../../docs/verification.md). Each adapter here is a
short how-to for the builder and the verifier. They are templates only:
nothing here changes a live routine.

All evidence is committed on the PR branch under `evidence/<pr>/`, so it is in
the head commit (see
[protocol §3](../../docs/protocol.md#3-evidence-requirements)).

| Adapter | Shape | Artifact |
|---|---|---|
| [cli-exit-stdout.md](cli-exit-stdout.md) | CLI (also service and API by command) | A text fixture: command, exit code, stdout, stderr |
| [web-screenshot.md](web-screenshot.md) | Web | A PNG of the changed view at head |

Mobile has no adapter yet (adapter TBD). Add a new adapter as one file here
and one row in the table above.
