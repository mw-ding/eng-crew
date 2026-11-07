#!/usr/bin/env python3
"""Notion knowledge connector (#1229): the actions/ binding for knowledge-read and knowledge-propose-edit.

Usage: knowledge.py --capabilities [--json]
       knowledge.py knowledge-read --role ROLE --source NAME --out PATH [common flags] [--json]
       knowledge.py knowledge-propose-edit --role ROLE --source NAME --body-file PATH [common flags] [--json]

Common flags (actions/cli.md): --project, --actor, --item, --head (full SHA), --key, plus --roles-dir DIR (the role
definitions to read, default roles/eng). Results keep the CLI contract: one JSON envelope with --json, else one
`<outcome>: <action> <reason or ref>` line; the exit code is the outcome.

A role reads or proposes only to a source its definition lists in `knowledge` (docs/roles-registry.md). Source
pointers and the credential come only from the install's private config (docs/backends/notion.md): the TOML file
named by CREW_KNOWLEDGE_CONFIG, default ~/.config/eng-crew/knowledge.toml, which maps each source name to a Notion
page and names the environment variable holding the integration token. A config file tracked by git is refused.

knowledge-read writes the page title and its top-level blocks as plain text to --out. knowledge-propose-edit never
edits the page: it posts the --body-file text as a comment on the page for the owner to accept. Every other action
of the contract is refused as unsupported (exit 6). Python 3.11+ stdlib only.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location("actions_contract", os.path.join(ROOT, "actions", "contract.py"))
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

DECLARED = {"knowledge-read": "supported", "knowledge-propose-edit": "supported"}
EXIT = {"completed": 0, "pending": 3, "unknown": 4, "stale": 5, "refused": 6, "failed": 7}
COMMON = ["--project", "--actor", "--role", "--item", "--head", "--key", "--roles-dir"]
FLAGS = {"knowledge-read": ["--source", "--out"], "knowledge-propose-edit": ["--source", "--body-file"]}
CONFIG = os.path.join("~", ".config", "eng-crew", "knowledge.toml")
API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
CHUNK, MAX_CHUNKS = 2000, 100  # Notion rich_text: 2000 characters per text object, 100 objects per comment
PAGE_ID = re.compile(r"[0-9a-f]{32}")
PREFIX = {"heading_1": "# ", "heading_2": "## ", "heading_3": "### ", "bulleted_list_item": "- ",
          "numbered_list_item": "1. ", "quote": "> ", "callout": "> "}


class Outcome(Exception):
    def __init__(self, outcome, code, text):
        super().__init__(text)
        self.outcome, self.code, self.text = outcome, code, text


def http(method, path, token, body=None):
    """One Notion API call; returns the decoded JSON object. Tests replace this function."""
    request = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + token, "Notion-Version": NOTION_VERSION,
                                              "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def call(method, path, token, write):
    """http() with Notion errors mapped to outcomes; a write that may have happened is unknown, never failed."""
    try:
        return http(method, path, token, write)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise Outcome("refused", "no-credential", "Notion rejected the token (401)")
        if e.code in (400, 403, 404):
            raise Outcome("refused", "invalid-ref", "Notion refused the page (%d); share it with the integration" % e.code)
        if write is not None and e.code >= 500:
            raise Outcome("unknown", "uncertain-write", "Notion answered %d; read the page comments back" % e.code)
        raise Outcome("failed", "unreadable", "Notion answered %d" % e.code)
    except (urllib.error.URLError, OSError, ValueError) as e:
        if write is not None:
            raise Outcome("unknown", "uncertain-write", "no answer from Notion (%s); read back before retrying" % e)
        raise Outcome("failed", "unreadable", "no answer from Notion (%s)" % e)


def declared_sources(roles_dir, role):
    path = os.path.join(roles_dir, role + ".toml")
    try:
        with open(path, "rb") as f:
            sources = tomllib.load(f).get("knowledge", [])
    except (OSError, tomllib.TOMLDecodeError):
        raise Outcome("refused", "no-authority", "no readable role definition %s" % path)
    return sources if isinstance(sources, list) else []


def git_ok(path, *args, name=True):
    """True when `git -C <path's folder> <args> [<path's name>]` exits 0; False when git or the folder is unavailable."""
    folder, base = os.path.split(os.path.realpath(path))
    try:
        return subprocess.run(["git", "-C", folder, *args] + ([base] if name else []), capture_output=True,
                              timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def source_config(name):
    """(page id, token) for a source, from the private config only."""
    path = os.path.expanduser(os.environ.get("CREW_KNOWLEDGE_CONFIG") or CONFIG)
    try:
        with open(path, "rb") as f:
            config = tomllib.load(f)
    except OSError:
        raise Outcome("refused", "no-source", "no private knowledge config at %s" % path)
    except tomllib.TOMLDecodeError as e:
        raise Outcome("refused", "invalid-config", "%s: invalid TOML (%s)" % (path, e))
    if git_ok(path, "ls-files", "--error-unmatch"):
        raise Outcome("refused", "committed-config", "%s is tracked by git; keep source pointers out of any repo" % path)
    source = config.get("sources", {}).get(name) if isinstance(config.get("sources"), dict) else None
    if not isinstance(source, dict):
        raise Outcome("refused", "no-source", "source %s is not in %s" % (name, path))
    if set(source) != {"backend", "page", "token_env"} or source["backend"] != "notion" or \
            not all(isinstance(v, str) for v in source.values()):
        raise Outcome("refused", "invalid-config", "sources.%s: expected exactly backend = \"notion\", page and "
                      "token_env (the token itself never goes in the file)" % name)
    page = source["page"].replace("-", "").lower()
    if not PAGE_ID.fullmatch(page):
        raise Outcome("refused", "invalid-config", "sources.%s.page: expected a 32-hex Notion page ID" % name)
    token = os.environ.get(source["token_env"])
    if not token:
        raise Outcome("refused", "no-credential", "environment variable %s is unset" % source["token_env"])
    return page, token


def plain(rich):
    return "".join(part.get("plain_text", "") for part in rich if isinstance(part, dict))


def block_text(block):
    kind = block.get("type")
    data = block.get(kind) if isinstance(block.get(kind), dict) else {}
    if kind == "child_page":
        return "[page] " + data.get("title", "")
    if kind == "to_do":
        return ("- [x] " if data.get("checked") else "- [ ] ") + plain(data.get("rich_text", []))
    if kind == "code":
        return "```\n%s\n```" % plain(data.get("rich_text", []))
    if "rich_text" not in data:
        return None
    return PREFIX.get(kind, "") + plain(data["rich_text"])


def knowledge_read(source, page, token, out):
    meta = call("GET", "/pages/" + page, token, None)
    title = next((plain(p.get("title", [])) for p in meta.get("properties", {}).values()
                  if isinstance(p, dict) and p.get("type") == "title"), "")
    lines, cursor = [], None
    while True:
        listing = call("GET", "/blocks/%s/children?page_size=100%s" % (page, "&start_cursor=" + cursor if cursor else ""),
                       token, None)
        lines += [t for t in map(block_text, listing.get("results", [])) if t is not None]
        cursor = listing.get("next_cursor") if listing.get("has_more") else None
        if not cursor:
            break
    try:
        with open(out, "w") as f:
            f.write("# %s\n\n%s\n" % (title, "\n".join(lines)))
    except OSError as e:
        raise Outcome("refused", "invalid-ref", "cannot write --out (%s)" % e.strerror)
    result = {"source": source, "page": page, "title": title, "url": meta.get("url"),
              "last_edited_time": meta.get("last_edited_time"), "blocks": len(lines), "out": out}
    return {"source": source, "page": page, "out": out}, result


def knowledge_propose_edit(source, page, token, body_file, role):
    try:
        with open(body_file) as f:
            body = f.read().strip()
    except OSError as e:
        raise Outcome("refused", "invalid-ref", "cannot read --body-file (%s)" % e.strerror)
    if not body:
        raise Outcome("refused", "invalid-ref", "--body-file is empty")
    text = "Proposed edit from eng-crew (%s), for the owner to accept or decline:\n\n%s" % (role, body)
    chunks = [text[i:i + CHUNK] for i in range(0, len(text), CHUNK)]
    if len(chunks) > MAX_CHUNKS:
        raise Outcome("refused", "invalid-ref", "proposal longer than one Notion comment (%d characters)" % (CHUNK * MAX_CHUNKS))
    posted = call("POST", "/comments", token, {"parent": {"page_id": page},
                                                "rich_text": [{"type": "text", "text": {"content": c}} for c in chunks]})
    comment = posted.get("id")
    return {"source": source, "page": page, "comment": comment}, {"comment": comment,
                                                                  "discussion": posted.get("discussion_id")}


def finish(action, as_json, outcome, code=None, text="", refs=None, result=None, key="", exit_code=None, op=None):
    record = {"contract": contract.CONTRACT, "action": action, "op": op, "outcome": outcome,
              "reason": None if outcome == "completed" else {"code": code, "text": text}, "refs": refs or {},
              "result": result or {}, "capability": DECLARED.get(action, "unsupported"), "key": key,
              "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    primary = (refs or {}).get("comment") or (refs or {}).get("out") or ""
    print(json.dumps(record) if as_json else "%s: %s%s %s" % (outcome, action, " " + op if op else "", text or primary))
    return EXIT[outcome] if exit_code is None else exit_code


def main(argv):
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if argv == ["--capabilities"]:
        print(json.dumps({"contract": contract.CONTRACT, "capabilities": DECLARED}) if as_json else
              "\n".join("%s: %s" % kv for kv in sorted(DECLARED.items())))
        return 0
    if argv in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    action = argv[0] if argv and not argv[0].startswith("--") else None
    if action not in contract.ACTIONS:
        return finish(action, as_json, "refused", "usage", "unknown action", exit_code=2)
    if action not in DECLARED:
        op = argv[1] if len(argv) > 1 and argv[1] in contract.ACTIONS[action] else None
        return finish(action, as_json, "refused", "unsupported", "the Notion connector declares %s unsupported" % action,
                      op=op)
    flags, rest = {}, argv[1:]
    while rest:
        if rest[0] not in COMMON + FLAGS[action] or len(rest) < 2:
            return finish(action, as_json, "refused", "usage", "unknown flag or missing value: %s" % rest[0], exit_code=2)
        flags[rest[0]], rest = rest[1], rest[2:]
    missing = [f for f in ["--role"] + FLAGS[action] if f not in flags]
    if missing:
        return finish(action, as_json, "refused", "usage", "missing %s" % ", ".join(missing), exit_code=2)
    role, source = flags["--role"], flags["--source"]
    key = flags.get("--key") or ":".join(filter(None, (action, flags.get("--item"), source, role)))
    refs = {"source": source} if "--item" not in flags else {"source": source, "item": flags["--item"]}
    try:
        if "--head" in flags and not re.fullmatch(r"[0-9a-f]{40}", flags["--head"]):
            raise Outcome("refused", "invalid-ref", "--head must be a full 40-character SHA")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", role):
            raise Outcome("refused", "invalid-ref", "--role must be a role ID")
        if source not in declared_sources(flags.get("--roles-dir") or os.path.join(ROOT, "roles", "eng"), role):
            raise Outcome("refused", "no-authority", "role %s does not declare knowledge source %s" % (role, source))
        page, token = source_config(source)
        out = flags.get("--out")
        if out and git_ok(out, "rev-parse", "--is-inside-work-tree", name=False) and not git_ok(out, "check-ignore", "-q"):
            raise Outcome("refused", "committable-out", "--out %s is in a git work tree and not ignored" % out)
        if action == "knowledge-read":
            made, result = knowledge_read(source, page, token, flags["--out"])
        else:
            made, result = knowledge_propose_edit(source, page, token, flags["--body-file"], role)
    except Outcome as o:
        return finish(action, as_json, o.outcome, o.code, o.text, refs=refs, key=key)
    return finish(action, as_json, "completed", refs=dict(refs, **made), result=result, key=key)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
