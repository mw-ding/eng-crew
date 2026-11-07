# Seat template

An owner-facing seat is a role the owner addresses directly. Each seat here
is an empty placeholder in the role-package shape. Seat content is written
elsewhere and dropped in; this repo only provides the folders.

| Seat | Folder |
|---|---|
| CEO | [ceo/](ceo/SKILL.md) |
| CTO, the technical seat; the engineering team's head maps to it | [cto/](cto/SKILL.md) |
| CPO | [cpo/](cpo/SKILL.md) |
| COO | [coo/](coo/SKILL.md) |
| CDO | [cdo/](cdo/SKILL.md) |
| CFO | [cfo/](cfo/SKILL.md) |

## What to fill in

Each seat folder holds three things.

### `role.toml`

The seat's metadata, as data:

- **Identity defaults:** display name, title and emoji.
- **Class:** `owner-facing`, as opposed to `internal` staff.
- **Authority:** what the seat may decide alone and what it carries to the
  owner.
- **Lifecycle:** how long a session of the seat lives.
- **Skill index:** the skills under `skills/` the seat loads.
- **Team:** the team the seat heads, if any.

The registry does not read seat packages yet; it reads `roles/eng/` only.
Match the key names of the role registry when it does.

### `SKILL.md`

The seat's entry skill, in the Agent Skills format. Keep the front matter
(`name`, `description`) and replace the body with who the seat is, what it
owns, its procedures, what it refuses and whom it hands off to. Write it
once, with no runtime-specific operating text: the same file must work
unchanged in every environment and harness.

### `skills/`

One `skills/<skill>/SKILL.md` per procedure, each with the same front
matter. Delete `skills/.gitkeep` once the first skill lands.

## Rules

- No personal data: no names of real people, contacts, accounts, internal
  tool names or credentials. Seat files are public.
- Reference only `roles/`, `protocols/` and `actions/`; the repo lint fails
  a seat file that names another module or a runtime word.
