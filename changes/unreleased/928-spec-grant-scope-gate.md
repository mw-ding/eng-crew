---
type: added
issue: 928
pr: TBD
date: 2026-11-04
box-skill: deferred to #140
---

The #398 spec grant scope is in effect. A spec change is one carrying
`crew:spec` or with any changed path, both rename paths, matching
`spec.paths` (default `docs/specs/**`). `crew train check` and
`crew train land` now classify every member this way, including ordinary
crew-lane changes: a spec change needs the owner's merge-ok at head unless
`runtime.options.merge_grant_scope` lists `spec` beside a standing
`merge_grant`, and an unreadable path set blocks. Sensitive spec changes and
open rereviews stay excluded. A merge record that used the grant for a spec
change names the grant and says it covered a spec change. The tmux
synthesizer brief renders `<merge-grant-scope>` and `<spec-paths>`. With
neither key set, a labelled or `docs/specs/` change needs merge-ok as the
protocol already required, and non-spec records are unchanged.
