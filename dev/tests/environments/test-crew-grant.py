"""Shipped grant/down command tests for conservative recognition, owner confirmation and archive-before-write.

All forge and tmux calls use disposable fakes. Positive PTY runs are automated coverage, not the required human
owner-shell proof. The long historical fixture renders with the same bounded grant pointer before and after.
"""
import fcntl
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import pty
import re
import select
import subprocess
import sys
import time
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crew_testlib import Base, CREW, ROOT_DIR

FINITE = "M35 PRs incl. the v7.1.0 cut (owner 2026-11-08, #9 comment 101)"
STANDING = "all mdstack PRs, cap extensions and releases (owner 2026-11-09, #9 comment 102)"
OPEN = "every M36 PR including spec text (owner 2026-11-09, #9 comment 103)"
PROTECTED = "crew:sensitive still needs the owner's reason (finished M35 clauses archived at #9 comment 104)"
GRANT = "; ".join((FINITE, STANDING, OPEN, "unknown policy", "all §7 gates still apply", PROTECTED))

FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
root = Path(os.environ["GRANT_FORGE"])
facts = json.loads((root / "facts.json").read_text())
path = next(a for a in sys.argv[2:] if not a.startswith("-"))
with (root / "calls.log").open("a") as f:
    f.write(path + "\\n")
if os.environ.get("GRANT_UNREADABLE") and os.environ["GRANT_UNREADABLE"] in path:
    sys.exit(1)
if path == "user":
    print(json.dumps({"login": os.environ.get("GRANT_USER", "acme-owner")}))
elif path.endswith("/issues/9/comments"):
    posted = root / "archive.json"
    if "--input" in sys.argv:
        body = json.load(sys.stdin)["body"]
        project = Path(os.environ["GRANT_PROJECT"])
        assert project.read_bytes() == (root / "original.toml").read_bytes(), "write before archive"
        tmux = Path(os.environ["FAKE_TMUX_STATE"])
        assert "crew-acme-widgets" not in (json.loads(tmux.read_text()) if tmux.exists() else {}), "archive before teardown"
        result = {"body": body, "user": {"login": "acme-owner"}, "html_url": "https://github.com/acme/widgets/issues/9#issuecomment-999"}
        if os.environ.get("GRANT_POST_FAIL") != "failed":
            posted.write_text(json.dumps(result))
        if os.environ.get("GRANT_EDIT"):
            project.write_bytes(project.read_bytes() + b"# concurrent edit\\n")
        if os.environ.get("GRANT_LOSE_OWNER"):
            facts["ownership"] = [{"user": {"login": "acme-bot"}, "body": "<!-- crew:v1 role=coordinator pass=handoff handoff=20261113-abcdef state=claimed from=none to=tmux@other cmd-id=chat sha=" + "1" * 40 + " round=n/a verdict=n/a -->"}]
            (root / "facts.json").write_text(json.dumps(facts))
        if os.environ.get("GRANT_POST_FAIL"):
            sys.exit(1)
        print(json.dumps(result))
    else:
        print(json.dumps([[json.loads(posted.read_text())] if posted.exists() else []]))
elif "/issues/comments/" in path:
    source = facts["sources"][path.rsplit("/", 1)[1]]
    count = root / "source-count"
    n = int(count.read_text()) + 1 if count.exists() else 1
    count.write_text(str(n))
    if os.environ.get("GRANT_CHANGE_SOURCE") and n > 2:
        source["body"] += " changed source"
    if os.environ.get("GRANT_EDIT_LAST") and n == 5:
        project = Path(os.environ["GRANT_PROJECT"])
        project.write_bytes(project.read_bytes() + b"# late concurrent edit\\n")
    print(json.dumps(source))
elif "/milestones?" in path:
    print(json.dumps([facts["milestones"]]))
elif "/releases/tags/" in path:
    print(json.dumps(facts["releases"][path.rsplit("/", 1)[1]]))
elif path.endswith("/issues/10/comments"):
    print(json.dumps([facts.get("ownership", [])]))
else:
    sys.exit(1)
