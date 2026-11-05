# Project doc set

Reference module for the docs of the projects a crew works on, split out of
the [project docs consolidation design](project-docs.md) under the M26
modular organization principle
([#1024](https://github.com/mw-ding/eng-crew/issues/1024)): the essential
doc set every crew-run project should have and the status banner a design
doc carries. The profile's [`[docs]`](profile.md#docs) table maps a
project's homes; the docs pass that checks them stays in the design.

## Essential doc set

Every crew-run project should have these five docs. The canonical home is
a default; a project with an existing home for one maps it in the profile
(`[docs] homes`, [profile](profile.md#docs)) instead of moving it.

| Doc | Purpose | Default home | Kind |
|---|---|---|---|
| Overview | What the project is, who it serves, how to get started, links to the rest | `README.md` | reference |
| Agent guide | What a crew role needs to build and review here: build and test commands, the local check set, review posture, crew profile notes | `AGENTS.md` | rule |
| Architecture | Components, boundaries, data flow and where each lives in the tree | `docs/architecture.md` | reference |
| Runbook | How to run, deploy, operate and recover the project | `docs/runbook.md` | reference |
| Decisions | Dated decisions with their reasons and rejected options, newest first; each design doc's decision links here | `docs/decisions.md` | history |

- **Agent guide.** The file the builder brief already reads ("Read the
  repo's `AGENTS.md`", [roles](roles.md)). Its **crew profile notes** say
  what the crew must know about this project and the profile can't express:
  which paths are sensitive and why, the flavor and its reason, owner rules
  specific to the repo, and which docs a role reads at start. It links to
  `crew.toml` for values and never restates them.
- **Docs index.** A project with more than five docs under `docs/` also keeps
  `docs/README.md`: one row per doc with its purpose and kind, in the shape of
  [eng-crew's index](README.md#available-now).
- **Small projects.** A section of `README.md` may be the home of the
  architecture, runbook or decisions doc while it stays under about 100 lines;
  the profile maps it to `README.md#<anchor>`.
- **Not essential.** API references, changelogs, contributor guides and
  design docs are kept when a project has them; the pass checks their banners
  and links but never reports them missing.

## Status banners

A design doc in a target project states its lifecycle right under its H1,
in the shape of [principle 3](README.md#documentation-principles) and
[triage.md](triage.md):

```markdown
# <Title>

> - **Status:** design | partly built | built | superseded
> - **Applies to:** <scope>
> - **Current rules:** <links to the docs that own the live rules>
> - **Built:** <issues or PRs, or "nothing">
> - **Last checked:** <YYYY-MM-DD> at `<sha7>`
```

- `superseded` names its successor in **Current rules**.
- Kind (rule, reference, design, history) stays in the index, not the banner.
- Only design docs carry a banner. A rule or reference doc is live by
  definition; a history doc is dated by its title or first line.
