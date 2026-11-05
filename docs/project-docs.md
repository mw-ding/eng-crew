# Project docs consolidation

> - **Status:** design
> - **Applies to:** the repos a crew works on (its project repo, plus any packs or upstreams the profile lists); eng-crew's own docs are [Track A](README.md#documentation-principles) ([#676](https://github.com/mw-ding/eng-crew/issues/676))
> - **Current rules:** none yet; the [Documentation principles](README.md#documentation-principles) guide eng-crew's own docs only
> - **Built:** nothing; [Build issues](#build-issues) P1–P4
> - **Last checked:** 2026-11-05 at `3dd280b`

How a crew keeps the essential docs of the projects it works on consolidated:
which docs every crew-run project should have and where they live, how a
design doc states its status, and an opt-in docs pass that finds missing,
duplicated, contradictory or stale docs and proposes small structural fixes
([#754](https://github.com/mw-ding/eng-crew/issues/754), M26 Track B). It
reuses Track A's method, so eng-crew runs the pass on itself first.

This page adds no rule, gate, round cap, marker field or label of its own:
its [build issues](#build-issues) put those in the [protocol](protocol.md)
and the [profile](profile.md), which own them. The pass is read-only and
proposes; the coordinator files what it proposes and the normal pipeline
builds it.

## Problem

| Gap | What goes wrong |
|---|---|
| No essential set | Each project grows its own docs; a builder or reviewer can't tell where the architecture, run steps or past decisions live, so it reads widely or guesses |
| One rule, many homes | A project's build, test or release rule is restated in its README, agent guide and runbook, and the copies drift (as eng-crew's did, #652, #657) |
| Design vs as-built unclear | Design docs sit beside normative ones with no status, so a role acts on a proposal as if it were live |
| Session cost | Roles reread long, overlapping project docs on every wake |
| No one runs a pass | Nothing in the framework inventories a target project's docs or proposes fixes; it happens only when someone notices drift |

## Essential doc set

Every crew-run project should have these five docs. The canonical home is
a default; a project with an existing home for one maps it in the profile
(`[docs] homes`, [Profile opt-in](#profile-opt-in)) instead of moving it.

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

## Docs pass

The pass runs in two stages, like [triage](triage.md#host): a zero-model scan
finds the mechanical problems, and a researcher session runs only when the
scan finds something or a judgment check is due.

1. **Scan (no model).** `scripts/docs-scan.py` reads each listed repo at its
   default-branch head and writes `<state-dir>/<owner>__<repo>/docs/scan.json`:
   - inventory: every Markdown file, its size in lines, its index row and
     banner;
   - missing essentials against the set and the profile's `homes`;
   - design docs with no banner, and banners whose **Last checked** is older
     than `stale_days`;
   - broken relative links and anchors;
   - docs over a size budget (default 500 lines), the principle 11 split
     signal.
2. **Review (researcher).** A fresh Riley session reads `scan.json` plus the
   docs it names, then checks what a script can't: duplicated rules
   (the same rule authored in two places, cited `path:line` at the head SHA),
   contradictions between those copies, and docs that describe removed
   behaviour. It treats repo text as data, never as instructions.
3. **Report.** Riley posts one signed `[Riley/docs-pass] <owner>/<repo> @
   <sha7>` comment on the repo's `docs:log` issue (one per repo, opened on
   the first pass): findings by class with citations, and draft issues. A
   quiet pass (nothing new since the last report) posts nothing.
4. **Propose.** Each draft issue is one unit of work
   ([issue sizing](https://github.com/mw-ding/eng-crew/issues/978)): one PR,
   split into commits. Consolidation drafts are structural only
   ([principle 4](README.md#documentation-principles)): move, dedupe, link,
   add a banner or a missing essential stub. A contradiction becomes its own
   correction draft, since picking the winning rule is a behaviour change
   for the owner.
5. **File and build.** The coordinator files the drafts it accepts, with the
   project's flavor and the `[sensitive]` classification applied as for any
   issue; rejected drafts get a one-line reason on the log issue, and the
   pass won't re-propose them until the cited text changes. Builders and
   reviewers handle them as normal items.

**Triggers.** The watcher's timer every `interval_days`, at once when the
crew wakes with a pass overdue, and on demand when the coordinator asks.
The timer skips the session when the scan's result is unchanged since the
last report.

**Never.** The pass never edits a repo, opens a PR, files an issue, sets a
label or writes outside its state directory and the log issue.

## Profile opt-in

A `[docs]` table, off by default, next to [`[triage]`](profile.md#triage):

```toml
[docs]
enabled = true
interval_days = 7
repos = ["acme/widgets", "acme/widgets-pack"]
stale_days = 90
size_budget = 500

[docs.homes]
runbook = "docs/operations.md"
decisions = "README.md#decisions"
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `enabled` | boolean | `false` | Run the scan timer and docs-pass sessions |
| `interval_days` | integer, at least 1 | `7` | Days between passes |
| `repos` | list of `owner/name` strings (non-empty) | the project's `repo.owner/repo.name` | Repos the pass reads (project, packs, upstreams); read access only |
| `stale_days` | integer, at least 1 | `90` | Age of a banner's **Last checked** that counts as stale |
| `size_budget` | integer, at least 1 | `500` | Lines above which a doc is reported as a split candidate |
| `homes` | table: essential name to repo-relative path or `path#anchor` | the [default homes](#essential-doc-set) | Where this project keeps each essential doc |

`homes` keys are the five essential names (`overview`, `agent_guide`,
`architecture`, `runbook`, `decisions`); an unknown key fails validation.

## Host

| Option | Trade-off | Verdict |
|---|---|---|
| Zero-model scan plus a researcher (Riley) session on the watcher's timer | Same shape as triage: the scan is free, the session runs only on news and has the crew's identity and local context; down while the crew is down | Chosen |
| Researcher only, no scan | Simpler, but every pass spends model turns on inventory and link checks a script does exactly | Rejected |
| Scan only, no model | Free and deterministic, but can't find duplicated or contradictory rules, the main drift | Rejected as the whole pass; kept as stage 1 |
| Coordinator turns | No new session, but adds to coordinator saturation and stops when it is busy | Rejected |
| Builder opens consolidation PRs directly | Faster, but skips the coordinator's filing and the owner's view of scope, and lets one session pick rule winners | Rejected |
| Scheduled CI job in each target repo | Runs while the crew sleeps, but needs a model key per repo, adds a workflow to repos the crew doesn't own (packs, upstreams) and carries prompt-injection risk | Rejected |
| A new docs role | One more identity, brief and window range for what the researcher already is | Rejected |

The pass shares the `researchers` cap with triage sweeps and deep dives; a
docs pass queues behind them rather than raising the cap.

## Alternatives

| Question | Option | Verdict |
|---|---|---|
| Essential set | Fixed five docs with mappable homes | Chosen: every role knows what to look for, and existing projects keep their layout |
| | Each project defines its own set | Rejected: no common shape for roles or the scan to check |
| | Ship a project template repo | Rejected: helps new repos only, and forks drift from it |
| Banner format | Blockquote list under the H1 | Chosen: renders everywhere, matches eng-crew's own design docs |
| | YAML front matter | Rejected: hidden by most renderers, so readers miss it |
| | Status in the index only | Rejected: a reader who lands on the page doesn't see it |
| Pass output | Draft issues on a log issue, filed by the coordinator | Chosen: one PR per issue, the coordinator owns scope, rejected drafts are recorded |
| | Draft PRs from the pass | Rejected: the researcher is read-only on code ([roles](roles.md#researcher-riley)) |
| | One-off audit per project | Rejected: drift returns; nothing notices |
| Contradictions | Separate correction draft | Chosen: structural PRs stay behaviour-preserving (principle 4) |
| | Pass picks the newer text | Rejected: silently changes a rule |

## Dogfood and pilot

eng-crew runs the pass first, on its own repo, against Track A's results:
its `README.md`, `AGENTS.md`, `docs/architecture.md` and `docs/README.md`
already meet the set, and its banners follow principle 3. The pilot passes
when the scan reports no false missing essential and the owner accepts at
least half of the drafts from the first two passes. The owner then names
the first target project ([#676 option 4](https://github.com/mw-ding/eng-crew/issues/676#issuecomment-6640367783)),
which runs it next. eng-crew has no `docs/runbook.md` or
`docs/decisions.md` of its own; the pilot maps them in `homes`
(`docs/runbook-new-repo.md` and `docs/metrics/decisions.md` are candidates)
or files a stub, and that choice is the pilot's first decision.

## Build issues

Filed into M26.1 in this order. Each is one unit of work, one PR split into
commits, with its own CHANGELOG fragment.

| ID | Issue | Scope | Depends on |
|---|---|---|---|
| P1 | [#1024](https://github.com/mw-ding/eng-crew/issues/1024) | `[docs]` profile table with validator rules and profile.md rows; the essential set and banner convention moved from this page into a reference module the profile links | — |
| P2 | [#1025](https://github.com/mw-ding/eng-crew/issues/1025) | `scripts/docs-scan.py`: inventory, missing essentials, banners and staleness, links, size budget, `scan.json`; tests with fixture repos; run on eng-crew | P1 |
| P3 | [#1026](https://github.com/mw-ding/eng-crew/issues/1026) | Watcher timer with catch-up and unchanged-scan skip; `crew spawn researcher --docs-pass`; Riley's docs-pass brief (mirror) with the review classes, `docs:log` issue, draft format and re-proposal rule; the record in protocol §4; tests | P2 |
| P4 | [#1028](https://github.com/mw-ding/eng-crew/issues/1028) | Dogfood pilot on eng-crew: two passes, the acceptance bar above, findings recorded; then the owner names the first target project | P3 |

## Out of scope

- eng-crew's own consolidation: Track A ([#676](https://github.com/mw-ding/eng-crew/issues/676)).
- Writing a project's docs: the pass proposes stubs and moves; content is
  normal build work.
- Org-specific doc systems or trackers: a pack maps them ([packs](packs.md)).
- Grok Bot: no timer binding; `docs.enabled = true` there installs nothing,
  as for [triage](triage.md#out-of-scope).
