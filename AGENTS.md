# AGENTS.md

Thin project guide for agents working on eng-crew. This repo is a framework
of docs, templates and small guard scripts, so most review is about wording.
Keep effort proportional. Read this file before building or reviewing.

## Map

- [docs/README.md](docs/README.md): index of every doc.
- [docs/concepts.md](docs/concepts.md): glossary of abstract protocol terms,
  mapped to GitHub and Grok Bot.
- [docs/protocol.md](docs/protocol.md): stages, markers, rounds, merge gate
  (stage 7).
- [docs/roles.md](docs/roles.md): roles, tiers, engines, worker brief and PR
  templates.
- [docs/verification.md](docs/verification.md): typed runtime evidence per
  shape and the role duties.
- [templates/README.md](templates/README.md): routine and listener templates.
- [docs/lessons/README.md](docs/lessons/README.md): lessons log.
- [docs/findings/README.md](docs/findings/README.md): findings buffer for
  repeated small smells.
- [CONTRIBUTING.md](CONTRIBUTING.md): how to iterate on the framework.

## Build posture

- Do what the acceptance criteria (ACs) say. Keep scope tight.
- Do not gold-plate: no extra features, rewrites or edge-case hardening
  beyond the ACs. Note worthwhile extras in the PR as follow-ups.
- Run the checks CI runs before pushing, and add a CHANGELOG entry.
- Direction rule: packs reference eng-crew; eng-crew never references an
  external pack or names an org's internal tools ([docs/packs.md](docs/packs.md)).

## Review posture

Keep review thin. Spend rounds on what can break the pipeline.

Blocking (red) only when:

- an acceptance criterion fails;
- the stage 7 merge gate in [docs/protocol.md](docs/protocol.md) would merge
  something wrong;
- CI fails;
- there is a security or secret issue.

Non-blocking (yellow, follow-up, do not request changes for these):

- CHANGELOG wording and non-normative prose;
- template phrasing that does not change gate behaviour;
- adversarial script edge cases beyond the ACs. Defer them to the next
  milestone, unless an AC says the script must fail closed.

Bright line for the reviewer-validator: if wording would make a stage 7 rule
or a `pass=verdict` / `pass=ack` marker rule fire wrong, it is still red,
however small the edit.

This posture changes no merge gate, round cap or standing merge-ok.
