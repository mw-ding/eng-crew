#!/usr/bin/env python3
"""Notion knowledge connector tests (#1229): knowledge-read and knowledge-propose-edit against a fake Notion API,
role source declarations, the private-config and credential refusals, error mapping and the actions/ conformance kit.
No network or credentials: the connector's http() is replaced and urllib's urlopen raises if reached.
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
import urllib.error
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


notion = load("notion_knowledge", "connectors/notion/knowledge.py")
PAGE = "0123456789abcdef0123456789abcdef"
TOKEN = "secret_fake_token_value"


def rich(text):
    return [{"type": "text", "plain_text": text}]


class FakeNotion:
    """Records calls; answers GET page, paged GET block children and POST comments; `fail` raises per path."""

    def __init__(self):
        self.calls, self.fail, self.comments = [], {}, []

    def __call__(self, method, path, token, body=None):
        self.calls.append((method, path, token, body))
        for k in (path.split("?")[0], method + " " + path.split("?")[0]):
            if k in self.fail:
                raise self.fail[k]
        if method == "GET" and path == "/pages/" + PAGE:
            return {"url": "https://www.notion.so/brain-" + PAGE, "last_edited_time": "2026-11-07T10:00:00.000Z",
                    "properties": {"Name": {"type": "title", "title": rich("Second brain")}}}
        if method == "GET" and path.startswith("/blocks/%s/children" % PAGE):
            if "start_cursor=c2" not in path:
                return {"results": [{"type": "heading_1", "heading_1": {"rich_text": rich("Goals")}},
                                    {"type": "paragraph", "paragraph": {"rich_text": rich("Ship M32.")}},
                                    {"type": "divider", "divider": {}}],
                        "has_more": True, "next_cursor": "c2"}
            return {"results": [{"type": "to_do", "to_do": {"rich_text": rich("Review #1229"), "checked": True}},
                                {"type": "child_page", "child_page": {"title": "Archive"}}],
                    "has_more": False, "next_cursor": None}
        if method == "GET" and path.startswith("/comments?block_id=%s&page_size=100" % PAGE):
            first = "start_cursor=" not in path
            batch = self.comments[:1] if first else self.comments[1:]
            return {"results": batch, "has_more": first and len(self.comments) > 1, "next_cursor": "k2"}
        if method == "POST" and path == "/comments":
            n = len(self.comments) + 1
            self.comments.append({"id": "comment-%d" % n, "discussion_id": "discussion-%d" % n,
                                  "rich_text": [dict(part, plain_text=part["text"]["content"]) for part in body["rich_text"]]})
            return {"id": "comment-%d" % n, "discussion_id": "discussion-%d" % n}
        raise AssertionError("unexpected call %s %s" % (method, path))


class KnowledgeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.roles = os.path.join(self.dir, "roles")
        os.makedirs(self.roles)
        self.role('knowledge = ["second-brain"]\n')
        self.config = os.path.join(self.dir, "knowledge.toml")
        self.write_config('[sources.second-brain]\nbackend = "notion"\npage = "%s"\ntoken_env = "FAKE_NOTION_TOKEN"\n'
                          % "-".join([PAGE[:8], PAGE[8:12], PAGE[12:16], PAGE[16:20], PAGE[20:]]))
        self.out = os.path.join(self.dir, "brain.md")
        self.body = os.path.join(self.dir, "proposal.md")
        with open(self.body, "w") as f:
            f.write("Add: M32 knowledge connector shipped.\n")
        self.fake = FakeNotion()
        for patch in (mock.patch.object(notion, "http", self.fake),
                      mock.patch.object(notion.urllib.request, "urlopen", side_effect=AssertionError("network"))):
            patch.start()
            self.addCleanup(patch.stop)
        self.keys = os.path.join(self.dir, "state", "knowledge-keys.json")
        env = mock.patch.dict(os.environ, {"CREW_KNOWLEDGE_CONFIG": self.config, "FAKE_NOTION_TOKEN": TOKEN,
                                           "CREW_KNOWLEDGE_KEYS": self.keys})
        env.start()
        self.addCleanup(env.stop)

    def role(self, text):
        with open(os.path.join(self.roles, "researcher.toml"), "w") as f:
            f.write("schema_version = 1\n" + text)

    def write_config(self, text):
        with open(self.config, "w") as f:
            f.write(text)

    def run_cli(self, action, *extra, role="researcher", json_out=True):
        flags = {"knowledge-read": ["--out", self.out], "knowledge-propose-edit": ["--body-file", self.body]}
        argv = [action, "--role", role, "--source", "second-brain", "--roles-dir", self.roles, "--item", "1229",
                *flags.get(action, []), *extra] + (["--json"] if json_out else [])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = notion.main(argv)
        return code, json.loads(stdout.getvalue()) if json_out else stdout.getvalue()

    def assertRefused(self, code, result, reason, exit_code=6):
        self.assertEqual((code, result["outcome"], result["reason"]["code"]), (exit_code, "refused", reason))

    def test_read_writes_title_and_blocks_across_pages(self):
        code, result = self.run_cli("knowledge-read")
        self.assertEqual((code, result["outcome"], result["reason"]), (0, "completed", None))
        self.assertEqual(result["refs"], {"source": "second-brain", "item": "1229", "page": PAGE, "out": self.out})
        self.assertEqual({k: result["result"][k] for k in ("title", "blocks", "last_edited_time")},
                         {"title": "Second brain", "blocks": 4, "last_edited_time": "2026-11-07T10:00:00.000Z"})
        with open(self.out) as f:
            self.assertEqual(f.read(), "# Second brain\n\n# Goals\nShip M32.\n- [x] Review #1229\n[page] Archive\n")
        self.assertEqual([(m, p) for m, p, _, _ in self.fake.calls],
                         [("GET", "/pages/" + PAGE), ("GET", "/blocks/%s/children?page_size=100" % PAGE),
                          ("GET", "/blocks/%s/children?page_size=100&start_cursor=c2" % PAGE)])
        self.assertTrue(all(t == TOKEN for _, _, t, _ in self.fake.calls))
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_propose_edit_posts_a_comment_and_never_edits_the_page(self):
        code, result = self.run_cli("knowledge-propose-edit")
        self.assertEqual((code, result["outcome"]), (0, "completed"))
        self.assertEqual((result["refs"]["comment"], result["result"]["discussion"]), ("comment-1", "discussion-1"))
        posts = [(m, p, b) for m, p, _, b in self.fake.calls if m == "POST"]
        self.assertEqual([(m, p.split("?")[0]) for m, p, _, _ in self.fake.calls], [("GET", "/comments"), ("POST", "/comments")])
        [(method, path, body)] = posts
        self.assertEqual(body["parent"], {"page_id": PAGE})
        text = "".join(part["text"]["content"] for part in body["rich_text"])
        self.assertTrue(text.startswith("Proposed edit from eng-crew (researcher, key knowledge-propose-edit:1229:"))
        self.assertTrue(text.endswith("Add: M32 knowledge connector shipped."))

    def test_same_key_and_inputs_never_post_twice(self):
        code, first = self.run_cli("knowledge-propose-edit", "--key", "proposal-retry-1229")
        code2, second = self.run_cli("knowledge-propose-edit", "--key", "proposal-retry-1229")
        self.assertEqual((code, code2, first["outcome"], second["outcome"]), (0, 0, "completed", "completed"))
        self.assertEqual((first["result"]["replayed"], second["result"]["replayed"]), (False, True))
        self.assertEqual(second["refs"]["comment"], first["refs"]["comment"])
        self.assertEqual(len([c for c in self.fake.calls if c[0] == "POST"]), 1)
        with open(self.body, "w") as f:
            f.write("A different proposal.\n")
        self.assertRefused(*self.run_cli("knowledge-propose-edit", "--key", "proposal-retry-1229"), "key-conflict")
        self.assertEqual(len([c for c in self.fake.calls if c[0] == "POST"]), 1)

    def posts(self):
        return len([c for c in self.fake.calls if c[0] == "POST"])

    def test_resolved_proposal_is_still_replayed(self):
        code, first = self.run_cli("knowledge-propose-edit", "--key", "proposal-retry-1229")
        self.fake.comments.clear()  # the owner resolved it: Notion lists only unresolved comments
        code2, second = self.run_cli("knowledge-propose-edit", "--key", "proposal-retry-1229")
        self.assertEqual((code, code2, second["outcome"], second["result"]["replayed"]), (0, 0, "completed", True))
        self.assertEqual((second["refs"]["comment"], self.posts()), (first["refs"]["comment"], 1))
        with open(self.body, "w") as f:
            f.write("A different proposal.\n")
        self.assertRefused(*self.run_cli("knowledge-propose-edit", "--key", "proposal-retry-1229"), "key-conflict")
        with open(self.keys) as f:
            self.assertNotIn("M32", f.read())  # digests and ids only, never the proposal text

    def test_key_from_another_install_is_found_on_the_page(self):
        self.run_cli("knowledge-propose-edit", "--key", "k1")
        os.remove(self.keys)
        code, again = self.run_cli("knowledge-propose-edit", "--key", "k1")
        self.assertEqual((code, again["result"]["replayed"], self.posts()), (0, True, 1))

    def test_uncertain_post_is_never_repeated_and_a_refused_one_frees_the_key(self):
        self.fake.fail = {"POST /comments": TimeoutError("timed out")}
        self.assertEqual(self.run_cli("knowledge-propose-edit", "--key", "k2")[1]["outcome"], "unknown")
        self.fake.fail = {}
        code, result = self.run_cli("knowledge-propose-edit", "--key", "k2")
        self.assertEqual((code, result["outcome"], result["reason"]["code"], self.posts()), (4, "unknown", "uncertain-write", 1))
        self.fake.fail = {"POST /comments": urllib.error.HTTPError("https://api.notion.com", 403, "error", {}, None)}
        self.assertRefused(*self.run_cli("knowledge-propose-edit", "--key", "k3"), "invalid-ref")
        self.fake.fail = {}
        code, result = self.run_cli("knowledge-propose-edit", "--key", "k3")
        self.assertEqual((code, result["result"]["replayed"]), (0, False))

    def test_ledger_inside_a_work_tree_must_be_ignored(self):
        repo = os.path.join(self.dir, "repo")
        subprocess.run(["git", "init", "-q", repo], check=True)
        with mock.patch.dict(os.environ, {"CREW_KNOWLEDGE_KEYS": os.path.join(repo, "keys.json")}):
            self.assertRefused(*self.run_cli("knowledge-propose-edit"), "committable-keys")
        self.assertEqual(self.posts(), 0)

    def test_default_key_follows_the_body(self):
        code, first = self.run_cli("knowledge-propose-edit")
        code2, again = self.run_cli("knowledge-propose-edit")
        self.assertEqual((code, code2, again["result"]["replayed"], again["key"]), (0, 0, True, first["key"]))
        with open(self.body, "w") as f:
            f.write("A second, separate proposal.\n")
        code, other = self.run_cli("knowledge-propose-edit")
        self.assertEqual((code, other["result"]["replayed"]), (0, False))
        self.assertNotEqual(other["key"], first["key"])
        self.assertEqual(len(self.fake.comments), 2)

    def test_long_proposal_splits_into_rich_text_chunks(self):
        with open(self.body, "w") as f:
            f.write("x" * 4500)
        self.assertEqual(self.run_cli("knowledge-propose-edit")[0], 0)
        chunks = [part["text"]["content"] for part in self.fake.calls[-1][3]["rich_text"]]
        self.assertEqual([len(c) <= 2000 for c in chunks], [True] * 3)
        with open(self.body, "w") as f:
            f.write("x" * 200001)
        self.assertRefused(*self.run_cli("knowledge-propose-edit"), "invalid-ref")

    def test_role_must_declare_the_source(self):
        self.role("passes = [\"research\"]\n")
        code, result = self.run_cli("knowledge-read")
        self.assertRefused(code, result, "no-authority")
        self.assertRefused(*self.run_cli("knowledge-read", role="builder"), "no-authority")
        self.assertEqual(self.fake.calls, [])

    def test_private_config_and_credential_refusals(self):
        os.remove(self.config)
        self.assertRefused(*self.run_cli("knowledge-read"), "no-source")
        self.write_config('[sources.other]\nbackend = "notion"\npage = "%s"\ntoken_env = "FAKE_NOTION_TOKEN"\n' % PAGE)
        self.assertRefused(*self.run_cli("knowledge-read"), "no-source")
        self.write_config('[sources.second-brain]\nbackend = "notion"\npage = "%s"\ntoken = "%s"\n' % (PAGE, TOKEN))
        code, result = self.run_cli("knowledge-read")
        self.assertRefused(code, result, "invalid-config")
        self.assertNotIn(TOKEN, json.dumps(result))
        self.write_config('[sources.second-brain]\nbackend = "notion"\npage = "nope"\ntoken_env = "FAKE_NOTION_TOKEN"\n')
        self.assertRefused(*self.run_cli("knowledge-read"), "invalid-config")
        self.write_config('[sources.second-brain]\nbackend = "notion"\npage = "%s"\ntoken_env = "UNSET_TOKEN"\n' % PAGE)
        self.assertRefused(*self.run_cli("knowledge-read"), "no-credential")
        self.assertEqual(self.fake.calls, [])

    def test_config_tracked_by_git_is_refused(self):
        subprocess.run(["git", "init", "-q", self.dir], check=True)
        subprocess.run(["git", "-C", self.dir, "add", "knowledge.toml"], check=True)
        self.assertRefused(*self.run_cli("knowledge-read"), "committed-config")
        self.assertEqual(self.fake.calls, [])

    def test_out_inside_a_work_tree_must_be_ignored(self):
        repo = os.path.join(self.dir, "repo")
        subprocess.run(["git", "init", "-q", repo], check=True)
        self.out = os.path.join(repo, "brain.md")
        self.assertRefused(*self.run_cli("knowledge-read"), "committable-out")
        with open(os.path.join(repo, ".gitignore"), "w") as f:
            f.write("brain.md\n")
        self.assertEqual(self.run_cli("knowledge-read")[0], 0)

    def test_notion_errors_map_to_outcomes(self):
        def http_error(code):
            return urllib.error.HTTPError("https://api.notion.com", code, "error", {}, None)
        cases = [("knowledge-read", "/pages/" + PAGE, http_error(401), 6, "refused", "no-credential"),
                 ("knowledge-read", "/pages/" + PAGE, http_error(404), 6, "refused", "invalid-ref"),
                 ("knowledge-read", "/pages/" + PAGE, http_error(502), 7, "failed", "unreadable"),
                 ("knowledge-read", "/pages/" + PAGE, urllib.error.URLError("timed out"), 7, "failed", "unreadable"),
                 ("knowledge-propose-edit", "POST /comments", http_error(403), 6, "refused", "invalid-ref"),
                 ("knowledge-propose-edit", "POST /comments", http_error(500), 4, "unknown", "uncertain-write"),
                 ("knowledge-propose-edit", "POST /comments", TimeoutError("timed out"), 4, "unknown", "uncertain-write"),
                 ("knowledge-propose-edit", "GET /comments", http_error(502), 7, "failed", "unreadable")]
        for action, path, error, exit_code, outcome, reason in cases:
            with self.subTest(action=action, error=error):
                self.fake.fail = {path: error}
                code, result = self.run_cli(action)
                self.assertEqual((code, result["outcome"], result["reason"]["code"]), (exit_code, outcome, reason))

    def test_cli_contract_edges(self):
        self.assertRefused(*self.run_cli("knowledge-read", "--head", "abc1234"), "invalid-ref")
        self.assertRefused(*self.run_cli("land", "acquire"), "unsupported")
        self.assertRefused(*self.run_cli("crew-unknown"), "usage", exit_code=2)
        self.assertRefused(*self.run_cli("knowledge-read", "--bogus", "1"), "usage", exit_code=2)
        self.assertRefused(*self.run_cli("knowledge-read", role="../researcher"), "invalid-ref")
        self.out = os.path.join(self.dir, "missing", "brain.md")
        self.assertRefused(*self.run_cli("knowledge-read"), "invalid-ref")
        self.out = os.path.join(self.dir, "brain.md")
        code, line = self.run_cli("knowledge-read", json_out=False)
        self.assertEqual((code, line), (0, "completed: knowledge-read %s\n" % self.out))

    def test_conformance_kit_passes(self):
        cfg, contract = load("crew_config", "core/crew-config.py"), load("actions_contract", "actions/contract.py")
        manifest = os.path.join(ROOT, "connectors", "notion", "manifest.toml")
        self.assertEqual([(c, p) for c, p in contract.connector("notion", manifest, cfg) if p], [])
        self.assertIn("knowledge-read", contract.ACTIONS)
        self.assertIn("knowledge-propose-edit", contract.ACTIONS)


if __name__ == "__main__":
    unittest.main()
