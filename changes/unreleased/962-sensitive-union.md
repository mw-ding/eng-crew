---
type: added
issue: 962
pr: TBD
date: 2026-11-05
box-skill: none (scripts and reference docs; no rendered template change)
---

`scripts/crew-config.py sensitive` runs a bound `classify.sensitive`
extension beside the built-in rules (#880 slice B2). The extension reads
the same stdin and its matches and content records are added, rule names
prefixed `<pack>:`; it can never clear a built-in match. A nonzero exit, a
timeout (120 s) or output that breaks the shared JSON contract adds a line
to a new `errors` field and makes the result `crew:sensitive`, exit 0.
`errors` appears only with an extension bound. Without one, output and exit
codes are unchanged.
