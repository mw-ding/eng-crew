# Evidence adapters

How to capture typed runtime evidence for a PR. The rules (when evidence is
required, who checks it, when the synthesizer may merge) are in the
[verification protocol](../../docs/verification.md). Each adapter here is a
short how-to for the builder and the verifier. They are templates only:
nothing here changes a live routine.

Adapters emit inline snippets for the body or signed reviews. No evidence
is committed to the repo (see
[protocol §3](../../docs/protocol.md#3-evidence-requirements)).

| Adapter | Shape | Artifact |
|---|---|---|
| [cli-exit-stdout.md](cli-exit-stdout.md) | CLI (also service and API by command) | A copyable command/output pair: exit code, stdout, stderr |
| [cli-exit-stdout.md#negative-control](cli-exit-stdout.md#negative-control) | Negative control for a new or changed guard (any shape) | A fail-then-pass pair: the guard failing on a mutated copy (N1), then passing at head (N2) |
| [web-screenshot.md](web-screenshot.md) | Web | An embedded GitHub attachment of the view, or capture recipe plus validator reproduction |

Mobile has no adapter yet (adapter TBD). Add a new adapter as one file here
and one row in the table above.
