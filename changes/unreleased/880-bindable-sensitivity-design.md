---
type: added
issue: 880
pr: 968
date: 2026-11-05
box-skill: none (reference docs only; no rendered template change)
---

Design note for a bindable sensitivity classifier, marked proposed and not
yet in force. `docs/interfaces.md` sets out an optional `classify` concern
with one operation, `sensitive`: a pack binds its own policy check as an
extension, and without the binding every manifest and profile stays valid
and classification is unchanged. `<op:classify.sensitive>` always renders
the core `scripts/crew-config.py sensitive`, which runs the built-in rules,
then the extension on the same input, and unions the results: an extension
can add matches (prefixed `<pack>:`) but never remove one, and a failed,
timed-out or unreadable extension adds an `errors` line and makes the
change sensitive. `docs/profile.md` adds `errors` to the shared JSON
contract, `docs/packs.md` notes the one token a pack map cannot replace,
and `docs/protocol.md` records the override scope. Slices B1 to B3 (#961
to #963) implement it.
