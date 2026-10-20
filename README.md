# eng-crew

Versioned, reviewed source of truth for the **engineering-bot crew framework**:
how a crew of bots (coordinator, builder, reviewer-validator, synthesizer,
researcher) runs a GitHub repo's spec → build → CI → review → validation → merge
loop, and how each bot is wired to GitHub.

The repo is iterated on as the crew learns. Content is built by the crew itself
through the normal PR pipeline; every change is recorded in `CHANGELOG.md`.

![eng-crew collaboration flow](docs/diagrams/eng-crew-flow.png)

*Crew collaboration flow.* Editable source:
[eng-crew-flow.excalidraw](docs/diagrams/eng-crew-flow.excalidraw)
(see [docs/diagrams/README.md](docs/diagrams/README.md)).

- Spec: [docs/specs/framework.md](docs/specs/framework.md)
- No secrets or tokens are ever committed here. Per-repo specifics are templates
  with placeholders.
