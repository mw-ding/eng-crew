---
type: added
issue: 1229
pr: 1277
date: 2026-11-07
box-skill: none
---

A first `knowledge` connector: Notion. The actions contract gains A21 `knowledge-read` and A22 `knowledge-propose-edit`, and `connectors/notion/knowledge.py` implements both under the CLI contract (one JSON envelope, exit code as outcome). `knowledge-read` writes a page's title and top-level blocks as plain text to a local file that git ignores; `knowledge-propose-edit` posts the proposal as a page comment and never edits the page; the comment names the idempotency key, and a private key ledger (`CREW_KNOWLEDGE_KEYS`, digests and comment ids only) plus a read-back of the page's open comments make a retry with the same key and inputs return the earlier comment instead of posting again, even after the owner resolves it. A role reaches only the sources its definition lists in the new optional `knowledge` key of `roles/<domain>/<role>.toml`. Page pointers and the token come only from the install's private config (`CREW_KNOWLEDGE_CONFIG`, default `~/.config/eng-crew/knowledge.toml`, which names the token's environment variable); a config tracked by git is refused, and `.gitignore` ignores `knowledge.toml`. A connector manifest may now declare the `knowledge` concern alone. See `docs/backends/notion.md`.