'''


class Grant(Base):
    def setUp(self):
        super().setUp()
        for name in ("TMUX", "TMUX_PANE", "CREW_ROLE", "CREW_ID", "CREW_BRIEF"):
            self.env.pop(name, None)
        self.forge = Path(self.tmp) / "forge"
        self.forge.mkdir()
        self.env.update(GRANT_FORGE=str(self.forge), GRANT_PROJECT=self.project)
        self.socket = str(Path(self.tmp) / "sandbox.sock")
        with open(self.project, "a") as f:
            f.write('\n[runtime.options]\nmerge_grant = %s # untouched comment\n' % json.dumps(GRANT, ensure_ascii=False))
        bindir = Path(self.tmp) / "bin"
        (bindir / "tmux").rename(bindir / "tmux-base")
        (bindir / "tmux").write_text('#!/usr/bin/env python3\nimport os, sys\nargs = sys.argv[1:]\n'
                                     'if args[:1] in (["-L"], ["-S"]): args = args[2:]\n'
                                     'os.execv(%r, ["tmux", "-S", %r] + args)\n' % (
                                         str(bindir / "tmux-base"), self.socket))
        (bindir / "tmux").chmod(0o755)
        self.original = Path(self.project).read_bytes()
        (self.forge / "original.toml").write_bytes(self.original)
        (Path(self.tmp) / "bin" / "gh").write_text(FAKE_GH)
        self.facts = {
            "sources": {str(n): {"html_url": "https://github.com/acme/widgets/issues/9#issuecomment-" + str(n),
                                  "body": "Owner grants M35 M36 v7.1.0 per this decision.\n— Owner (Owner)",
                                  "user": {"login": "acme-owner"}} for n in (101, 102, 103)},
            "milestones": [{"title": "M35", "state": "closed", "html_url": "https://github.com/acme/widgets/milestone/35"},
                           {"title": "M36", "state": "open", "html_url": "https://github.com/acme/widgets/milestone/36"}],
            "releases": {"v7.1.0": {"tag_name": "v7.1.0", "draft": False, "published_at": "2026-11-08T00:00:00Z",
                                     "html_url": "https://github.com/acme/widgets/releases/tag/v7.1.0"}}}
        self.save_facts()

    def save_facts(self):
        (self.forge / "facts.json").write_text(json.dumps(self.facts))

    def grant(self, value):
        original = self.original.decode().replace(json.dumps(GRANT, ensure_ascii=False), json.dumps(value, ensure_ascii=False))
        Path(self.project).write_text(original)
        self.original = Path(self.project).read_bytes()
        (self.forge / "original.toml").write_bytes(self.original)

    def invoke(self, *args, answer="prune", terminal=True, **env):
        command = [sys.executable, CREW, *args, "--project", self.project]
        if env.pop("replace_failure", False):
            wrapper = ('import os, runpy, sys; '
                       'os.replace = lambda *a: (_ for _ in ()).throw(PermissionError("replacement failure")); '
                       'sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name="__main__")')
            command = [sys.executable, "-c", wrapper, CREW, *args, "--project", self.project]
        environment = dict(self.env, **env)
        if not terminal:
            return subprocess.run(command, input=answer + "\n", capture_output=True, text=True, env=environment,
                                  cwd=self.tmp)
        master, slave = pty.openpty()
        proc = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, env=environment, cwd=self.tmp)
        os.close(slave)
        output, sent = b"", False
        deadline = time.monotonic() + 20
        try:
            while True:
                if time.monotonic() > deadline:
                    proc.kill()
                    self.fail("PTY command timed out: " + output.decode())
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    try:
                        block = os.read(master, 65536)
                    except OSError:
                        break
                    if not block:
                        break
                    output += block
                    if b"Type prune" in output and not sent:
                        os.write(master, (answer + "\n").encode())
                        sent = True
                elif proc.poll() is not None:
                    break
            return subprocess.CompletedProcess(command, proc.wait(), output.decode().replace("\r\n", "\n"), "")
        finally:
            os.close(master)
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def unchanged(self):
        self.assertEqual(Path(self.project).read_bytes(), self.original)
        self.assertFalse((self.forge / "archive.json").exists())
        self.assertEqual(list(Path(self.state).glob("runs/grant-backup-*")), [])

    def test_dry_run_classifies_finished_standing_open_and_protected(self):
        result = self.invoke("grant", "prune", "--dry-run", terminal=False)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stderr, "mdstack: config " + self.project + "\n")
        self.assertIn("remove: " + FINITE, result.stdout)
        self.assertIn("M35 closed, v7.1.0 published", result.stdout)
        for kept in (STANDING, OPEN, "unknown policy", PROTECTED):
            self.assertIn("keep:  " + kept, result.stdout)
        self.unchanged()

    def test_mixed_scope_requires_every_milestone_and_published_cut(self):
        for field, value in (("draft", True), ("published_at", None)):
            with self.subTest(field=field):
                self.facts["releases"]["v7.1.0"][field] = value
                self.save_facts()
                result = self.invoke("grant", "prune", "--dry-run", terminal=False)
                self.assertNotIn("remove:", result.stdout)
                self.unchanged()
        self.grant("M35, M36 PRs incl. the v7.1.0 cut (owner 2026-11-08, #9 comment 101)")
        result = self.invoke("grant", "prune", "--dry-run", terminal=False)
        self.assertNotIn("remove:", result.stdout)
        self.assertIn("M36 open", result.stdout)

    def test_finite_cut_only_and_milestone_only(self):
        for value in ("the v7.1.0 minor cut as the per-release go (owner 2026-11-08, #9 comment 101)",
                      "the v7.1.0 cut after M35 (owner 2026-11-08, #9 comment 101)",
                      "every M35 PR including gate-contract (F6) text (owner 2026-11-08, #9 comment 101)"):
            self.grant(value)
            result = self.invoke("grant", "prune", "--dry-run", terminal=False)
            self.assertIn("remove:", result.stdout)
            self.unchanged()

    def test_literal_string_and_crlf_preserve_every_other_byte(self):
        literal = GRANT.replace("owner's", "owner")
        self.original = self.original.decode().replace(json.dumps(GRANT, ensure_ascii=False), "'" + literal + "'").replace(
            "\n", "\r\n").encode()
        Path(self.project).write_bytes(self.original)
        (self.forge / "original.toml").write_bytes(self.original)
        result = self.invoke("grant", "prune")
        self.assertEqual(result.returncode, 0, result.stdout)
        expected = self.original.replace(("'" + literal + "'").encode(),
                                         json.dumps(literal.split(";", 1)[1], ensure_ascii=False).encode())
        self.assertEqual(Path(self.project).read_bytes(), expected)

    def test_unsafe_boundaries_ranges_and_mixed_restrictions_stay(self):
        for value in (FINITE + ", " + STANDING, FINITE + " and " + PROTECTED,
                      "M35-M36 PRs (owner 2026-11-08, #9 comment 101)",
                      "M35 PRs (owner 2026-11-08, #9 comment 101; includes all future PRs)",
                      "M35 PRs (owner 2026-11-08, #9 comment 101", "M35 PRs without a source"):
            self.grant(value)
            result = self.invoke("grant", "prune", "--dry-run", terminal=False)
            self.assertNotIn("remove:", result.stdout, value)
            self.unchanged()

    def test_unreadable_state_or_source_keeps_everything(self):
        for path in ("milestones", "releases/tags", "issues/comments"):
            result = self.invoke("grant", "prune", "--dry-run", terminal=False, GRANT_UNREADABLE=path)
            self.assertNotIn("remove:", result.stdout)
            self.assertIn("keeping everything", result.stdout)
            self.unchanged()

    def test_source_locator_attribution_and_history(self):
        for key, value in (("html_url", "https://github.com/foreign/repo/issues/9#issuecomment-101"),
                           ("user", {"login": "outsider"}), ("body", "unsigned"),
                           ("body", "[Owner/grant-prune] archive\n— Owner (Owner)")):
            saved = self.facts["sources"]["101"][key]
            self.facts["sources"]["101"][key] = value
            self.save_facts()
            result = self.invoke("grant", "prune", "--dry-run", terminal=False)
            self.assertNotIn("remove:", result.stdout)
            self.unchanged()
            self.facts["sources"]["101"][key] = saved

    def test_apply_archives_verbatim_then_replaces_only_value_with_recoverable_backup(self):
        result = self.invoke("grant", "prune")
        self.assertEqual(result.returncode, 0, result.stdout)
        expected = self.original.decode().replace(json.dumps(GRANT, ensure_ascii=False),
                                                 json.dumps(GRANT.split(";", 1)[1], ensure_ascii=False))
        self.assertEqual(Path(self.project).read_text(), expected)
        archives = json.loads((self.forge / "archive.json").read_text())
        self.assertIn(FINITE, archives["body"])
        self.assertIn("history only; supplies no authority", archives["body"])
        self.assertIn("releases/tag/v7.1.0", archives["body"])
        self.assertIn("Profile bytes SHA-256:", archives["body"])
        self.assertNotIn("crew:v1", archives["body"])
        backups = list(Path(self.state).glob("runs/grant-backup-*.toml.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.original)
        calls_before = (self.forge / "calls.log").read_text().count("/issues/9/comments")
        result = self.invoke("grant", "prune")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(list(Path(self.state).glob("runs/grant-backup-*"))), 1)
        self.assertEqual((self.forge / "calls.log").read_text().count("/issues/9/comments"), calls_before)

    def test_role_pipe_decline_and_nonowner_refuse_or_keep(self):
        for env in ({"CREW_ROLE": "builder"}, {"CREW_ID": "ben-1774"}):
            result = self.invoke("grant", "prune", **env)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("attended owner shell", result.stdout)
            self.unchanged()
        result = self.invoke("grant", "prune", terminal=False)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(result.stderr, "mdstack: config " + self.project + "\n")
        self.unchanged()
        result = self.invoke("grant", "prune", answer="no")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.unchanged()
        result = self.invoke("grant", "prune", GRANT_USER="acme-bot")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(Path(self.project).read_bytes(), self.original)
        self.assertFalse((self.forge / "archive.json").exists())

    def test_backup_and_archive_failure_preserve_profile(self):
        Path(self.state).mkdir(parents=True)
        (Path(self.state) / "runs").write_text("backup directory unavailable")
        result = self.invoke("grant", "prune")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.unchanged()
        (Path(self.state) / "runs").unlink()
        result = self.invoke("grant", "prune", GRANT_POST_FAIL="failed")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("post failed/unconfirmed", result.stdout)
        self.assertEqual(Path(self.project).read_bytes(), self.original)
        self.assertFalse((self.forge / "archive.json").exists())

    def test_uncertain_success_is_reconciled_without_repost(self):
        result = self.invoke("grant", "prune", GRANT_POST_FAIL="uncertain")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("grant pruned", result.stdout)
        self.assertEqual((self.forge / "calls.log").read_text().count("/issues/9/comments"), 3)

    def test_replacement_failure_keeps_profile_and_retry_reuses_archive(self):
        result = self.invoke("grant", "prune", replace_failure=True)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("replacement failure", result.stdout)
        self.assertEqual(Path(self.project).read_bytes(), self.original)
        self.assertTrue((self.forge / "archive.json").exists())
        self.assertEqual((self.forge / "calls.log").read_text().count("/issues/9/comments"), 2)
        result = self.invoke("grant", "prune")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.forge / "calls.log").read_text().count("/issues/9/comments"), 3)

    def test_changed_source_facts_and_unattended_bypass_refuse(self):
        result = self.invoke("grant", "prune", GRANT_CHANGE_SOURCE="1")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("scope/source facts changed", result.stdout)
        self.unchanged()
        result = self.invoke("grant", "prune", "--yes")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.unchanged()

    def test_late_profile_edit_during_final_scope_reads_is_not_overwritten(self):
        result = self.invoke("grant", "prune", GRANT_EDIT_LAST="1")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("profile changed before replacement", result.stdout)
        self.assertEqual(Path(self.project).read_bytes(), self.original + b"# late concurrent edit\n")

    def ownership_profile(self):
        text = self.original.decode().replace('[repo]\n', '[repo]\ncontrol_item = 10\n').replace(
            '[runtime]\n', '[runtime]\ninstance = "local"\n')
        self.original = text.encode()
        Path(self.project).write_bytes(self.original)
        (self.forge / "original.toml").write_bytes(self.original)

    def test_ownership_loss_and_concurrent_edit_after_archive_refuse_replacement(self):
        result = self.invoke("grant", "prune", GRANT_EDIT="1")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("profile changed after archive", result.stdout)
        self.assertEqual(Path(self.project).read_bytes(), self.original + b"# concurrent edit\n")
        (self.forge / "archive.json").unlink()
        self.ownership_profile()
        result = self.invoke("grant", "prune", GRANT_LOSE_OWNER="1")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("ownership: read-only", result.stdout)
        self.assertEqual(Path(self.project).read_bytes(), self.original)
        result = self.invoke("grant", "prune")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(Path(self.project).read_bytes(), self.original)

    def test_layered_and_unsupported_layouts_are_not_materialized(self):
        for assignment in ('options = { merge_grant = "M35 PRs per #9 comment 101" }',
                           '[runtime.options]\nmerge_grant = """M35 PRs per #9 comment 101"""'):
            prefix = self.original.decode().split('[runtime.options]')[0]
            if assignment.startswith("options ="):
                prefix = prefix.replace('[runtime]\n', '[runtime]\n' + assignment + '\n')
                assignment = ""
            Path(self.project).write_text(prefix + assignment + "\n")
            result = self.invoke("grant", "prune")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("unsupported", result.stdout)
        org = Path(self.tmp) / "org.toml"
        org.write_text('[runtime.options]\nmerge_grant = ' + json.dumps(GRANT) + "\n")
        Path(self.project).write_text(self.original.decode().split('[runtime.options]')[0])
        result = self.invoke("grant", "prune", "--org-profile", str(org))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("inherited/team", result.stdout)
        self.assertNotIn("merge_grant", Path(self.project).read_text())

    def live(self):
        Path(self.state_file).write_text(json.dumps({"crew-acme-widgets": {"0": "ash", "1": "sam"}}))

    def test_down_previews_then_tears_down_then_prunes(self):
        self.live()
        result = self.invoke("down")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertLess(result.stdout.index("grant preview"), result.stdout.index("crew: stopped"))
        self.assertLess(result.stdout.index("crew: stopped"), result.stdout.index("grant backup"))
        self.assertIn("grant pruned", result.stdout)
        sockets = Path(self.log + ".sockets").read_text().splitlines()
        self.assertTrue(sockets)
        self.assertEqual(set(sockets), {self.socket})

    def test_down_keep_preserve_role_pipe_and_decline_skip_pruning(self):
        for flags, env, terminal, answer in ((["--keep-grant"], {}, True, "prune"),
                                            (["--preserve"], {}, True, "prune"),
                                            ([], {"CREW_ROLE": "builder"}, True, "prune"),
                                            ([], {}, False, "prune"), ([], {}, True, "no")):
            self.live()
            result = self.invoke("down", *flags, terminal=terminal, answer=answer, **env)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("crew: stopped", result.stdout)
            self.unchanged()

    def test_down_land_lock_or_pause_refusal_cannot_prune(self):
        self.live()
        locks = Path(self.state) / "locks"
        locks.mkdir(parents=True)
        with (locks / "merge.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = self.invoke("down")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("land lock", result.stdout)
        self.unchanged()
        self.put("pause.json", '{"reason": "owner pause"}')
        result = self.invoke("down")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("paused", result.stdout)
        self.unchanged()

    def test_standalone_refuses_live_writers(self):
        self.live()
        result = self.invoke("grant", "prune")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("writers/land lock", result.stdout)
        self.unchanged()

    def test_long_historical_grant_has_bounded_render_before_and_after(self):
        self.grant("; ".join([FINITE] * 25 + [STANDING, PROTECTED]))
        command = [sys.executable, str(Path(ROOT_DIR) / "core" / "crew-render.py"), "--project", self.project]
        before, after = Path(self.tmp) / "before", Path(self.tmp) / "after"
        result = subprocess.run(command + ["--out", str(before)], capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        before_report = result.stderr
        result = self.invoke("grant", "prune")
        self.assertEqual(result.returncode, 0, result.stdout)
        result = subprocess.run(command + ["--out", str(after)], capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for role in ("coordinator", "synthesizer", "builder", "researcher"):
            first = (before / "runtime" / (role + ".md")).read_bytes()
            self.assertEqual(first, (after / "runtime" / (role + ".md")).read_bytes())
            pattern = r"budget runtime/" + role + r"\.md ([0-9]+)/([0-9]+) bytes"
            budgeted, budget = map(int, re.search(pattern, before_report).groups())
            self.assertLessEqual(budgeted, budget)
            self.assertEqual(re.search(pattern, before_report).groups(), re.search(pattern, result.stderr).groups())
            self.assertNotIn(FINITE.encode(), first)


class Scope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_loader("scope_cli", SourceFileLoader("scope_cli", CREW))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        cls.scope = cli.load("unit_grant_scope", "environments/terminal/crew.d/_grant_scope.py")

    def test_safe_boundaries_keep_nested_semicolons_and_unbalanced_text(self):
        self.assertEqual(self.scope.clauses("one (two; three); four"), ["one (two; three)", " four"])
        self.assertEqual(self.scope.clauses("one (two; three; four"), ["one (two; three; four"])

    def test_finite_multiple_sources_and_foreign_locator(self):
        value = "every M35 and M36 PRs (owner 2026-11-08, #9 comment 101, #9 comment 103)"
        self.assertEqual(self.scope.recognize(value, "acme/widgets"),
                         (["M35", "M36"], [], [("acme/widgets", "9", "101"), ("acme/widgets", "9", "103")]))
        self.assertIsNone(self.scope.recognize("M35 PRs per https://github.com/other/repo/issues/9#issuecomment-101", "acme/widgets"))


if __name__ == "__main__":
    unittest.main()
