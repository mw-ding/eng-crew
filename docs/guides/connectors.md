# Configuring connectors

A connector reaches one tool of record for one or more concerns
([connectors module](../../connectors/README.md)). This guide shows how to
pick connectors in a profile and how to set up the knowledge connector,
which keeps private pointers and secrets out of git. It is navigation only:
[profile.md](../profile.md), [interfaces.md](../interfaces.md) and each
backend doc own the rules.

## Pick a connector per concern

The profile names one connector for each core concern: change, review,
tracker, state tags, markers, CI, events and owner channel. The default
profile picks `github` for all eight, so a GitHub repo needs no
`[backends]` table. To set them explicitly, or to override a declared
capability:

```toml
[backends.change]
name = "github"
[backends.review]
name = "github"
capabilities = { post-verdict = "emulated (COMMENT-review verdict + recorded owner merge-ok)" }
```

The concerns and operation keys are in the
[`[backends.<concern>]` keys](../profile.md#backendsconcern). Each connector declares what it can
do in `connectors/<name>/manifest.toml`. `resolve` folds that declaration in
under your overrides and fails closed when a combination cannot keep an
invariant ([capability declaration](../interfaces.md#capability-declaration)).
Check the result:

```sh
python3 core/crew-config.py validate ~/.mdstack/config.toml
python3 core/crew-config.py resolve --project ~/.mdstack/config.toml
```

A connector that is not built in comes from a pack: name it in
`backends.<concern>.name` once the pack is wired
([pack author guide](pack-authoring.md)). The GitHub operation mapping is in
[backends/github.md](../backends/github.md).

## Add a knowledge source

The knowledge concern reaches the owner's notes service, such as a second
brain kept in Notion ([knowledge concern](../interfaces.md#knowledge)).
Knowledge is context only: no gate, verdict or marker reads it. No profile
binds it. It needs three pieces, and only the first is in git.

1. **The role names the source.** In the role's definition,
   `roles/<domain>/<role>.toml`, list the source by name:

   ```toml
   knowledge = ["second-brain"]
   ```

   A name is all the repo holds. A role without the name is refused with
   `no-authority` before any request
   ([role registry](../roles-registry.md#schema)).

2. **The install's private config maps the name.** Write
   `~/.config/eng-crew/knowledge.toml`, or a file that `CREW_KNOWLEDGE_CONFIG`
   names, outside every repo:

   ```toml
   [sources.second-brain]
   backend = "notion"
   page = "<32-hex Notion page ID>"
   token_env = "NOTION_TOKEN"
   ```

   The page pointer lives here, never in the profile or a committed file.
   A config that git tracks is refused (`committed-config`), and the repo's
   `.gitignore` ignores `knowledge.toml`.

3. **The token stays in the environment.** `token_env` names the variable
   that holds the integration token; the token itself is never written to a
   file. Export it in the shell that starts the crew, and share the page with
   the integration in Notion. The integration needs the read content, read
   comments and insert comments capabilities.

Then check the source from the repo:

```sh
python3 connectors/notion/knowledge.py knowledge-read \
  --role <role> --source second-brain --out .crew/brain.md --json
```

The output file must be outside any git work tree or ignored by git (bootstrap
adds `.crew/` to `.git/info/exclude`). A role proposes changes to a page as a comment and never edits
it (`knowledge-propose-edit`). Reason codes, idempotency and the key ledger
are in the [Notion backend](../backends/notion.md).

## Where personal data goes

Core memory in git (`memory/owner.md`, `memory/roles/<role>.md`) refuses
personal data and routes it to the knowledge connector
([core memory](../memory.md)). If a lint run rejects a memory line, move that
fact to the knowledge source instead.
