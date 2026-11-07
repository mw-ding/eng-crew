"""OpenCode adapter (docs/runtimes/harness-adapters.md#opencode-opencode): a tier-order and pack-capability engine
with no interactive launch, so crew spawn skips it and it is no coordinator choice. Its non-interactive review
command is in roles.md."""

EXECUTABLE = "opencode"
TITLE = "OpenCode"
ENGINE_RANK = 3
LOGIN_STATUS = ["auth", "status"]
