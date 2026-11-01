"""Tests for crew doctor (#190) on a fake host; fixtures in crew_testlib.py (stdlib only).

Covers: only fake tools on `PATH` and a fake home with Claude Code and Codex configs; a ready host passes (a missing
tier-order engine warns), a missing tool or coordinator engine fails, one working engine fails diversity, a missing
state dir fails read-only and `--fix` creates it idempotently, human steps (a `gh` login, an untrusted Codex hook,
Claude Code folder trust) are listed with exit 0 and never fixed, trust on a parent counts, a placeholder path fails
without touching state, grok-bot skips the tmux checks, a profile problem exits 1, and the installed version against the
latest release (latest, behind, unreadable, no VERSION). Run in CI.
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import unittest
from unittest import mock
from crew_testlib import Base, CREW

HOOK_KEY = "%s:session_start:0:0"


def read(path):
    with open(path) as f:
        return f.read()


class DoctorBase(Base):
    def setUp(self):
        super().setUp()
        self.bindir = os.path.join(self.tmp, "bin")
        self.home = os.path.join(self.tmp, "home")
        self.codex = os.path.join(self.home, ".codex")
        os.makedirs(self.codex)
        self.env["PATH"] = self.bindir  # nothing from the real host
        self.env["HOME"] = self.home
        for var in ("CODEX_HOME", "CLAUDE_CONFIG_DIR"):
            self.env.pop(var, None)
        for tool in ("git", "claude", "codex"):
            self.tool(tool)
        self.gh(["acme-bot", "acme-reviewer"], "v2.1.0")
        self.trust_claude()
        self.hooks(trusted=True)
        for d in ("claims", "inbox", "status", "wake", "locks"):
            os.makedirs(os.path.join(self.state, d))
        open(os.path.join(self.state, "locks", "merge.lock"), "w").close()

    def tool(self, name, body="echo 1.0"):
        path = os.path.join(self.bindir, name)
        with open(path, "w") as f:
            f.write("#!/bin/sh\n%s\n" % body)
        os.chmod(path, 0o755)

    def gh(self, logins, latest):
        lines = "".join("echo '  ✓ Logged in to github.com account %s (keyring)'\n" % u for u in logins)
        labels = [{"name": n, "color": c, "description": d} for n, c, d in
                  re.findall(r"^(crew:[^|]+)\|([^|]+)\|(.+)$", read(os.path.join(os.path.dirname(CREW), "..", "docs", "runbook-new-repo.md")), re.M)]
        self.tool("gh", 'case "$1 $2" in\n"auth status") echo github.com\n%s;;\n"auth token") echo fixture-token;;\n"release view") echo %s;;\n'
                  '"api repos/acme/widgets/labels?per_page=100") echo \'%s\';;\n'
                  '"api repos/acme/widgets/collaborators/acme-reviewer/permission") echo \'{"permission":"write"}\';;\n'
                  '"api repos/acme/widgets/milestones?state=all&per_page=100") echo \'[[{"title":"M1","state":"open"}]]\';;\n'
                  '"project list") echo \'{"totalCount":1,"projects":[{"id":"P1","number":1,"title":"widgets crew board","closed":false}]}\';;\n'
                  '"api graphql") echo \'{"data":{"repository":{"projectsV2":{"nodes":[{"id":"P1"}],"pageInfo":{"hasNextPage":false}}}}}\';;\n'
                  '"project field-list") echo \'{"fields":[{"id":"F1","name":"Status","options":[{"name":"Todo"},{"name":"In Progress"},{"name":"In Review"},{"name":"Done"}]}]}\';;\n'
                  "*) exit 1;;\nesac" % (lines, latest, json.dumps([labels])))

    def trust_claude(self, accepted=True):
        with open(os.path.join(self.home, ".claude.json"), "w") as f:
            json.dump({"projects": {os.path.realpath(self.project_dir): {"hasTrustDialogAccepted": accepted}}}, f)

    def hooks(self, trusted):
        path = os.path.join(self.codex, "hooks.json")
        with open(path, "w") as f:
            json.dump({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "x"}]}]}}, f)
        with open(os.path.join(self.codex, "config.toml"), "w") as f:
            f.write('[hooks.state."%s"]\ntrusted_hash = "sha256:00"\n' % (HOOK_KEY % path) if trusted else "")

    def doctor(self, *args):
        return self.crew("doctor", "--project", self.project, *args)

    def rows(self, r):
        """{check: status} from the report lines: status, check name (18 wide), detail and hint."""
        return {line[6:24].strip(): line[:5].strip() for line in r.stdout.split("\n\n")[0].splitlines()}

    def detail(self, r, check):
        return [line[25:] for line in r.stdout.splitlines() if line[6:24].strip() == check][0]

    def humans(self, r):
        return r.stdout.split("Steps only a person can take:\n")[1].splitlines() if "Steps only" in r.stdout else []



class Doctor(DoctorBase):
    def test_ready_host_passes(self):
        r = self.doctor()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = self.rows(r)
        for check in ("python", "git", "gh", "tmux", "gh acme-bot", "gh acme-reviewer", "engine claude-code",
                      "engine codex", "codex hooks", "claude trust", "state dir"):
            self.assertEqual(rows[check], "ok", r.stdout)
        self.assertEqual(rows["engine opencode"], "warn")  # a tier-order engine the order falls through
        self.assertEqual(rows["version"], "warn")  # a checkout has no VERSION
        self.assertNotIn("fail", rows.values())
        self.assertEqual(len(self.humans(r)), 1)  # branch protection stays human

    def test_missing_tool_fails(self):
        os.remove(os.path.join(self.bindir, "tmux"))
        r = self.doctor()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.rows(r)["tmux"], "fail")
        self.assertEqual(self.detail(r, "tmux"), "not on PATH; install tmux")

    def test_missing_coordinator_engine_fails_and_one_engine_breaks_diversity(self):
        os.remove(os.path.join(self.bindir, "claude"))
        r = self.doctor()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.rows(r)["engine claude-code"], "fail")
        self.assertEqual(self.detail(r, "engine claude-code"),
                         "claude --version exit 127; install it, or drop it from [engines]")
        self.assertEqual(self.rows(r)["engine diversity"], "fail")

    def test_missing_state_dir_is_read_only_until_fix(self):
        for name in ("inbox", "wake"):
            os.rmdir(os.path.join(self.state, name))
        os.remove(os.path.join(self.state, "locks", "merge.lock"))
        r = self.doctor()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(self.detail(r, "state dir"),
                         "missing locks/merge.lock, inbox/, wake/ in %s; crew doctor --fix creates them" % self.state)
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox")))
        r = self.doctor("--fix")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.rows(r)["state dir"], "ok")
        self.assertEqual(self.detail(r, "state dir"), "created locks/merge.lock, inbox/, wake/ in " + self.state)
        self.assertTrue(os.path.isfile(os.path.join(self.state, "locks", "merge.lock")))
        self.assertTrue(os.path.isdir(os.path.join(self.state, "wake")))
        r = self.doctor("--fix")  # idempotent
        self.assertEqual(r.returncode, 0)
        self.assertEqual((self.rows(r)["state dir"], self.detail(r, "state dir")), ("ok", self.state))

    def test_dry_run_does_not_create_local_state(self):
        os.rmdir(os.path.join(self.state, "inbox"))
        r = self.doctor("--fix", "--dry-run")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox")))

    def test_invalid_milestone_is_rejected(self):
        r = self.doctor("--fix", "--milestone", "release")
        self.assertEqual(r.returncode, 2)
        self.assertIn("milestone must be M followed by a number", r.stderr)

    def test_human_steps_listed_and_never_fixed(self):
        self.gh(["acme-bot"], "v2.1.0")
        self.trust_claude(accepted=False)
        self.hooks(trusted=False)
        configs = [os.path.join(self.home, ".claude.json"), os.path.join(self.codex, "config.toml")]
        before = [read(p) for p in configs]
        for args in ((), ("--fix",)):
            r = self.doctor(*args)
            self.assertEqual(r.returncode, 0, r.stdout)  # a human step is not a fail
            rows = self.rows(r)
            for check in ("gh acme-reviewer", "codex hooks", "claude trust"):
                self.assertEqual(rows[check], "human", r.stdout)
            self.assertIn("1 untrusted in %s" % os.path.join(self.codex, "hooks.json"), r.stdout)
            steps = self.humans(r)
            self.assertEqual(len(steps), 4, r.stdout)
            self.assertIn("- gh auth login as acme-reviewer (never gh auth switch)", steps)
            self.assertTrue(any("trust every hook under Review hooks" in s for s in steps), steps)
            self.assertTrue(any("crew attach ash --rw" in s for s in steps), steps)
        self.assertEqual([read(p) for p in configs], before)

    def test_claude_trust_on_a_parent_counts(self):
        with open(os.path.join(self.home, ".claude.json"), "w") as f:
            json.dump({"projects": {os.path.realpath(self.tmp): {"hasTrustDialogAccepted": True}}}, f)
        self.assertEqual(self.rows(self.doctor())["claude trust"], "ok")

    def test_placeholder_path_fails_without_touching_state(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('worktree_root = "%s/wt"' % os.path.join(self.tmp, "state"),
                                 'worktree_root = "<worktree-root>"'))
        r = self.doctor("--fix")
        self.assertEqual(r.returncode, 1)
        self.assertIn("paths.worktree_root: still the placeholder <worktree-root>", r.stdout)
        self.assertNotIn("state dir", self.rows(r))

    def test_grok_bot_runtime_skips_tmux_checks(self):
        self.write_profile(runtime="grok-bot")
        os.remove(os.path.join(self.bindir, "tmux"))
        for name in ("status", "wake"):
            os.rmdir(os.path.join(self.state, name))
        r = self.doctor()
        self.assertEqual(r.returncode, 0, r.stdout)
        rows = self.rows(r)
        for check in ("tmux", "codex hooks", "claude trust"):
            self.assertNotIn(check, rows)
        self.assertEqual(rows["state dir"], "ok")

    def test_profile_problem_exits_1(self):
        with open(self.project, "w") as f:
            f.write("[repo]\nowner = 1\n")
        r = self.doctor()
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("python", r.stdout)


class Version(DoctorBase):
    """The installed VERSION against the latest release (docs/release.md update path, Learn), in-process."""

    def version(self, have):
        loader = importlib.machinery.SourceFileLoader("crew_cli", CREW)
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
        loader.exec_module(mod)
        doctor = mod.commands()["doctor"]
        path = os.path.join(self.tmp, "VERSION-%s" % have)
        if have:
            with open(path, "w") as f:
                f.write(have + "\n")
        with mock.patch.dict(os.environ, self.env), mock.patch.object(doctor, "VERSION_FILE", path):
            return doctor.version()[0]

    def test_latest_is_ok(self):
        self.assertEqual(self.version("v2.1.0"), ("ok", "version", "v2.1.0 (latest)", ""))

    def test_behind_warns_with_the_update_path(self):
        self.gh(["acme-bot"], "v2.2.0")
        status, _, detail, hint = self.version("v2.1.0")
        self.assertEqual((status, detail), ("warn", "v2.1.0 installed, v2.2.0 is the latest release"))
        self.assertIn("docs/release.md update path", hint)

    def test_unreadable_release_or_no_version_warns(self):
        self.tool("gh", "exit 1")
        self.assertEqual(self.version("v2.1.0")[0], "warn")
        self.assertEqual(self.version(None)[2], "no VERSION: not a release bundle")


if __name__ == "__main__":
    unittest.main()
