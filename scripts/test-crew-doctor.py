"""Tests for crew doctor (#190) on a fake host; fixtures in crew_testlib.py (stdlib only).

Covers: only fake tools on `PATH` and a fake home with Claude Code and Codex configs; a ready host passes (a missing
tier-order engine warns), a missing tool or coordinator engine fails, one working engine fails diversity, a missing
state dir fails read-only and `--fix` creates it idempotently, human steps (a `gh` login, an untrusted Codex hook,
Claude Code folder trust) are listed with exit 0 and never fixed, trust on a parent counts, a placeholder path fails
without touching state, grok-bot skips the tmux checks, a profile problem exits 1, and the installed version against the
latest release (latest, behind, unreadable, no VERSION), and the handoff rows (no control item warns; this runtime owns,
another owns, draining, in transit and no record; an unreadable control item fails), and the grok-bot triage row
(off is ok; triage.enabled warns that no Grok timer is installed; no row on tmux), and the pack row (the install's
recorded pack name and version; no row without one). Run in CI.
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
                  re.findall(r"^(crew:[^|]+)\|([^|]+)\|(.+)$", read(os.path.join(os.path.dirname(CREW), "..", "docs", "runbooks", "github-tracking.md")), re.M)]
        self.tool("gh", 'case "$1 $2" in\n"auth status") echo github.com\n%s;;\n"auth token") echo fixture-token;;\n"release view") echo %s;;\n'
                  '"api repos/acme/widgets/labels?per_page=100") echo \'%s\';;\n'
                  '"api repos/acme/widgets/collaborators/acme-reviewer/permission") echo \'{"permission":"write"}\';;\n'
                  '"api repos/acme/widgets/milestones?state=all&per_page=100") echo \'[[{"title":"M1","state":"open"}]]\';;\n'
                  '"project list") echo \'{"totalCount":1,"projects":[{"id":"P1","number":1,"title":"widgets crew board","closed":false}]}\';;\n'
                  '"api graphql") echo \'{"data":{"repository":{"projectsV2":{"nodes":[{"id":"P1"}],"pageInfo":{"hasNextPage":false}}}}}\';;\n'
                  '"project field-list") echo \'{"fields":[{"id":"F1","name":"Status","options":[{"name":"Todo"},{"name":"In Progress"},{"name":"In Review"},{"name":"Done"}]}]}\';;\n'
                  '"api --paginate") exec /bin/cat "$FAKE_COMMENTS";;\n'
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

    def test_recorded_pack_version_row(self):
        manifest = os.path.join(self.state, "install.json")
        with open(manifest, "w") as f:
            json.dump({"tag": "v2.1.0"}, f)
        self.assertNotIn("pack", self.rows(self.doctor()))
        with open(manifest, "w") as f:
            json.dump({"tag": "v2.1.0", "pack": {"name": "acme", "version": "0.5.0"}}, f)
        r = self.doctor()
        self.assertEqual(self.rows(r)["pack"], "ok", r.stdout)
        self.assertEqual(self.detail(r, "pack"), "acme 0.5.0")

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
        self.assertEqual(self.detail(r, "triage"), "off: no Grok timer; coordinator dispositions")

    def test_grok_bot_triage_enabled_warns_no_timer(self):
        self.write_profile(runtime="grok-bot")
        with open(self.project, "a") as f:
            f.write("\n[triage]\nenabled = true\n")
        r = self.doctor()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.rows(r)["triage"], "warn")
        self.assertEqual(self.detail(r, "triage"), "enabled: grok-bot installs no Grok timer; triage stays coordinator "
                         "dispositions; set triage.enabled = false (docs/triage.md)")
        self.assertNotIn("timer installed", r.stdout)
        self.write_profile()
        with open(self.project, "a") as f:
            f.write("\n[triage]\nenabled = true\n")
        self.assertNotIn("triage", self.rows(self.doctor()))  # tmux runs the scan from crew poll

    def test_profile_problem_exits_1(self):
        with open(self.project, "w") as f:
            f.write("[repo]\nowner = 1\n")
        r = self.doctor()
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("python", r.stdout)


class ToolDrift(DoctorBase):
    def probes(self, running="2.10.0", installed="2.10.0", pin="2.9.0"):
        self.tool("session-version", "echo 'example v%s'" % running)
        self.tool("installed-version", "echo 'example %s'" % installed)
        with open(self.project, "a") as f:
            f.write('\n[tools.example]\nrunning = ["session-version"]\ninstalled = ["installed-version"]\n')
            if pin:
                f.write('pin = "%s"\n' % pin)

    def test_matching_versions_above_numeric_pin(self):
        self.probes()
        r = self.doctor()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rows(r)["tool example"], "ok")
        self.assertEqual(self.detail(r, "tool example"), "running 2.10.0, installed 2.10.0, pin >= 2.9.0")

    def test_dry_run_keeps_state_read_only_and_reports_repo_and_tool_checks(self):
        self.probes(running="2.9.0", pin=None)
        os.rmdir(os.path.join(self.state, "inbox"))
        r = self.doctor("--fix", "--dry-run")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        rows = self.rows(r)
        self.assertEqual(rows["state dir"], "fail")
        self.assertEqual(rows["crew labels"], "ok")
        self.assertEqual(rows["tool example"], "warn")
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox")))

    def test_installed_update_is_inert_and_fix_does_not_restart(self):
        self.probes(running="2.9.0", pin=None)
        for args in ((), ("--fix",)):
            r = self.doctor(*args)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.rows(r)["tool example"], "warn")
            self.assertEqual(self.detail(r, "tool example"),
                             "running 2.9.0, installed 2.10.0; restart the session using the installed tool")
        self.assertIn("2.9.0", read(os.path.join(self.bindir, "session-version")))

    def test_below_pin_even_when_versions_match(self):
        self.probes(running="2.9.0", installed="2.9.0", pin="v2.10.0")
        r = self.doctor()
        self.assertEqual(self.rows(r)["tool example"], "warn")
        self.assertIn("upgrade to at least v2.10.0 and restart the session", r.stdout)

    def test_unreadable_or_failed_probe_warns(self):
        self.probes()
        for body in ("echo unknown", "echo 2.10.0; exit 1", "echo 2.10.0-beta"):
            self.tool("session-version", body)
            r = self.doctor()
            self.assertEqual(self.rows(r)["tool example"], "warn")
            self.assertIn("check the profile's read-only version probes", r.stdout)

    def test_no_configured_tools_skips_probes(self):
        self.assertFalse(any(k.startswith("tool ") for k in self.rows(self.doctor())))


class Handoff(DoctorBase):
    SHA = "a" * 40

    def setUp(self):
        super().setUp()
        self.env["FAKE_COMMENTS"] = os.path.join(self.tmp, "comments.json")
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace("[repo]\n", "[repo]\ncontrol_item = 99\n").replace(
                "[runtime]\n", '[runtime]\ninstance = "laptop"\n'))

    def record(self, *markers):
        """Coordinator handoff posts by a trusted login: (state, from, to) each, all under one handoff id."""
        with open(self.env["FAKE_COMMENTS"], "w") as f:
            json.dump([[{"user": {"login": "acme-bot"}, "body": "<!-- crew:v1 role=coordinator pass=handoff "
                         "handoff=20261103-abc123 state=%s from=%s to=%s cmd-id=chat sha=%s round=n/a verdict=n/a -->"
                         % (state, src, dst, self.SHA)} for state, src, dst in markers]], f)

    def owning(self, *markers):
        self.record(*markers)
        r = self.doctor()
        rows = self.rows(r)
        self.assertEqual((rows["control item"], rows["runtime instance"]), ("ok", "ok"), r.stdout)
        self.assertEqual(self.detail(r, "control item"), "#99")
        return rows["owning runtime"], self.detail(r, "owning runtime")

    def test_no_control_item_warns_without_an_owner_row(self):
        self.write_profile()
        r = self.doctor()
        self.assertEqual(r.returncode, 0, r.stdout)
        rows = self.rows(r)
        self.assertEqual((rows["control item"], rows["runtime instance"]), ("warn", "warn"))
        self.assertEqual(self.detail(r, "control item"),
                         "not set: no ownership record; set repo.control_item (docs/handoff.md)")
        self.assertNotIn("owning runtime", rows)

    def test_this_runtime_owns(self):
        self.assertEqual(self.owning(("claimed", "none", "tmux@laptop")), ("ok", "tmux@laptop (this runtime)"))

    def test_another_runtime_owns(self):
        self.assertEqual(self.owning(("claimed", "none", "grok-bot@box")),
                         ("warn", "grok-bot@box; this runtime is tmux@laptop; read-only here until a handoff to it"))

    def test_draining_and_in_transit(self):
        claim, drain = ("claimed", "none", "tmux@laptop"), ("draining", "tmux@laptop", "session@laptop")
        self.assertEqual(self.owning(claim, drain), ("warn", "tmux@laptop, draining to session@laptop "
                                                             "(20261103-abc123); it starts no new pass"))
        self.assertEqual(self.owning(claim, drain, ("offered", "tmux@laptop", "session@laptop")),
                         ("warn", "in transit tmux@laptop → session@laptop (20261103-abc123); "
                                  "read-only until session@laptop acks or the owner aborts"))

    def test_no_record_yet(self):
        self.assertEqual(self.owning(), ("warn", "no record yet; this runtime's first start posts claimed"))

    def test_unreadable_control_item_fails(self):
        r = self.doctor()  # no comments file: the read exits 1
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(self.rows(r)["control item"], "fail")
        self.assertIn("#99 unreadable", self.detail(r, "control item"))
        self.assertNotIn("owning runtime", self.rows(r))


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
