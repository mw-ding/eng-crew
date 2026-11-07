#!/usr/bin/env python3
"""Offline self-test for scripts/docs-scan.py (#1025): fixture git repos for each finding class and a clean repo.

Builds throwaway git repos in a temp dir, runs the scan through main() and asserts each scan.json. No network.
Run in CI.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("docs_scan", os.path.join(HERE, "docs-scan.py"))
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)

PROFILE = """\
[repo]
owner = "acme"
name = "widgets"

[runtime]
name = "tmux"

[identities]
owners = ["acme-owner"]
coordinator = { gh_user = "acme-bot" }
builder = { gh_user = "acme-bot" }
reviewer = { gh_user = "acme-reviewer" }
synthesizer = { gh_user = "acme-bot" }

[engines]
coordinator = "codex"
trivial = { order = ["claude-code/sonnet"] }
default = { order = ["codex/gpt-6.1-sol"] }
deep = { order = ["codex/gpt-6.1-sol"] }

[paths]
state_dir = "%s"
worktree_root = "/srv/wt"
"""

BANNER = "# %s\n\n> - **Status:** design\n> - **Built:** nothing\n> - **Last checked:** %s at `abc1234`\n\nBody.\n"
INDEX = """\
# Docs index

| Doc | Purpose | Kind |
|---|---|---|
| [architecture.md](architecture.md) | Components | reference |
| [plan.md](plan.md) | A plan | rule, design |
| [old.md](old.md) | An old plan | design |
| [undated.md](undated.md) | Undated plan | design |
| [bare.md](bare.md) | No banner | design |
"""
CLEAN = {
    "README.md": "# Widgets\n\nSee [the guide](AGENTS.md#build) and [docs](docs/README.md).\n\n## Start\n\nText.\n",
    "AGENTS.md": "# Agent guide\n\n## Build\n\nRun `make`. Back to [start](README.md#start).\n",
    "docs/README.md": "# Docs index\n\n| Doc | Purpose | Kind |\n|---|---|---|\n"
                      "| [architecture.md](architecture.md) | Components | reference |\n"
                      "| [plan.md](plan.md) | A plan | design |\n",
    "docs/architecture.md": "# Architecture\n\n## `[hosts.<name>]` and more\n\n## Notes\n\n## Notes\n\n"
                            "Self links: [here](#hostsname-and-more), [second](#notes-1), [line](plan.md#L3).\n",
    "docs/runbook.md": "# Runbook\n\nSee [plan](./plan.md \"title\") and [code](../src/).\n",
    "docs/decisions.md": "# Decisions\n\n```text\n[not a link](missing.md)\n```\n\nInline `[x](gone.md)`.\n",
    "docs/plan.md": BANNER % ("Plan", "2026-11-01"),
    "src/main.py": "print('hi')\n",
}


def git(path, *args):
    subprocess.run(["git", "-C", path, *args], check=True, capture_output=True)


def make_repo(root, name, files):
    path = os.path.join(root, name)
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(path, rel)), exist_ok=True)
        with open(os.path.join(path, rel), "w", encoding="utf-8") as f:
            f.write(text)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "gc.auto", "0")
    git(path, "config", "maintenance.auto", "false")
    git(path, "add", "-A")
    git(path, "-c", "user.name=t", "-c", "user.email=t@example.test", "commit", "-q", "-m", "fixture")
    return path


def transient(rel):
    """Git-internal churn the scan does not cause: the object store and lock files under .git/ (#1168)."""
    parts = rel.split(os.sep)
    if ".git" not in parts:
        return False
    inner = parts[parts.index(".git") + 1:]
    return inner[:1] == ["objects"] or rel.endswith(".lock")


def snapshot(root):
    out = {}
    for d, _, names in os.walk(root):
        for n in names:
            p = os.path.join(d, n)
            rel = os.path.relpath(p, root)
            if transient(rel):
                continue
            with open(p, "rb") as f:
                out[rel] = (hashlib.sha256(f.read()).hexdigest(), os.stat(p).st_mtime_ns)
    return out


def changes(before, after):
    return {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}


class DocsScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.state = os.path.join(self.root, "state")

    def tearDown(self):
        self.tmp.cleanup()

    def run_scan(self, docs_table, checkouts, extra=()):
        project = os.path.join(self.root, "crew.toml")
        with open(project, "w", encoding="utf-8") as f:
            f.write(PROFILE % self.state + docs_table)
        argv = ["--project", project, "--today", "2026-11-05"] + list(extra)
        for repo, path in checkouts.items():
            argv += ["--checkout", "%s=%s" % (repo, path)]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ds.main(argv)
        return code, out.getvalue(), err.getvalue()

    def result(self, repo="acme/widgets"):
        with open(os.path.join(self.state, repo.replace("/", "__"), "docs", "scan.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_clean_repo_reports_nothing(self):
        path = make_repo(self.root, "widgets", CLEAN)
        code, out, err = self.run_scan("\n[docs]\n", {"acme/widgets": path})
        self.assertEqual(code, 0, err)
        self.assertIn("acme/widgets @ ", out)
        scan = self.result()
        for key in ("missing", "unbannered", "stale", "broken_links", "oversize"):
            self.assertEqual(scan[key], [], key)
        self.assertEqual(scan["settings"], {"stale_days": 90, "size_budget": 500, "homes": ds.DEFAULT_HOMES})
        plan = next(d for d in scan["inventory"] if d["path"] == "docs/plan.md")
        self.assertEqual(plan, {"path": "docs/plan.md", "lines": 7, "index": "docs/README.md:6", "kind": "design",
                                "banner": {"Status": "design", "Built": "nothing",
                                           "Last checked": "2026-11-01 at `abc1234`"}})
        self.assertEqual(sorted(d["path"] for d in scan["inventory"]), sorted(p for p in CLEAN if p.endswith(".md")))

    def test_each_finding_class(self):
        files = {
            "README.md": "# Widgets\n\n[gone](docs/gone.md), [anchor](AGENTS.md#nope), [out](../../etc/passwd),"
                         " [self](#missing), [ok](https://example.test/x), [ph](docs/<owner>.md)\n\n[ref]: docs/lost.md\n",
            "AGENTS.md": "# Agent guide\n\n## Build\n",
            "docs/README.md": INDEX,
            "docs/architecture.md": "# Architecture\n" + "line\n" * 30,
            "docs/plan.md": BANNER % ("Plan", "2026-11-01"),
            "docs/old.md": BANNER % ("Old", "2026-01-01"),
            "docs/undated.md": BANNER % ("Undated", "sometime"),
            "docs/bare.md": "# Bare\n\nNo banner here.\n",
        }
        path = make_repo(self.root, "widgets", files)
        code, out, err = self.run_scan("\n[docs]\nsize_budget = 20\n", {"acme/widgets": path})
        self.assertEqual(code, 0, err)
        scan = self.result()
        self.assertEqual(scan["missing"], [
            {"essential": "runbook", "home": "docs/runbook.md", "reason": "no such file"},
            {"essential": "decisions", "home": "docs/decisions.md", "reason": "no such file"}])
        self.assertEqual(scan["unbannered"], [{"path": "docs/bare.md", "index": "docs/README.md:9"}])
        self.assertEqual(scan["stale"], [{"path": "docs/old.md", "last_checked": "2026-01-01", "age_days": 308},
                                         {"path": "docs/undated.md", "last_checked": None, "age_days": None}])
        self.assertEqual([(b["line"], b["target"], b["reason"]) for b in scan["broken_links"]], [
            (3, "docs/gone.md", "no such file"), (3, "AGENTS.md#nope", "no such anchor"),
            (3, "../../etc/passwd", "escapes the repo"), (3, "#missing", "no such anchor"),
            (5, "docs/lost.md", "no such file")])
        self.assertEqual(scan["oversize"], [{"path": "docs/architecture.md", "lines": 31}])
        self.assertIn("2 missing, 1 unbannered, 2 stale, 5 broken_links, 1 oversize", out)

    def test_docs_index_missing_over_five_docs(self):
        files = dict(CLEAN)
        del files["docs/README.md"]
        files.update({"docs/a.md": "# A\n", "docs/b.md": "# B\n"})
        code, _, err = self.run_scan("\n[docs]\n", {"acme/widgets": make_repo(self.root, "widgets", files)})
        self.assertEqual(code, 0, err)
        self.assertEqual(self.result()["missing"], [
            {"essential": "docs_index", "home": "docs/README.md", "reason": "more than five docs under docs/"}])

    def test_home_anchor_satisfies_or_misses(self):  # AC2
        files = {k: v for k, v in CLEAN.items() if k not in ("docs/runbook.md", "docs/decisions.md")}
        files["README.md"] += "\n## Decisions\n\n- 2026-11-01: chose X.\n"
        path = make_repo(self.root, "widgets", files)
        table = '\n[docs]\n[docs.homes]\ndecisions = "README.md#decisions"\nrunbook = "README.md#runbook"\n'
        code, _, err = self.run_scan(table, {"acme/widgets": path})
        self.assertEqual(code, 0, err)
        scan = self.result()
        self.assertEqual(scan["missing"], [{"essential": "runbook", "home": "README.md#runbook",
                                            "reason": "no such anchor"}])
        self.assertEqual(scan["settings"]["homes"]["decisions"], "README.md#decisions")

    def test_reads_the_ref_and_writes_only_scan_json(self):  # AC4
        path = make_repo(self.root, "widgets", CLEAN)
        pack = make_repo(self.root, "pack", {"README.md": "# Pack\n"})
        with open(os.path.join(path, "docs", "bare.md"), "w", encoding="utf-8") as f:
            f.write("# Uncommitted\n\n[gone](gone.md)\n")  # work tree only: not at the ref, so not scanned

        before = snapshot(self.root)
        code, out, err = self.run_scan('\n[docs]\nrepos = ["acme/widgets", "acme/pack"]\n',
                                       {"acme/widgets": path, "acme/pack": pack})
        self.assertEqual(code, 0, err)
        written = {"crew.toml", os.path.join("state", "acme__widgets", "docs", "scan.json"),
                   os.path.join("state", "acme__pack", "docs", "scan.json")}
        self.assertEqual(changes(before, snapshot(self.root)), written)
        self.assertNotIn("docs/bare.md", [d["path"] for d in self.result()["inventory"]])
        self.assertEqual(self.result("acme/pack")["missing"][0]["essential"], "agent_guide")
        self.assertEqual(len(out.splitlines()), 2)

    def test_snapshot_ignores_git_churn_but_not_work_tree_writes(self):  # #1168
        path = make_repo(self.root, "widgets", CLEAN)
        lock = os.path.join(path, ".git", "objects", "maintenance.lock")
        with open(lock, "w", encoding="utf-8") as f:
            f.write("x")
        before = snapshot(self.root)
        os.remove(lock)  # the CI flake: present before, gone after
        for rel in (os.path.join(".git", "index.lock"), os.path.join(".git", "objects", "ab", "cdef")):
            os.makedirs(os.path.dirname(os.path.join(path, rel)), exist_ok=True)
            with open(os.path.join(path, rel), "w", encoding="utf-8") as f:
                f.write("x")
        self.assertEqual(changes(before, snapshot(self.root)), set())
        with open(os.path.join(path, "docs", "extra.md"), "w", encoding="utf-8") as f:
            f.write("# Extra\n")
        with open(os.path.join(path, ".git", "HEAD"), "a", encoding="utf-8") as f:
            f.write("\n")
        self.assertEqual(changes(before, snapshot(self.root)),
                         {os.path.join("widgets", "docs", "extra.md"), os.path.join("widgets", ".git", "HEAD")})

    def test_fixture_repo_disables_auto_maintenance(self):  # #1168
        path = make_repo(self.root, "widgets", CLEAN)
        get = lambda key: subprocess.run(["git", "-C", path, "config", key], capture_output=True, text=True).stdout
        self.assertEqual((get("gc.auto"), get("maintenance.auto")), ("0\n", "false\n"))

    def test_ref_override_and_head_fallback(self):
        path = make_repo(self.root, "widgets", CLEAN)
        first = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        os.remove(os.path.join(path, "AGENTS.md"))
        git(path, "-c", "user.name=t", "-c", "user.email=t@example.test", "commit", "-qam", "drop guide")
        self.run_scan("\n[docs]\n", {"acme/widgets": path})
        self.assertEqual(self.result()["missing"][0]["essential"], "agent_guide")  # no origin: HEAD
        code, _, err = self.run_scan("\n[docs]\n", {"acme/widgets": path}, ["--ref", "acme/widgets=" + first])
        self.assertEqual(code, 0, err)
        self.assertEqual((self.result()["head"], self.result()["missing"]), (first, []))

    def test_no_table_and_errors(self):
        path = make_repo(self.root, "widgets", CLEAN)
        code, out, err = self.run_scan("", {"acme/widgets": path})
        self.assertEqual((code, out), (0, ""))
        self.assertIn("no [docs] table", err)
        self.assertFalse(os.path.exists(self.state))
        code, _, err = self.run_scan("\n[docs]\n", {})
        self.assertEqual(code, 2)
        self.assertIn("no --checkout for acme/widgets", err)
        code, _, err = self.run_scan("\n[docs]\n", {"acme/widgets": path}, ["--ref", "acme/widgets=nope"])
        self.assertEqual(code, 2)
        self.assertIn("git rev-parse", err)
        self.assertFalse(os.path.exists(self.state))

    def test_slug_matches_github_headings(self):
        self.assertEqual(ds.slug("`[hosts.<name>]` and `[placement]`"), "hostsname-and-placement")
        self.assertEqual(ds.slug("Status <em>banners</em>"), "status-banners")
        self.assertEqual(ds.slug("[Linked](x.md) Title: v2.0"), "linked-title-v20")
        self.assertEqual(ds.anchors(["# A", "", "## A", "", "Setext", "---", '<a name="top"></a>']),
                         {"a", "a-1", "setext", "top"})


if __name__ == "__main__":
    unittest.main()
