# Reviewer engine choice (template)

Copy to `<state-dir>/<owner>__<repo>/reviewer-engines.md`. The reviewer bot
reads it fresh on every run, and only the reviewer's main chat edits it.
Engine names and quota rules below are examples; the live choice follows the
roles skill and the current quota steer from `<CoordinatorBot>`.

Updated: `<date>`, per `<reason>`.

## Hard rules

- The reviewer engine must differ from the builder engine. The builder engine
  is the engine that actually wrote the latest round. The latest fix note or
  commit trailer wins over the PR-body builder marker or signature when they
  disagree. A manual merge-up commit with no engine does not count. Three
  places name the engine, with model and effort: the fix note (initial
  build: the PR signature), the `Engine:` trailer on every commit of the
  round, and the round's builder marker (the initial build's PR-body marker
  names engine and model only; effort is in the signature and the trailers).
  If the builder marker and the fix note or commit trailer disagree on the
  engine, the note or trailer wins, and before merge the reviewer re-checks
  at head (fresh review + validation) on an engine different from the actual
  builder engine.
- Eng workers never use Cursor CLI or grok.
- Private repos use only Claude Code or Codex: no Muse Code, no OpenRouter, no
  other third-party or pay-per-use provider, and never an engine whose terms
  allow training on inputs.
- If no allowed engine has quota, stop, claim nothing and hand off the blocker
  with the reset time. Do not fall back outside the allowed set.

## Choice table

| Builder engine | Reviewer engine (first) | Fallback |
|---|---|---|
| Codex | Claude Code, high effort | `<fallback-engine>` from the allowed set, highest effort |
| Claude Code (any model) | Codex read-only sandbox, high effort | `<fallback-engine>` from the allowed set; do not wait for a rate limit to clear |

## Passes

- The validation pass uses the same engine family as the review pass, but a
  fresh session that has not seen the review output.
- Small docs-only re-checks get one light pass to save quota. The light
  re-check still keeps review and validation as separate, independent passes.
  A head that only merges `<default-branch>` in is handled by the merge-up rule
  in [reviewer-v2-watch.md](reviewer-v2-watch.md) (re-approve after an approval,
  ack after changes).
- Quota steers from the coordinator override the first choice for their stated
  window. Record the window here, and revert when it ends. Record percentages
  only as rounded, account-free hints.

The engine rules are summarized in [../../../docs/protocol.md](../../../docs/protocol.md);
this file is the per-repo state template.
