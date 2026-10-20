# agentconnect reviewer engine steer (worked example)

Worked example of a filled-in reviewer engine file, as of Oct 19, 2026. The
template is [../../templates/reviewer-engines.md](../../templates/reviewer-engines.md).

Updated Oct 19, 2026 after the coordinator's quota steer: the Codex weekly
allowance was partly used until Oct 24, while Claude Code had plenty of room.

Hard rule: the reviewer engine must differ from the builder engine (read the
builder marker or signature). Never Cursor or grok. Skip OpenRouter and
DeepSeek.

- Builder = Codex, or unknown or other non-Claude: Claude Code Opus at high
  effort. Fallback: Muse Code at its highest reasoning effort (public repo
  only; agentconnect is public).
- Builder = Claude Code (any model): Codex in a read-only sandbox, high effort.
  Fallback when Codex is rate-limited: Muse Code. Do not wait (coordinator
  steer, Oct 19, 2026).
- The validation pass uses the same engine family as the review pass, but a
  fresh session that has not seen the review output.
- Small merge-up or docs-only re-checks: one light pass, to save quota.
