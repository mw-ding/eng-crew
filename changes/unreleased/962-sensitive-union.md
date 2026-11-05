---
type: added
issue: 962
pr: TBD
date: 2026-11-05
box-skill: deferred to #140 (protocol Sensitive class wording; rendered briefs byte-identical)
---

`scripts/crew-config.py sensitive` runs a bound `classify.sensitive`
extension beside the built-in rules (#880 slice B2). The extension reads
the same stdin and its matches and content records are added, rule names
prefixed `<pack>:`; it can never clear a built-in match. A nonzero exit, a
timeout (120 s) or output that breaks the shared JSON contract adds a line
to a new `errors` field and makes the result `crew:sensitive`, exit 0.
`errors` appears only with an extension bound. Without one, output and exit
codes are unchanged. The tmux and Grok Bot briefs now reach the classifier
through `<op:classify.sensitive>`, which always renders the core command, so
a pack binding never replaces the built-in run and the default render is
byte-identical (#880 slice B3); the protocol's Sensitive class wording for
extensions is in force.
