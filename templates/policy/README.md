# Role policy fragments

Role policy shared by more than one runtime template, authored once (#1184).
A runtime template pulls a fragment in with a line exactly
`<include:policy/<dir>/<name>.md>`; the [renderer](../../scripts/README.md#renderer)
replaces that line with the fragment, whose lines then render like the
including file's. Nothing here renders on its own.

- `<dir>` is the role the policy belongs to, or `shared` for text more than
  one role carries.
- A fragment holds role policy only. Wake, delivery, worktree and
  runtime-specific operating text stays in the runtime template.
- Backend operations stay `<op:…>` tokens. Gates stay owned by
  [the protocol](../../docs/protocol.md); a fragment restates them, never
  defines or relaxes one.
- One level: a fragment cannot include another fragment.
- Each role directory is an Agent Skills skill (#1221,
  [team spec](../../docs/specs/team.md) REQ-04): an entry `SKILL.md` names
  the role-wide fragments, and one `skills/<skill>/SKILL.md` per procedure
  names the fragments it is made of. Skill files have `name` and
  `description` front matter, never render, and add no rule.
- Edit a fragment and every runtime template that includes it changes. Run
  the render and parity tests (`test-crew-render.py`, `test-render-parity.py`,
  `test-tmux-briefs.py`, `test-crew-bootstrap.py`) after any edit.
