# eng-crew

Versioned, reviewed source of truth for the **engineering-bot crew framework**:
how a crew of bots (coordinator, builder, reviewer-validator, synthesizer,
researcher) runs a GitHub repo's spec → build → CI → review → validation → merge
loop, and how each bot is wired to GitHub.

## Status / v1 cut

- **v1 cut: M1–M12 closed** (harness loop through the `AGENTS.md` thin review
  posture), locked 2026-10-29.
- **In cut:** the crew framework docs, skills and templates as of `main` at
  the current HEAD. See [CHANGELOG.md](CHANGELOG.md) and the
  [closed milestones](https://github.com/mw-ding/eng-crew/milestones?state=closed).
- **Out of cut / held:** the Sam-only merge ruleset
  ([#80](https://github.com/mw-ding/eng-crew/issues/80), needs GitHub Pro or an
  App; stays on `crew:hold`), and the product prove-it apps (they live
  elsewhere, not in eng-crew).
- **Canonical heading:** the
  [Personal AI swarm harness brief](https://www.notion.so/408223c9b3db81809f9bfe3985251c8b)
  is the gap-table north star. It is not a second source of truth for protocol
  text: the repo docs win for normative crew rules.

Content is built by the crew itself through the normal PR pipeline; every
change is recorded in `CHANGELOG.md`.

![eng-crew collaboration flow](docs/diagrams/eng-crew-flow.png)

*Crew collaboration flow.* Editable source:
[eng-crew-flow.excalidraw](docs/diagrams/eng-crew-flow.excalidraw)
(see [docs/diagrams/README.md](docs/diagrams/README.md)).

- Spec: [docs/specs/framework.md](docs/specs/framework.md)
- Lessons log: [docs/lessons/](docs/lessons/README.md)
- Changes: [CHANGELOG.md](CHANGELOG.md) · Process: [CONTRIBUTING.md](CONTRIBUTING.md)
- No secrets or tokens are ever committed here. Per-repo specifics are templates
  with placeholders.
