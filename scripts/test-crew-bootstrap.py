"""Offline bootstrap tests on a fake host and extracted bundle, including dry-run, confirmation, failures,
tmux record/idempotency, Grok Bot deployment, protected targets, clone version selection and url/mirror/git release
sources (no gh release call, local HTTP server, local bare git repository, refused bundles keep the previous
install). Run in CI.
Use --evidence or --fetch-evidence for deterministic install/verify/delete CLI transcripts, with paths scrubbed.
Use --self-test-evidence for post-apply success, failure and opt-in smoke evidence on a fake host.
Use --size-budget-evidence for deterministic size-budget success/failure and cleanup evidence.
Use --proposal-evidence for local detection, confirmation, edited-record/rerun and cleanup evidence.
"""
import functools
import importlib.util
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import threading
import tomllib
import unittest
from unittest import mock

from crew_testlib import write_pack

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("doctor_tests", HERE / "test-crew-doctor.py")
doctor_tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor_tests)


class Bootstrap(doctor_tests.DoctorBase):
    def setUp(self):
        super().setUp()
        self.bundle = Path(self.tmp) / "eng-crew-v2.1.0"
        for name in ("scripts", "profiles", "templates", "packs", "roles", "docs"):
            shutil.copytree(HERE.parent / name, self.bundle / name)
        (self.bundle / "VERSION").write_text("v2.1.0\n")
        self.project_path = Path(self.project)
        self.project_path.write_text(self.project_path.read_text() +
                                     'eng_crew = "%s/eng-crew"\nlive_dir = "%s/live"\n' % (self.state, self.tmp))
        self.cli = self.bundle / "scripts" / "crew"
        self.manifest = Path(self.state) / "install.json"
        self.tool("git", 'case "$1" in --version) echo 1.0;; *) exit 1;; esac')

    def bootstrap(self, *args):
        return subprocess.run([sys.executable, str(self.cli), "bootstrap", "--project", self.project, *args],
                              input="", capture_output=True, text=True, env=self.env)

    def test_dry_run_and_confirmation_leave_no_install(self):
        r = self.bootstrap("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for text in ("Plan: v2.1.0 (tmux)", "Render preview:", "Human step:", "no install written"):
            self.assertIn(text, r.stdout)
        self.assertIn("render/runtime/coordinator.md (planned)", r.stdout)
        self.assertFalse(self.manifest.exists())
        self.assertFalse((Path(self.state) / "eng-crew").exists())
        r = self.bootstrap()
        self.assertEqual(r.returncode, 1)
        self.assertIn("confirmation required", r.stderr)
        self.assertFalse(self.manifest.exists())

    def test_apply_records_and_reruns_without_starting_tmux(self):
        # Real git is used only for .git/info/exclude and tracked-file checks.
        os.remove(Path(self.bindir) / "git")
        os.symlink(shutil.which("git"), Path(self.bindir) / "git")
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        for _ in range(2):
            r = self.bootstrap("--yes")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["tag"], record["runtime"], record["status"]), ("v2.1.0", "tmux", "installed"))
        self.assertEqual((Path(self.state) / "VERSION").read_text(), "v2.1.0\n")
        self.assertEqual((Path(self.state) / "crew.toml").read_text(), self.project_path.read_text())
        self.assertEqual((Path(self.state) / "eng-crew").resolve(), self.bundle.resolve())
        self.assertFalse((Path(self.state) / "render").exists())
        self.assertEqual((Path(self.project_dir) / ".git/info/exclude").read_text().count(".crew/"), 1)
        self.assertEqual(self.calls(), [])
        self.assertEqual(record["self_test"], dict(profile="ok", render="ok", briefs="ok",
                                                size_budget="ok", deploy="pending crew up", targets="ok", doctor="ok"))

    def missing_project(self, remote="git@github.com:acme/widgets.git"):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        subprocess.run(["git", "-C", self.project_dir, "remote", "add", "origin", remote], check=True)
        self.project_path.unlink()

    def test_proposes_from_local_config_without_writes_or_network(self):
        self.missing_project()
        real_git = Path(self.bindir) / "real-git"
        (Path(self.bindir) / "git").rename(real_git)
        log = Path(self.tmp) / "git-calls"
        self.tool("git", 'echo "$*" >> "%s"\nexec "%s" "$@"' % (log, real_git))
        for remote in ("git@github.com:acme/widgets.git", "https://github.com/acme/widgets.git",
                       "ssh://git@github.com/acme/widgets"):
            subprocess.run([str(real_git), "-C", self.project_dir, "config", "remote.origin.url", remote], check=True)
            r = self.bootstrap("--dry-run", "--runtime", "tmux")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            proposal = r.stdout.split("\n", 1)[1].split("Review identities", 1)[0]
            profile = tomllib.loads(proposal)
            self.assertEqual(profile["repo"], dict(owner="acme", name="widgets"))
            self.assertEqual(profile["runtime"]["name"], "tmux")
            self.assertEqual({p["name"] for p in profile["backends"].values()}, {"github"})
            self.assertEqual(profile["flavor"]["name"], "standard")
        self.assertTrue(all("config --local --get remote.origin.url" in line for line in log.read_text().splitlines()))
        self.assertFalse(self.project_path.exists())
        self.assertFalse(self.manifest.exists())
        self.assertEqual(self.calls(), [])

    def test_confirmation_accepts_and_keeps_record_when_origin_changes(self):
        self.missing_project()
        r = self.bootstrap()
        self.assertEqual(r.returncode, 1)
        self.assertIn("profile confirmation required", r.stderr)
        self.assertFalse(self.project_path.exists())
        r = self.bootstrap("--yes")
        self.assertIn("recorded profile", r.stdout)
        before = self.project_path.read_text()
        self.assertEqual(tomllib.loads(before)["runtime"]["name"], "grok-bot")
        self.assertEqual(tomllib.loads(before)["flavor"]["name"], "standard")
        subprocess.run(["git", "-C", self.project_dir, "config", "remote.origin.url", "https://example.invalid/elsewhere"], check=True)
        r = self.bootstrap("--yes", "--runtime", "tmux", "--flavor", "fast", "--proposal", "/missing")
        self.assertNotIn("Project proposal:", r.stdout)
        self.assertEqual(self.project_path.read_text(), before)

    def test_explicit_flavor_and_edited_unset_flavor(self):
        self.missing_project()
        r = self.bootstrap("--dry-run", "--flavor", "fast")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('name = "fast"', r.stdout)
        edited = Path(self.tmp) / "edited.toml"
        edited.write_text('[repo]\nowner = "acme"\nname = "widgets"\n[flavor]\ngoal = "quality"\n')
        r = self.bootstrap("--dry-run", "--proposal", str(edited))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count("[flavor]"), 1)

    def test_owner_edits_install_and_rerun_preserves_exact_profile(self):
        edited = Path(self.tmp) / "edited.toml"
        edited.write_text(self.project_path.read_text() + '\n[flavor]\nname = "thorough"\n')
        self.missing_project("https://example.invalid/unknown")
        r = self.bootstrap("--yes", "--proposal", str(edited))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.project_path.read_text(), edited.read_text())
        self.assertEqual((Path(self.state) / "crew.toml").read_text(), edited.read_text())
        self.assertEqual(json.loads(self.manifest.read_text())["status"], "installed")
        r = self.bootstrap("--yes", "--proposal", "/missing", "--flavor", "fast")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.project_path.read_text(), edited.read_text())

    def test_unknown_origin_and_bad_edit_do_not_record(self):
        self.missing_project("https://example.invalid/widgets")
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a recognized GitHub URL", r.stderr)
        edited = Path(self.tmp) / "bad.toml"
        edited.write_text("[invalid")
        r = self.bootstrap("--yes", "--proposal", str(edited))
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.project_path.exists())

    def test_terminal_edit_requires_confirmation_of_edited_proposal(self):
        edited = Path(self.tmp) / "edited.toml"
        edited.write_text(self.project_path.read_text())
        self.missing_project()
        loader = importlib.machinery.SourceFileLoader("proposal_cli", str(self.cli))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("proposal_cli", loader))
        loader.exec_module(mod)
        bootstrap = mod.commands()["bootstrap"]
        parser = mod.argparse.ArgumentParser()
        bootstrap.register(parser.add_subparsers())
        args = parser.parse_args(["bootstrap", "--project", self.project])
        with mock.patch.dict(os.environ, self.env), mock.patch("sys.stdin.isatty", return_value=True), \
                mock.patch("builtins.input", side_effect=[str(edited), "y"]) as prompt, \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertTrue(bootstrap.propose_project(args, self.project_path))
        self.assertEqual(prompt.call_count, 2)
        self.assertEqual(tomllib.loads(self.project_path.read_text())["runtime"]["name"], "tmux")

    def test_render_notes_count_toward_size_budget(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        (self.bundle / "templates/runtimes/tmux/builder.md").write_text("é" * 8000)
        (Path(self.project_dir) / "note.md").write_text("n" * 400)
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.project_path.write_text(self.project_path.read_text() +
                                     '\n[runtime.options.notes.render]\nbuilder = ["note.md"]\n')
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("runtime/builder.md: 16426 path-normalized UTF-8 bytes exceeds builder budget 16384 bytes", r.stdout)
        self.assertEqual(json.loads(self.manifest.read_text())["self_test"]["size_budget"], "fail")

    def test_size_budget_under_at_over_and_default(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        for runtime in ("tmux", "grok-bot"):
            with self.subTest(runtime=runtime):
                text = self.project_path.read_text().replace('name = "tmux"', 'name = "%s"' % runtime)
                self.project_path.write_text(text)
                name = "builder" if runtime == "tmux" else "builder-b2"
                path = self.bundle / "templates/runtimes" / runtime / (name + ".md")
                # UTF-8 bytes, not characters: 16 KiB at the default budget.
                path.write_text("é" * 8192)
                r = self.bootstrap("--yes")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(json.loads(self.manifest.read_text())["self_test"]["size_budget"], "ok")
                self.project_path.write_text(text + "\n[size_budget]\nbuilder = 16385\n")
                self.assertEqual(self.bootstrap("--yes").returncode, 0)
                path.write_text("é" * 8193)
                r = self.bootstrap("--yes")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("runtime/%s.md: 16386 path-normalized UTF-8 bytes exceeds builder budget 16385 bytes" % name, r.stdout)
                record = json.loads(self.manifest.read_text())
                self.assertEqual((record["status"], record["self_test"]["size_budget"]), ("failed", "fail"))
                # Reset the install before testing the other runtime.
                for target in record["targets"]:
                    Path(target).unlink()
                (Path(self.state) / "eng-crew").unlink()
                self.manifest.unlink()
                self.project_path.write_text(text.replace('name = "grok-bot"', 'name = "tmux"'))

    def test_size_budget_covers_core_and_every_role_owned_file(self):
        loader = importlib.machinery.SourceFileLoader("budget_cli", str(self.cli))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("budget_cli", loader))
        loader.exec_module(mod)
        bootstrap = mod.commands()["bootstrap"]
        rendered = Path(self.tmp) / "rendered"
        names = ["briefs/builder.md", "runtime/coordinator-steering-dispatcher.md",
                 "runtime/reviewer-engines.md", "runtime/synthesizer.md"]
        for name in names + ["runtime/wiring.md"]:
            path = rendered / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x" * 11)
        values = {"size_budget." + role: 10 for role in ("coordinator", "builder", "reviewer", "synthesizer")}
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(bootstrap.size_budget(rendered, values), 1)
        for name in names:
            self.assertIn(name + ": 11 path-normalized UTF-8 bytes exceeds", out.getvalue())
        self.assertNotIn("wiring", out.getvalue())

    def test_size_budget_is_independent_of_install_paths(self):
        loader = importlib.machinery.SourceFileLoader("normalized_cli", str(self.cli))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("normalized_cli", loader))
        loader.exec_module(mod)
        renderer = mod.crew_render
        bootstrap = mod.commands()["bootstrap"]
        for runtime in ("tmux", "grok-bot"):
            counts = []
            for root in ("/a", "/very-long-install-root/" + "nested/" * 40):
                project = Path(self.tmp) / "budget.toml"
                project.write_text('[runtime]\nname = "%s"\n[paths]\n' % runtime + "".join(
                    '%s = "%s/%s"\n' % (key, root, key)
                    for key in ("state_dir", "worktree_root", "eng_crew", "toolchain_bin", "live_dir")))
                rendered = Path(self.tmp) / "normalized"
                with mock.patch("sys.stdout", new_callable=io.StringIO), mock.patch("sys.stderr", new_callable=io.StringIO):
                    self.assertEqual(renderer.main(["--project", str(project), "--out", str(rendered)],
                                                   normalize_paths=True), 0)
                counts.append({str(p.relative_to(rendered)): len(p.read_bytes())
                               for p in rendered.rglob("*.md")})
                values, problems = renderer.resolve(str(project), None)
                self.assertEqual(problems, [])
                self.assertEqual(bootstrap.size_budget(rendered, values), 0)
                values["size_budget.coordinator"] = 1
                with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                    self.assertEqual(bootstrap.size_budget(rendered, values), 1)
                self.assertIn("path-normalized UTF-8 bytes exceeds coordinator budget 1 bytes", out.getvalue())
                shutil.rmtree(rendered)
            self.assertEqual(counts[0], counts[1], runtime)
            if runtime == "tmux":
                for role in ("coordinator", "synthesizer"):
                    self.assertLessEqual(counts[0]["runtime/" + role + ".md"], 16384 - 1024)

    def test_missing_brief_records_failed_self_test(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        (self.bundle / "templates/runtimes/tmux/reviewer.md").unlink()
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("self-test failed: briefs", r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["self_test"]["briefs"], "fail")

    def test_post_apply_doctor_failure_is_recorded(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        counter = Path(self.tmp) / "claude-calls"
        self.tool("claude", 'echo call >> "%s"\n[ "$(wc -l < "%s")" -lt 3 ] && echo 1.0' %
                  (counter, counter))
        # The fake PATH has no wc; use the host tool without changing the fixture PATH.
        os.symlink(shutil.which("wc"), Path(self.bindir) / "wc")
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["self_test"]["doctor"], "fail")

    def test_deploy_drift_and_target_hash_failure(self):
        loader = importlib.machinery.SourceFileLoader("bootstrap_cli", str(self.cli))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("bootstrap_cli", loader))
        loader.exec_module(mod)
        bootstrap = mod.commands()["bootstrap"]
        live = Path(self.state) / "render"
        target = Path(self.tmp) / "target"
        target.write_text("installed\n")
        record = dict(runtime="tmux", targets={str(target): bootstrap.digest(target)})
        argv = ["--project", self.project, "--out", str(live)]
        with mock.patch.dict(os.environ, self.env), mock.patch.object(bootstrap.commands()["doctor"], "run", return_value=0):
            self.assertEqual(bootstrap.crew_render.main(argv), 0)
            doctor = bootstrap.commands()["doctor"]
            checks = bootstrap.self_test(self.project_path, None, live, record, doctor)
            self.assertEqual(set(checks.values()), {"ok"})
            (live / "runtime/reviewer.md").write_text("drift\n")
            target.write_text("changed\n")
            checks = bootstrap.self_test(self.project_path, None, live, record, doctor)
            self.assertEqual((checks["deploy"], checks["targets"]), ("fail", "fail"))

    def smoke_host(self):
        self.real_git()
        os.symlink(sys.executable, Path(self.bindir) / "python3")
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        self.issue_log = Path(self.tmp) / "issues"
        gh = Path(self.bindir) / "gh"
        text = gh.read_text().replace('*) exit 1;;',
            '"issue create") echo "$*" >> "%s"\n%s\n;;\n*) exit 1;;' %
            (self.issue_log, 'echo https://github.com/acme/widgets/issues/123'))
        gh.write_text(text)
        Path(self.state_file).write_text(json.dumps({"crew-acme-widgets": {"0": "ash"}}))

    def test_smoke_is_opt_in_dry_run_safe_and_queued_once(self):
        self.smoke_host()
        for flags in (("--dry-run", "--smoke"), ("--yes",)):
            r = self.bootstrap(*flags)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse(self.issue_log.exists())
            self.assertEqual(self.calls(), [])
        for _ in range(2):
            r = self.bootstrap("--yes", "--smoke")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.issue_log.read_text().splitlines()), 1)
        self.assertIn("--label crew:ready --assignee acme-bot", self.issue_log.read_text())
        record = json.loads(self.manifest.read_text())
        self.assertEqual(record["smoke"], dict(issue="https://github.com/acme/widgets/issues/123", status="queued"))
        self.assertEqual(self.calls(), [["has-session", "-t", "=crew-acme-widgets"]])

    def test_smoke_requires_started_tmux_and_records_creation_failure(self):
        self.smoke_host()
        Path(self.state_file).unlink()
        r = self.bootstrap("--yes", "--smoke")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("requires a started crew", r.stderr)
        self.assertFalse(self.issue_log.exists())
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["status"], record["self_test"]["smoke"]), ("failed", "fail"))
        Path(self.state_file).write_text(json.dumps({"crew-acme-widgets": {"0": "ash"}}))
        gh = Path(self.bindir) / "gh"
        gh.write_text(gh.read_text().replace('echo https://github.com/acme/widgets/issues/123', 'exit 1'))
        r = self.bootstrap("--yes", "--smoke")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("smoke issue creation failed", r.stderr)
        self.assertNotIn("smoke", json.loads(self.manifest.read_text()))

    def test_grok_deploys_and_refuses_edited_targets(self):
        self.project_path.write_text(self.project_path.read_text().replace('name = "tmux"', 'name = "grok-bot"'))
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        live = Path(self.tmp) / "live"
        files = list(live.rglob("*.md"))
        self.assertTrue(files)
        self.assertEqual(self.bootstrap("--yes").returncode, 0)
        files[0].write_text("owner edit\n")
        before = self.manifest.read_text()
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("target edited or unowned", r.stderr)
        self.assertEqual(files[0].read_text(), "owner edit\n")
        self.assertEqual(self.manifest.read_text(), before)

    def test_grok_triage_enabled_reports_no_timer(self):
        text = self.project_path.read_text().replace('name = "tmux"', 'name = "grok-bot"')
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.project_path.write_text(text + "\n[triage]\nenabled = %s\n" % str(enabled).lower())
                r = self.bootstrap("--dry-run")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                note = "Triage: triage.enabled installs no Grok timer; triage stays coordinator dispositions"
                (self.assertIn if enabled else self.assertNotIn)(note, r.stdout)
                self.assertRegex(r.stdout, r"(?m)^%s +triage " % ("warn" if enabled else "ok"))
                self.assertNotRegex(r.stdout.lower(), r"timer (installed|created)|install(ed|ing) (a|the) .*timer")

    def test_failures_do_not_write_install(self):
        for version in (None, "v2.2.0-rc.1"):
            path = self.bundle / "VERSION"
            if version is None:
                path.unlink()
            else:
                path.write_text(version)
            self.assertEqual(self.bootstrap("--yes").returncode, 1)
            self.assertFalse(self.manifest.exists())
        (self.bundle / "VERSION").write_text("v2.1.0\n")
        os.remove(Path(self.bindir) / "claude")
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Plan:", r.stdout)
        self.assertFalse(self.manifest.exists())

    def test_placeholder_and_resolve_failures(self):
        self.project_path.write_text(self.project_path.read_text().replace('eng_crew = "' + self.state + '/eng-crew"',
                                                                         'eng_crew = "<eng-crew>"'))
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("placeholder", r.stderr)
        self.project_path.write_text("[repo]\nowner = 1\n")
        self.assertEqual(self.bootstrap("--yes").returncode, 1)
        self.assertFalse(self.manifest.exists())

    def real_git(self):
        os.remove(Path(self.bindir) / "git")
        os.symlink(shutil.which("git"), Path(self.bindir) / "git")

    def test_clone_requires_exact_stable_tag_or_explicit_dev(self):
        self.real_git()
        argv = ["git", "-C", str(self.bundle), "-c", "user.name=t", "-c", "user.email=t"]
        for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "base"]):
            subprocess.run(argv + args, check=True)
        self.assertEqual(self.bootstrap("--dry-run").returncode, 1)
        sha = subprocess.check_output(argv + ["rev-parse", "HEAD"], text=True).strip()
        r = self.bootstrap("--dev", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Plan: " + sha, r.stdout)
        subprocess.run(argv + ["tag", "v2.1.0"], check=True)
        self.assertEqual(self.bootstrap("--dry-run").returncode, 0)

    def test_missing_state_layout_fails_before_plan(self):
        shutil.rmtree(Path(self.state) / "inbox")
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("fail  state dir", r.stdout)
        self.assertNotIn("Plan:", r.stdout)
        self.assertFalse((Path(self.state) / "inbox").exists())
        self.assertFalse(self.manifest.exists())

    def test_missing_repo_labels_fail_before_install(self):
        self.tool("gh", 'case "$1 $2" in\n"auth token") echo fixture-token;;\n'
                  '"api repos/acme/widgets/labels?per_page=100") echo \'[[]]\';;\n*) exit 1;;\nesac')
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("fail  crew labels", r.stdout)
        self.assertNotIn("Plan:", r.stdout)
        self.assertFalse(self.manifest.exists())

    def test_tracked_target_is_not_overwritten(self):
        self.real_git()
        live = Path(self.tmp) / "live"
        live.mkdir()
        self.project_path.write_text(self.project_path.read_text().replace('name = "tmux"', 'name = "grok-bot"'))
        subprocess.run(["git", "init", "-q", str(live)], check=True)
        target = live / "runtime" / "builder-b1.md"
        target.parent.mkdir()
        target.write_text("tracked owner content\n")
        subprocess.run(["git", "-C", str(live), "add", "runtime/builder-b1.md"], check=True)
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(target.read_text(), "tracked owner content\n")
        self.assertFalse(self.manifest.exists())


    def release(self, tag="v2.2.0", checksum=True, version=None, unsafe=False):
        assets = Path(self.tmp) / "assets"
        assets.mkdir(exist_ok=True)
        name = "eng-crew-" + tag[1:]
        archive = assets / (name + ".tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            for path in sorted(self.bundle.rglob("*")):
                if path.is_file():
                    data = ((version or tag) + "\n").encode() if path.name == "VERSION" else path.read_bytes()
                    info = tarfile.TarInfo(name + "/" + str(path.relative_to(self.bundle)))
                    info.mode, info.size = path.stat().st_mode & 0o777, len(data)
                    tar.addfile(info, io.BytesIO(data))
            if unsafe:
                info = tarfile.TarInfo(name + "/../../escape")
                tar.addfile(info, io.BytesIO())
        sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        (assets / "SHA256SUMS").write_text((sha if checksum else "0" * 64) + "  " + archive.name + "\n")
        original = Path(self.bindir) / "gh-doctor"
        if not original.exists():
            (Path(self.bindir) / "gh").rename(original)
        self.tool("gh", "exec %s - \"$@\" <<'PY'\n" % sys.executable +
                  "import json, os, pathlib, shutil, sys\n"
                  "args = sys.argv[1:]\n"
                  "if args[:2] != ['release', 'download']:\n"
                  "    os.execv(%r, [%r] + args)\n" % (str(original), str(original)) +
                  "pathlib.Path(%r).write_text(json.dumps(args))\n" % str(assets / "argv.json") +
                  "for name in %r:\n" % [archive.name, "SHA256SUMS"] +
                  "    shutil.copyfile(pathlib.Path(%r) / name, pathlib.Path(args[args.index('--dir')+1]) / name)\n"
                  "PY" % str(assets))
        return Path(self.tmp) / name, sha

    def org(self, pin):
        org = Path(self.tmp) / "org"
        org.mkdir(exist_ok=True)
        (org / "profile.toml").write_text("")
        manifest = (HERE.parent / "packs/github/manifest.toml").read_text()
        (org / "manifest.toml").write_text(manifest.replace('[pack]\n',
                                                          '[pack]\neng_crew_version = "%s"\n' % pin))
        return str(org / "profile.toml")

    def test_fetch_verifies_runs_selected_bundle_and_records_digest(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        destination, sha = self.release()
        r = self.bootstrap("--version", "v2.2.0", "--yes", "--org-profile", self.org("v2.2.0"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["tag"], record["source"], record["bundle_sha256"]),
                         ("v2.2.0", str(destination.resolve()), sha))
        self.assertEqual((Path(self.state) / "eng-crew").resolve(), destination.resolve())
        self.assertEqual((self.bundle / "VERSION").read_text(), "v2.1.0\n")
        argv = json.loads((Path(self.tmp) / "assets/argv.json").read_text())
        self.assertEqual(argv[:5], ["release", "download", "v2.2.0", "-R", "mw-ding/eng-crew"])
        self.assertIn("eng-crew-2.2.0.tar.gz", argv)
        self.assertIn("SHA256SUMS", argv)
        self.cli = destination / "scripts/crew"
        self.assertEqual(self.bootstrap("--yes").returncode, 0)
        self.assertEqual(json.loads(self.manifest.read_text())["bundle_sha256"], sha)

    def test_recorded_pack_pin_is_checked(self):
        org = self.org("v2.1.0")
        directory = os.path.relpath(Path(org).parent, self.project_path.parent)
        self.project_path.write_text(self.project_path.read_text() + 'pack = "%s"\n' % directory)
        self.assertEqual(self.bootstrap("--dry-run").returncode, 0)
        self.org("v2.2.0")
        result = self.bootstrap("--dry-run")
        self.assertEqual(result.returncode, 1)
        self.assertIn("pack.eng_crew_version must equal the stable installed tag v2.1.0", result.stderr)

    def pack_version(self, version):
        org = Path(self.org("v2.1.0"))
        if version:
            manifest = org.parent / "manifest.toml"
            manifest.write_text(manifest.read_text().replace('[pack]\n', '[pack]\nversion = "%s"\n' % version))
        if "pack = " not in self.project_path.read_text():
            self.project_path.write_text(self.project_path.read_text() +
                                         'pack = "%s"\n' % os.path.relpath(org.parent, self.project_path.parent))

    def test_pack_version_recorded_only_when_declared(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        self.pack_version("0.5.0")
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["tag"], record["pack"]), ("v2.1.0", {"name": "github", "version": "0.5.0"}))
        self.pack_version(None)
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("pack", json.loads(self.manifest.read_text()))

    def test_pack_overlay_renders_in_bootstrap_and_upgrade(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        pack = Path(self.tmp) / "pack"
        write_pack(pack)
        self.project_path.write_text(self.project_path.read_text() +
                                     'pack = "%s"\n' % os.path.relpath(pack, self.project_path.parent))
        r = self.bootstrap("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("render/runtime/solo.md (planned)", r.stdout)
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self_test = json.loads(self.manifest.read_text())["self_test"]
        self.assertEqual((self_test["render"], self_test["size_budget"], self_test["briefs"]), ("ok", "ok", "ok"))
        self.assertNotIn("fail", self_test.values())
        r = subprocess.run([sys.executable, str(self.cli), "upgrade", "--project", self.project, "--yes"],
                           input="", capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        runtime = Path(self.state) / "render/runtime"
        self.assertTrue((runtime / "solo.md").read_text().endswith("\nPack rule.\n"))
        self.assertIn("to every `ex` command except\n`gh api`", (runtime / "builder.md").read_text())

    def test_fetch_preserves_smoke_opt_in_and_self_tests(self):
        self.smoke_host()
        destination, sha = self.release()
        r = self.bootstrap("--version", "v2.2.0", "--yes", "--smoke")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["tag"], record["bundle_sha256"], record["status"]),
                         ("v2.2.0", sha, "installed"))
        self.assertEqual(record["self_test"]["briefs"], "ok")
        self.assertEqual(record["smoke"]["status"], "queued")
        self.assertEqual(len(self.issue_log.read_text().splitlines()), 1)
        self.assertEqual((Path(self.state) / "eng-crew").resolve(), destination.resolve())

    def test_fetch_dry_run_preserves_live_install_and_existing_versions(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        self.assertEqual(self.bootstrap("--yes").returncode, 0)
        previous = self.manifest.read_text()
        destination, _ = self.release()
        r = self.bootstrap("--version", "v2.2.0", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Plan: v2.2.0", r.stdout)
        self.assertTrue(destination.is_dir())
        self.assertEqual(self.manifest.read_text(), previous)
        self.assertEqual((Path(self.state) / "eng-crew").resolve(), self.bundle.resolve())
        marker = destination / "owner-file"
        marker.write_text("preserve")
        r = self.bootstrap("--version", "v2.2.0", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("already exists", r.stderr)
        self.assertEqual(marker.read_text(), "preserve")

    def test_fetch_rejects_checksum_version_and_unsafe_archive_before_publish(self):
        for options, message in ((dict(checksum=False), "SHA256SUMS mismatch"),
                                 (dict(version="v9.9.9"), "VERSION"),
                                 (dict(unsafe=True), "unsafe release archive")):
            destination, _ = self.release(**options)
            r = self.bootstrap("--version", "v2.2.0", "--yes")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(message, r.stderr)
            self.assertFalse(destination.exists())
            self.assertFalse(self.manifest.exists())
            self.assertFalse(list(Path(self.tmp).glob(".crew-fetch-*")))
        self.assertFalse((Path(self.tmp) / "escape").exists())

    def test_prereleases_need_pre_and_never_satisfy_pin(self):
        destination, _ = self.release(tag="v2.2.0-rc.1")
        r = self.bootstrap("--version", "v2.2.0-rc.1", "--dry-run")
        self.assertEqual(r.returncode, 1)
        self.assertIn("require --pre", r.stderr)
        self.assertFalse(destination.exists())
        r = self.bootstrap("--version", "v2.2.0-rc.1", "--pre", "--dry-run",
                           "--org-profile", self.org("v2.2.0-rc.1"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("pack.eng_crew_version", r.stderr)
        self.assertFalse(destination.exists())
        r = self.bootstrap("--version", "v2.2.0-rc.1", "--pre", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Plan: v2.2.0-rc.1", r.stdout)
        (self.bundle / "VERSION").write_text("v2.1.0-rc.1\n")
        self.assertEqual(self.bootstrap("--pre", "--dry-run").returncode, 0)

    def test_pack_pin_and_invalid_flags_fail_before_download(self):
        for flags in (("--version", "v2.2.0", "--org-profile", self.org("v2.1.0")),
                      ("--org-profile", self.org("v9.9.9")),
                      ("--version", "../../escape"), ("--version", "v2.2.0", "--dev")):
            r = self.bootstrap(*flags, "--dry-run")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertFalse(self.manifest.exists())
        org = self.org("v2.1.0")
        (Path(org).parent / "manifest.toml").unlink()
        self.assertEqual(self.bootstrap("--org-profile", org, "--dry-run").returncode, 1)
        self.assertEqual(self.bootstrap("--version", "v2.2.0", "--dry-run").returncode, 1)



class ReleaseSources(Bootstrap):
    """url and mirror [install] sources (docs/bootstrap.md Release sources, #944): no gh release call, the shared
    verifier and the install.json transport record."""

    def setUp(self):
        super().setUp()
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        self.mirror = Path(self.tmp) / "mirror"
        self.gh_log = Path(self.tmp) / "gh.log"

    def mirror_release(self, tag="v2.2.0", sums=None, **options):
        """Publish the release under mirror/<tag>/ and make any gh release call fail and leave a log line."""
        destination, sha = self.release(tag, **options)
        assets, where = Path(self.tmp) / "assets", self.mirror / tag
        where.mkdir(parents=True, exist_ok=True)
        archive = "eng-crew-%s.tar.gz" % tag[1:]
        shutil.copyfile(assets / archive, where / archive)
        (where / "SHA256SUMS").write_text(sums(sha, archive) if sums else (assets / "SHA256SUMS").read_text())
        self.tool("gh", 'case "$1" in release) echo "$@" >> %s; exit 1;; esac\nexec %s "$@"' %
                  (self.gh_log, Path(self.bindir) / "gh-doctor"))
        return destination, sha

    def source(self, kind, location, **keys):
        text = '\n[install]\nsource = "%s"\nlocation = "%s"\n' % (kind, location)
        text += "".join('%s = "%s"\n' % item for item in keys.items())
        self.project_path.write_text(self.project_path.read_text() + text)

    def test_mirror_fetch_records_transport_and_never_calls_gh_release(self):
        destination, sha = self.mirror_release()
        self.source("mirror", self.mirror)
        r = self.bootstrap("--version", "v2.2.0", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("latest not checked (source mirror)", r.stdout)
        record = json.loads(self.manifest.read_text())
        sums = hashlib.sha256((self.mirror / "v2.2.0/SHA256SUMS").read_bytes()).hexdigest()
        self.assertEqual((record["tag"], record["source"], record["bundle_sha256"]),
                         ("v2.2.0", str(destination.resolve()), sha))
        self.assertEqual(record["transport"], {"kind": "mirror", "location": str(self.mirror),
                                               "sha256sums_sha256": sums, "pinned": False})
        self.assertEqual((Path(self.state) / "eng-crew").resolve(), destination.resolve())
        self.cli = destination / "scripts/crew"
        self.assertEqual(self.bootstrap("--yes").returncode, 0)
        self.assertEqual(json.loads(self.manifest.read_text())["transport"], record["transport"])
        r = subprocess.run([sys.executable, str(self.cli), "doctor", "--project", self.project],
                           capture_output=True, text=True, env=self.env)
        self.assertIn("install source     mirror %s; bundle sha256 %s" % (self.mirror, sha), r.stdout)
        self.assertFalse(self.gh_log.exists())

    def test_url_fetch_from_local_http_server_with_pin(self):
        destination, sha = self.mirror_release()
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(self.mirror))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = "http://127.0.0.1:%d/releases" % server.server_port
        (self.mirror / "releases").symlink_to(self.mirror, target_is_directory=True)
        pin = hashlib.sha256((self.mirror / "v2.2.0/SHA256SUMS").read_bytes()).hexdigest()
        self.source("url", url, sha256sums_digest=pin)
        r = self.bootstrap("--version", "v2.2.0", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["bundle_sha256"], record["transport"]),
                         (sha, {"kind": "url", "location": url, "sha256sums_sha256": pin, "pinned": True}))
        self.assertFalse(self.gh_log.exists())

    def test_refused_release_keeps_previous_install(self):
        self.assertEqual(self.bootstrap("--yes").returncode, 0)
        previous = self.manifest.read_bytes()
        cases = (
            (dict(checksum=False), {}, "SHA256SUMS mismatch"),
            (dict(sums=lambda sha, name: ""), {}, "SHA256SUMS mismatch or missing entry"),
            (dict(sums=lambda sha, name: "%s  %s\n%s  %s\n" % (sha, name, sha, name)), {}, "missing entry"),
            (dict(), {"sha256sums_digest": "0" * 64}, "does not match the pinned sha256sums_digest"),
            (dict(version="v9.9.9"), {}, "VERSION"),
            (dict(unsafe=True), {}, "unsafe release archive"),
        )
        for options, keys, message in cases:
            with self.subTest(message=message):
                self.project_path.write_text(self.project_path.read_text().split("\n[install]\n")[0])
                destination, _ = self.mirror_release(**options)
                self.source("mirror", self.mirror, **keys)
                r = self.bootstrap("--version", "v2.2.0", "--yes")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(message, r.stderr)
                self.assertFalse(destination.exists())
                self.assertEqual(self.manifest.read_bytes(), previous)
                self.assertEqual((Path(self.state) / "eng-crew").resolve(), self.bundle.resolve())
                self.assertFalse(list(Path(self.tmp).glob(".crew-fetch-*")))
        self.assertFalse((Path(self.tmp) / "escape").exists())
        self.assertFalse(self.gh_log.exists())

    def test_missing_release_fails_before_extraction(self):
        self.mirror_release()
        self.source("mirror", self.mirror)
        r = self.bootstrap("--version", "v2.3.0", "--dry-run")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("release fetch failed for v2.3.0 from mirror", r.stderr)
        self.assertFalse((Path(self.tmp) / "eng-crew-2.2.0").exists())
        self.assertFalse(self.gh_log.exists())

    def git_release(self, tag="v2.2.0"):
        """A local bare repository whose commit's stub release-bundle.py emits the fixture archive; tag at it."""
        destination, sha = self.mirror_release(tag)
        os.symlink(shutil.which("git-upload-pack"), Path(self.bindir) / "git-upload-pack")
        work, remote = Path(self.tmp) / "git-work", Path(self.tmp) / "release.git"
        stub = "import shutil, sys\nshutil.copy(%r, sys.argv[sys.argv.index('--out') + 1])\n" % str(
            Path(self.tmp) / "assets" / ("eng-crew-%s.tar.gz" % tag[1:]))
        (work / "scripts").mkdir(parents=True)
        (work / "scripts/release-bundle.py").write_text(stub)
        git = ["git", "-c", "user.name=t", "-c", "user.email=t"]
        subprocess.run(git + ["init", "-q", "--bare", str(remote)], check=True)
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "release"], ["tag", tag],
                     ["push", "-q", str(remote), "refs/tags/" + tag]):
            subprocess.run(git + ["-C", str(work)] + args, check=True)
        commit = subprocess.check_output(git + ["-C", str(work), "rev-parse", "HEAD"], text=True).strip()
        return destination, sha, remote, commit

    def test_git_source_builds_the_pinned_commit_and_records_it(self):
        destination, sha, remote, commit = self.git_release()
        self.source("git", remote, git_commit=commit)
        r = self.bootstrap("--version", "v2.2.0", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("verified v2.2.0 commit=%s sha256=%s" % (commit, sha), r.stdout)
        self.assertIn("latest not checked (source git)", r.stdout)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["source"], record["bundle_sha256"], record["transport"]),
                         (str(destination.resolve()), sha, {"kind": "git", "location": str(remote), "commit": commit}))
        r = subprocess.run([sys.executable, str(destination / "scripts/crew"), "doctor", "--project", self.project],
                           capture_output=True, text=True, env=self.env)
        self.assertIn("install source     git %s; bundle sha256 %s; commit %s" % (remote, sha, commit), r.stdout)
        self.assertFalse(self.gh_log.exists())

    def test_git_source_refuses_a_tag_off_the_pin(self):
        self.assertEqual(self.bootstrap("--yes").returncode, 0)
        previous = self.manifest.read_bytes()
        destination, _, remote, commit = self.git_release()
        self.source("git", remote, git_commit="a" * 40)
        r = self.bootstrap("--version", "v2.2.0", "--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("resolves to %s, not the pinned git_commit %s" % (commit, "a" * 40), r.stderr)
        self.assertFalse(destination.exists())
        self.assertEqual(self.manifest.read_bytes(), previous)
        self.assertFalse(list(Path(self.tmp).glob(".crew-fetch-*")))
        self.assertFalse(self.gh_log.exists())


class HarnessTargets(Bootstrap):
    def setUp(self):
        super().setUp()
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        self.claude = Path(self.project_dir) / ".claude"
        self.exclude = Path(self.project_dir) / ".git/info/exclude"

    def test_fetch_preserves_harness_selection_and_self_tests(self):
        destination, sha = self.release()
        r = self.bootstrap("--version", "v2.2.0", "--harness", "claude-code",
                           "--harness", "codex", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual(record["source"], str(destination.resolve()))
        self.assertEqual(record["bundle_sha256"], sha)
        self.assertEqual(record["harnesses"], ["claude-code", "codex"])
        self.assertEqual(len(record["launches"]), 1)
        self.assertEqual(set(record["self_test"].values()), {"ok"})
        self.assertTrue((self.claude / "skills/crew-coordinator/SKILL.md").is_file())
        for path in self.claude.rglob("*"):
            if path.is_file():
                self.assertIn(str(path), record["targets"])
                self.assertIn("/" + str(path.relative_to(self.project_dir)), self.exclude.read_text().splitlines())
        self.cli = destination.resolve() / "scripts/crew"
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(self.manifest.read_text()), record)

    def test_harness_plan_and_repeat_install(self):
        before = self.exclude.read_text()
        flags = ("--harness", "claude-code", "--harness", "codex")
        r = self.bootstrap(*flags, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("crew-coordinator/SKILL.md (planned)", r.stdout)
        self.assertIn("Codex launch", r.stdout)
        self.assertIn('trust_level="trusted"', r.stdout)
        self.assertFalse(self.claude.exists())
        self.assertFalse((Path(self.state) / "render").exists())
        self.assertEqual(self.exclude.read_text(), before)
        r = self.bootstrap(*flags, "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual(set(record["self_test"].values()), {"ok"})
        files = list(self.claude.rglob("*"))
        files = [p for p in files if p.is_file()]
        self.assertEqual(len(files), 5)
        for path in files:
            self.assertIn(str(path), record["targets"])
            self.assertIn("/" + str(path.relative_to(self.project_dir)), self.exclude.read_text().splitlines())
            if path.suffix == ".md":
                pointer = path.read_text().split("Read your brief at ")[1].split(" and follow it.")[0]
                self.assertTrue(Path(pointer).is_file())
                self.assertLess(len(path.read_text().splitlines()), 9)
        self.assertIn("runtime/coordinator.md", record["launches"][0])
        settings = json.loads((self.claude / "settings.local.json").read_text())
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertNotIn("harness_pointers", record)
        before = {p: p.read_bytes() for p in files}
        excluded = self.exclude.read_text()
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(self.manifest.read_text()), record)
        self.assertEqual({p: p.read_bytes() for p in files}, before)
        self.assertEqual(self.exclude.read_text(), excluded)
        self.assertEqual(self.calls(), [])

    def test_codex_installs_no_project_files(self):
        before = {p: p.read_bytes() for p in Path(self.home).rglob("*") if p.is_file()}
        for name in ("AGENTS.md", "CLAUDE.md"):
            (Path(self.project_dir) / name).write_text("owner instructions\n")
        subprocess.run(["git", "-C", self.project_dir, "add", "AGENTS.md", "CLAUDE.md"], check=True)
        r = self.bootstrap("--harness", "codex", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.claude.exists())
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertEqual((Path(self.project_dir) / name).read_text(), "owner instructions\n")
        self.assertEqual({p: p.read_bytes() for p in Path(self.home).rglob("*") if p.is_file()}, before)
        self.assertTrue((Path(self.state) / "render/runtime/coordinator.md").is_file())

    def test_tracked_edited_and_symlink_targets_are_preserved(self):
        target = self.claude / "agents/crew-builder.md"
        target.parent.mkdir(parents=True)
        target.write_text("tracked\n")
        subprocess.run(["git", "-C", self.project_dir, "add", str(target)], check=True)
        for flags in (("--dry-run",), ("--yes",)):
            r = self.bootstrap("--harness", "claude-code", *flags)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(target.read_text(), "tracked\n")
            self.assertFalse(self.manifest.exists())
        subprocess.run(["git", "-C", self.project_dir, "rm", "-f", str(target)], check=True,
                       capture_output=True)
        target.parent.parent.mkdir(parents=True, exist_ok=True)
        target.parent.symlink_to(self.home, target_is_directory=True)
        r = self.bootstrap("--harness", "claude-code", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("symlink", r.stderr)
        self.assertFalse((Path(self.home) / target.name).exists())
        target.parent.unlink()
        r = self.bootstrap("--harness", "claude-code", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        target.write_text("owner edit\n")
        before = self.manifest.read_text()
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("target edited or unowned", r.stderr)
        self.assertEqual(target.read_text(), "owner edit\n")
        self.assertEqual(self.manifest.read_text(), before)

    def registry(self, entries, files=None):
        """A pack whose pack.harness registry holds entries (TOML), with files written in the pack; its path."""
        pack = Path(self.tmp) / "pack"
        write_pack(pack)
        manifest = pack / "manifest.toml"
        manifest.write_text(manifest.read_text().replace("[pack]\n", '[pack]\nharness = "harness.toml"\n'))
        (pack / "harness.toml").write_text(entries)
        for name, text in (files or {}).items():
            (pack / name).parent.mkdir(parents=True, exist_ok=True)
            (pack / name).write_bytes(text.encode())
        if "pack = " not in self.project_path.read_text():
            self.project_path.write_text(self.project_path.read_text() +
                                         'pack = "%s"\n' % os.path.relpath(pack, self.project_path.parent))
        return pack

    REGISTRY = """[[pointer]]
harness = "claude-code"
target = ".claude/skills/org-tool/SKILL.md"
source = "harness/tool.md"
[[pointer]]
harness = "claude-code"
target = "docs/org/venue.md"
source = "harness/venue.md"
mode = "pointer"
[[pointer]]
harness = "codex"
target = ".codex/org.md"
source = "harness/venue.md"
mode = "pointer"
[[pointer]]
harness = "codex"
launch_note = "harness/codex-note.md"
"""
    FILES = {"harness/tool.md": "---\nname: org-tool\n---\r\nRun org-tool.\n", "harness/venue.md": "Venue.\n",
             "harness/codex-note.md": "Note.\n"}

    def test_registry_copy_pointer_and_launch_note(self):
        pack = self.registry(self.REGISTRY, self.FILES).resolve()
        root = Path(self.project_dir)
        flags = ("--harness", "claude-code", "--harness", "codex")
        before = self.exclude.read_text()
        r = self.bootstrap(*flags, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for line in (".claude/skills/org-tool/SKILL.md (planned)", "+Read %s/harness/venue.md and follow it." % pack,
                     "Repo operation: add /docs/org/venue.md to .git/info/exclude",
                     "Repo operation: add /.codex/org.md to .git/info/exclude",
                     " Then read %s/harness/codex-note.md and follow it." % pack):
            self.assertIn(line, r.stdout)
        self.assertFalse((root / "docs").exists())
        self.assertEqual(self.exclude.read_text(), before)
        r = self.bootstrap(*flags, "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual(set(record["self_test"].values()), {"ok"})
        copy = root / ".claude/skills/org-tool/SKILL.md"
        self.assertEqual(copy.read_bytes(), self.FILES["harness/tool.md"].encode())
        self.assertEqual((root / "docs/org/venue.md").read_text(), "Read %s/harness/venue.md and follow it.\n" % pack)
        self.assertEqual((root / ".codex/org.md").read_text(), "Read %s/harness/venue.md and follow it.\n" % pack)
        self.assertTrue(record["launches"][0].endswith(
            " and follow it. Then read %s/harness/codex-note.md and follow it.'" % pack), record["launches"])
        self.assertEqual(record["harness_pointers"], {
            str(copy): {"harness": "claude-code", "source": "harness/tool.md", "mode": "copy"},
            str(root / "docs/org/venue.md"): {"harness": "claude-code", "source": "harness/venue.md", "mode": "pointer"},
            str(root / ".codex/org.md"): {"harness": "codex", "source": "harness/venue.md", "mode": "pointer"}})
        for path in record["harness_pointers"]:
            self.assertEqual(record["targets"][path], hashlib.sha256(Path(path).read_bytes()).hexdigest())
            self.assertIn("/" + str(Path(path).relative_to(root)), self.exclude.read_text().splitlines())
        excluded = self.exclude.read_text()
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(self.manifest.read_text()), record)
        self.assertEqual(self.exclude.read_text(), excluded)

    def test_registry_installs_selected_harnesses_only(self):
        self.registry(self.REGISTRY, self.FILES)
        r = self.bootstrap("--harness", "codex", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual([e["harness"] for e in record["harness_pointers"].values()], ["codex"])
        self.assertFalse(self.claude.exists())
        self.assertIn("Then read", record["launches"][0])
        r = self.bootstrap("--harness", "claude-code", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual(record["launches"], [])
        self.assertEqual(sorted(e["harness"] for e in record["harness_pointers"].values()),
                         ["claude-code", "claude-code", "codex"])

    def test_registry_refusals_list_every_target_and_write_nothing(self):
        self.registry(self.REGISTRY, self.FILES)
        root = Path(self.project_dir)
        tracked = root / "docs/org/venue.md"
        tracked.parent.mkdir(parents=True)
        tracked.write_text("tracked\n")
        subprocess.run(["git", "-C", self.project_dir, "add", str(tracked)], check=True)
        tracked.unlink()
        (root / ".codex").symlink_to(self.home, target_is_directory=True)
        unowned = root / ".claude/skills/org-tool/SKILL.md"
        unowned.parent.mkdir(parents=True)
        unowned.write_text("owner file\n")
        before = self.exclude.read_text()
        for flags in (("--dry-run",), ("--yes",)):
            r = self.bootstrap("--harness", "claude-code", "--harness", "codex", *flags)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            for text in ("tracked target: " + str(tracked), "symlink target or parent: " + str(root / ".codex/org.md"),
                         "target edited or unowned: " + str(unowned)):
                self.assertIn(text, r.stderr)
            self.assertNotIn("(planned)", r.stdout)
        self.assertFalse(self.manifest.exists())
        self.assertFalse((self.claude / "agents").exists())
        self.assertFalse(tracked.exists())
        self.assertEqual(unowned.read_text(), "owner file\n")
        self.assertFalse((Path(self.home) / "org.md").exists())
        self.assertEqual(self.exclude.read_text(), before)

    def test_registry_source_escape_is_refused(self):
        outside = Path(self.tmp) / "outside.md"
        outside.write_text("secret\n")
        pack = self.registry(self.REGISTRY, self.FILES)
        (pack / "harness/venue.md").unlink()
        (pack / "harness/venue.md").symlink_to(outside)
        r = self.bootstrap("--harness", "claude-code", "--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("escapes the pack directory: 'harness/venue.md'", r.stderr)
        self.assertFalse(self.manifest.exists())
        self.assertFalse(self.claude.exists())

    def upgrade(self, *flags):
        return subprocess.run([sys.executable, str(self.cli), "upgrade", "--project", self.project, *flags],
                              input="", capture_output=True, text=True, env=self.env)

    def test_pack_only_upgrade_rewrites_owned_targets_and_reports_drift(self):
        pack = self.registry(self.REGISTRY, self.FILES)
        r = self.bootstrap("--harness", "claude-code", "--harness", "codex", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.upgrade("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines()[-1], "crew upgrade: no changes")
        copy = Path(self.project_dir) / ".claude/skills/org-tool/SKILL.md"
        (pack / "harness/tool.md").write_text("Run org-tool v2.\n")
        r = self.upgrade("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("+Run org-tool v2.", r.stdout)
        self.assertNotEqual(copy.read_text(), "Run org-tool v2.\n")
        r = self.upgrade("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual(copy.read_text(), "Run org-tool v2.\n")
        self.assertEqual(record["targets"][str(copy)], hashlib.sha256(b"Run org-tool v2.\n").hexdigest())
        self.assertEqual(self.upgrade("--dry-run").stdout.splitlines()[-1], "crew upgrade: no changes")
        (pack / "harness.toml").write_text(self.REGISTRY.replace("harness/codex-note.md", "harness/tool.md"))
        r = self.upgrade("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Then read %s/harness/tool.md" % pack.resolve(), json.loads(self.manifest.read_text())["launches"][0])
        copy.write_text("owner edit\n")
        (pack / "harness/tool.md").write_text("Run org-tool v3.\n")
        before = self.manifest.read_bytes()
        r = self.upgrade("--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("drift: " + str(copy), r.stdout + r.stderr)
        self.assertEqual(copy.read_text(), "owner edit\n")
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_removed_entries_follow_the_owned_target_lifecycle(self):
        pack = self.registry(self.REGISTRY, self.FILES)
        r = self.bootstrap("--harness", "claude-code", "--harness", "codex", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        root = Path(self.project_dir)
        venue, codex = root / "docs/org/venue.md", root / ".codex/org.md"
        codex.write_text("owner edit\n")
        (pack / "harness.toml").write_text(self.REGISTRY.split("[[pointer]]\nharness = \"claude-code\"\ntarget = \"docs")[0] +
                                           "[[pointer]]\nharness = \"codex\"\nlaunch_note = \"harness/codex-note.md\"\n")
        r = self.upgrade("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Remove: %s (dropped from the pack registry)" % venue, r.stdout)
        self.assertIn("Repo operation: remove /docs/org/venue.md from .git/info/exclude", r.stdout)
        self.assertIn("Human step: Remove or keep %s: dropped from the pack registry" % codex, r.stdout)
        self.assertTrue(venue.exists())
        r = self.upgrade("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertFalse(venue.exists())
        self.assertEqual(codex.read_text(), "owner edit\n")
        self.assertNotIn("/docs/org/venue.md", self.exclude.read_text().splitlines())
        for path in (venue, codex):
            self.assertNotIn(str(path), record["targets"])
            self.assertNotIn(str(path), record["harness_pointers"])
        self.assertEqual(list(record["harness_pointers"]), [str(root / ".claude/skills/org-tool/SKILL.md")])
        self.assertEqual(set(record["self_test"].values()), {"ok"})
        self.assertEqual(self.upgrade("--dry-run").stdout.splitlines()[-1], "crew upgrade: no changes")
        r = self.bootstrap("--harness", "codex", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(str(root / ".claude/skills/org-tool/SKILL.md"), json.loads(self.manifest.read_text())["harness_pointers"])
        (pack / "harness.toml").write_text(self.REGISTRY)
        r = self.bootstrap("--harness", "codex", "--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("target edited or unowned: " + str(codex), r.stderr)

    def test_harness_requires_role_render(self):
        self.project_path.write_text(self.project_path.read_text().replace('name = "tmux"', 'name = "grok-bot"'))
        r = self.bootstrap("--harness", "claude-code", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("session binding", r.stderr)
        self.assertFalse(self.claude.exists())


def load_tests(loader, tests, pattern):
    """ReleaseSources reuses the Bootstrap fixture; run only its own tests, not the inherited ones again."""
    def own(test):
        return type(test) is not ReleaseSources or test._testMethodName in ReleaseSources.__dict__

    def flat(suite):
        for test in suite:
            yield from flat(test) if isinstance(test, unittest.TestSuite) else [test]
    return unittest.TestSuite(t for t in flat(tests) if own(t))


def evidence():
    fixture = Bootstrap()
    fixture.setUp()
    try:
        fixture.real_git()
        subprocess.run(["git", "init", "-q", fixture.project_dir], check=True)
        for flags in (("--dry-run",), ("--yes",), ("--yes",)):
            result = fixture.bootstrap(*flags)
            assert result.returncode == 0, result.stdout + result.stderr
            if flags == ("--dry-run",):
                assert not fixture.manifest.exists()
            print("crew bootstrap %s: exit %d" % (" ".join(flags), result.returncode))
            print(result.stdout.splitlines()[-1].replace(str(fixture.manifest), "<state>/install.json"))
        record = json.loads(fixture.manifest.read_text())
        assert record["tag"] == "v2.1.0" and record["status"] == "installed"
        assert (Path(fixture.state) / "crew.toml").read_text() == fixture.project_path.read_text()
        assert (Path(fixture.state) / "eng-crew").resolve() == fixture.bundle.resolve()
        print("record: v2.1.0 tmux installed; profile copy and bundle link verified")
        (Path(fixture.state) / "VERSION").write_text("owner edit\n")
        result = fixture.bootstrap("--yes")
        assert result.returncode == 1 and "target edited or unowned" in result.stderr
        assert (Path(fixture.state) / "VERSION").read_text() == "owner edit\n"
        print("crew bootstrap --yes after owner edit: exit 1; edit preserved")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary project, install and bundle removed")
    fixture = HarnessTargets()
    fixture.setUp()
    try:
        flags = ("--harness", "claude-code", "--harness", "codex")
        result = fixture.bootstrap(*flags, "--dry-run")
        assert result.returncode == 0 and not fixture.claude.exists(), result.stdout + result.stderr
        print("harness dry-run: exit 0; no pointers or render written")
        result = fixture.bootstrap(*flags, "--yes")
        assert result.returncode == 0, result.stdout + result.stderr
        record = json.loads(fixture.manifest.read_text())
        pointers = [p for p in fixture.claude.rglob("*.md")]
        for path in pointers:
            brief = path.read_text().split("Read your brief at ")[1].split(" and follow it.")[0]
            assert Path(brief).is_file()
            assert str(path) in record["targets"]
            assert "/" + str(path.relative_to(fixture.project_dir)) in fixture.exclude.read_text().splitlines()
        assert len(pointers) == 4 and len(record["launches"]) == 1
        print("harness apply: exit 0; 3 subagents + coordinator skill resolve to deployed briefs")
        print("record: all 5 Claude targets hash-recorded and excluded; Codex launch carries pointer + trust")
        result = fixture.bootstrap("--yes")
        assert result.returncode == 0 and json.loads(fixture.manifest.read_text()) == record
        print("harness repeat: exit 0; same manifest, no duplicate hook or excludes")
        pointers[0].write_text("owner edit\n")
        result = fixture.bootstrap("--yes")
        assert result.returncode == 1 and pointers[0].read_text() == "owner edit\n"
        print("harness owner edit: exit 1; edit and manifest preserved")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary harness pointers, project, render and bundle removed")


def fetch_evidence():
    fixture = Bootstrap()
    fixture.setUp()
    try:
        fixture.real_git()
        subprocess.run(["git", "init", "-q", fixture.project_dir], check=True)
        r = fixture.bootstrap("--yes")
        assert r.returncode == 0, r.stdout + r.stderr
        print("create: crew bootstrap --yes -> exit 0; v2.1.0 installed")
        destination, sha = fixture.release()
        r = fixture.bootstrap("--version", "v2.2.0", "--yes", "--org-profile", fixture.org("v2.2.0"))
        assert r.returncode == 0, r.stdout + r.stderr
        record = json.loads(fixture.manifest.read_text())
        assert record["tag"] == "v2.2.0" and record["bundle_sha256"] == sha
        assert (Path(fixture.state) / "eng-crew").resolve() == destination.resolve()
        assert (fixture.bundle / "VERSION").read_text() == "v2.1.0\n"
        print("update: crew bootstrap --version v2.2.0 --yes --org-profile <pack>/profile.toml -> exit 0")
        print("verified SHA256SUMS; extracted eng-crew-2.2.0 beside original; matching pack pin accepted")
        print("record: v2.2.0 installed; checksum and selected bundle link verified; original v2.1.0 preserved")
        previous = fixture.manifest.read_text()
        for tag, options, flags, message in (
                ("v2.3.0", dict(checksum=False), (), "SHA256SUMS mismatch"),
                ("v2.4.0", {}, ("--org-profile", fixture.org("v9.9.9")), "pack.eng_crew_version"),
                ("v2.5.0-rc.1", {}, (), "require --pre")):
            rejected, _ = fixture.release(tag=tag, **options)
            r = fixture.bootstrap("--version", tag, "--dry-run", *flags)
            assert r.returncode == 1 and message in r.stderr, r.stdout + r.stderr
            assert not rejected.exists() and fixture.manifest.read_text() == previous
            print("reject: %s -> exit 1; %s; live install preserved" % (tag, message))
        rejected, _ = fixture.release(tag="v2.5.0-rc.1")
        r = fixture.bootstrap("--version", "v2.5.0-rc.1", "--pre", "--dry-run")
        assert r.returncode == 0 and rejected.is_dir(), r.stdout + r.stderr
        assert fixture.manifest.read_text() == previous
        print("preview: crew bootstrap --version v2.5.0-rc.1 --pre --dry-run -> exit 0; live install preserved")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary project, releases and install removed; absent=True")


def size_budget_evidence():
    fixture = Bootstrap()
    fixture.setUp()
    try:
        fixture.real_git()
        subprocess.run(["git", "init", "-q", fixture.project_dir], check=True)
        path = fixture.bundle / "templates/runtimes/tmux/builder.md"
        path.write_text("é" * 8192)
        result = fixture.bootstrap("--yes")
        assert result.returncode == 0, result.stdout + result.stderr
        print("apply: exit 0; builder 16384 UTF-8 bytes; missing budget defaults to 16384")
        print("Self-test: size_budget ok")
        fixture.project_path.write_text(fixture.project_path.read_text() + "\n[size_budget]\nbuilder = 16385\n")
        result = fixture.bootstrap("--yes")
        assert result.returncode == 0, result.stdout + result.stderr
        print("update: exit 0; builder 16384 bytes under configured 16385-byte budget")
        path.write_text("é" * 8193)
        result = fixture.bootstrap("--yes")
        record = json.loads(fixture.manifest.read_text())
        assert result.returncode == 1 and record["status"] == "failed" and record["self_test"]["size_budget"] == "fail"
        for line in result.stdout.splitlines():
            if line.startswith(("Self-test: size_budget", "runtime/builder.md:")):
                print(line)
        print("oversize apply: exit 1; install status failed")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary project and install removed")


def self_test_evidence():
    fixture = Bootstrap()
    fixture.setUp()
    try:
        fixture.smoke_host()
        result = fixture.bootstrap("--dry-run", "--smoke")
        assert result.returncode == 0 and not fixture.issue_log.exists()
        print("dry-run --smoke: exit 0; no install or issue created")
        result = fixture.bootstrap("--yes")
        assert result.returncode == 0 and not fixture.issue_log.exists(), result.stdout + result.stderr
        print("apply: exit 0; no smoke issue by default")
        for line in result.stdout.splitlines():
            if line.startswith("Self-test:"):
                print(line)
        for _ in range(2):
            result = fixture.bootstrap("--yes", "--smoke")
            assert result.returncode == 0, result.stdout + result.stderr
            print(result.stdout.splitlines()[-1])
        assert len(fixture.issue_log.read_text().splitlines()) == 1
        print("smoke: one docs-only issue, crew:ready, assigned to builder; result queued")
        (fixture.bundle / "templates/runtimes/tmux/reviewer.md").unlink()
        result = fixture.bootstrap("--yes")
        record = json.loads(fixture.manifest.read_text())
        assert result.returncode == 1 and record["status"] == "failed" and record["self_test"]["briefs"] == "fail"
        print("missing reviewer brief: exit 1; install status failed; briefs fail")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary project, install and fake issue log removed")


def proposal_evidence():
    fixture = Bootstrap()
    fixture.setUp()
    try:
        edited = Path(fixture.tmp) / "edited.toml"
        edited.write_text(fixture.project_path.read_text() + '\n[flavor]\nname = "thorough"\n')
        fixture.missing_project()
        r = fixture.bootstrap("--dry-run", "--runtime", "tmux")
        assert r.returncode == 0 and not fixture.project_path.exists(), r.stdout + r.stderr
        print("$ crew bootstrap --project <project>/crew.toml --runtime tmux --dry-run")
        print("exit=0; proposal: acme/widgets, tmux, GitHub for every concern, flavor standard")
        print(r.stdout.splitlines()[-1])
        r = fixture.bootstrap("--runtime", "tmux")
        assert r.returncode == 1 and not fixture.project_path.exists()
        print("$ crew bootstrap --project <project>/crew.toml --runtime tmux < /dev/null")
        print("exit=1; " + r.stderr.strip())
        r = fixture.bootstrap("--yes", "--proposal", str(edited))
        assert r.returncode == 0 and fixture.project_path.read_text() == edited.read_text(), r.stdout + r.stderr
        print("$ crew bootstrap --project <project>/crew.toml --proposal <edited.toml> --yes")
        print("exit=0; recorded owner edit: flavor thorough; install status installed")
        for line in r.stdout.splitlines():
            if line.startswith("Self-test:"):
                print(line)
        before = fixture.project_path.read_bytes()
        subprocess.run(["git", "-C", fixture.project_dir, "config", "remote.origin.url", "https://example.invalid/other"], check=True)
        r = fixture.bootstrap("--yes", "--proposal", "/missing", "--flavor", "fast")
        assert r.returncode == 0 and fixture.project_path.read_bytes() == before, r.stdout + r.stderr
        print("$ crew bootstrap --project <project>/crew.toml --proposal /missing --flavor fast --yes")
        print("exit=0; changed origin and proposal flags ignored; recorded profile byte-identical")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary project, edited proposal and install removed; absent=True")


if __name__ == "__main__":
    if sys.argv[1:] == ["--evidence"]:
        evidence()
    elif sys.argv[1:] == ["--fetch-evidence"]:
        fetch_evidence()
    elif sys.argv[1:] == ["--self-test-evidence"]:
        self_test_evidence()
    elif sys.argv[1:] == ["--size-budget-evidence"]:
        size_budget_evidence()
    elif sys.argv[1:] == ["--proposal-evidence"]:
        proposal_evidence()
    else:
        unittest.main()
