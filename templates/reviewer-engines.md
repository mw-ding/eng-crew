# Reviewer engine choice (template)

Copy to `<state-dir>/<owner>__<repo>/reviewer-engines.md`. The reviewer bot
reads it fresh on every run, and only the reviewer's main chat edits it.
Engine names and quota rules below are examples; the live choice follows the
roles skill and the current quota steer from `<CoordinatorBot>`.

Updated: `<date>`, per `<reason, for example a quota steer>`.

## Hard rules

- The reviewer engine must differ from the builder engine. Read the builder
  engine from the builder marker in the PR body, or its signature.
- Eng workers never use Cursor CLI.
- Private repos: never use engines whose terms allow training on inputs.
- Skip pay-per-use providers unless every subscription ahead is exhausted.

## Choice table

| Builder engine | Reviewer engine (first) | Fallback |
|---|---|---|
| Codex, or unknown non-Claude | Claude Code, high effort | `<second engine>` at its highest effort |
| Claude Code (any model) | Codex read-only sandbox, high effort | `<second engine>`; do not wait for a rate limit to clear |

## Passes

- The validation pass uses the same engine family as the review pass, but a
  fresh session that has not seen the review output.
- Small merge-up or docs-only re-checks get one light pass to save quota.
- Quota steers from the coordinator override the first choice for their stated
  window. Record the window here, and revert when it ends. Record percentages
  only as rounded, account-free hints.
