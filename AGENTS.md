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
- Add a CHANGELOG entry. Before pushing, run a targeted local set, not the
  full suite: `scripts/check-repo.py` (its `markdown` check runs
  `check-markdown.py`, local markdownlint parity) and
  `scripts/check-changelog-pr.py` always; the `scripts/test-*.py` named for
  each changed script; render and parity tests (`test-crew-render.py`,
  `test-render-parity.py`, `test-tmux-briefs.py`, `test-crew-bootstrap.py`)
  when templates or fixtures change; release and
  changelog tests (`test-changelog-cut.py`, `test-check-changelog-pr.py`,
  `test-release-*.py`) for a release cut. This is the reviewer-validator's
  selection rule ([docs/verification.md](docs/verification.md)).
- A diff touching shared plumbing (`scripts/crew.d/_shared.py`,
  `scripts/crew`, `scripts/crew-config.py` or `scripts/crew-render.py`) runs
  every `scripts/test-*.py` locally, with the parallel runner once it exists.
- The PR Testing section lists the targeted set, why it covers the diff, and
  that PR CI runs the full suite. Red CI still returns to the builder as a
  ci-red round; CI is never waived.
- Merge-ups (a push whose only new commit merges the default branch) run
  `scripts/check-repo.py` and only the `scripts/test-*.py` that cover the
  conflicted files (the test named for a changed script; render and parity tests
  when templates or fixtures conflicted). PR CI and the recheck pass cover the
  rest. The merge-up note lists the tests run and why that set covers the
  conflict.
- Never download or install a binary from the internet, bypass OS code-signing
  or quarantine, or use an alternate or mirror package registry. If a CI tool
  is missing or its registry fails, skip that one local check, say so in the PR
  evidence, and leave it to CI.
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
