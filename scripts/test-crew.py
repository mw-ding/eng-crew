#!/usr/bin/env python3
"""Tests for scripts/crew up / down / guard with a fake `tmux` binary on PATH (stdlib only)."""
import fcntl
import importlib.machinery
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
CREW = os.path.join(HERE, "crew")
INPUTS = os.path.join(HERE, "fixtures", "render", "inputs")

# Fake tmux: sessions live in $FAKE_TMUX_STATE (JSON), every call is appended to $FAKE_TMUX_LOG.
FAKE_TMUX = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    with open(os.environ["FAKE_TMUX_LOG"], "a") as f:
        f.write(json.dumps(args) + "\\n")
    path = os.environ["FAKE_TMUX_STATE"]
    state = json.load(open(path)) if os.path.exists(path) else {}
    cmd, target = args[0], args[args.index("-t") + 1].lstrip("=") if "-t" in args else None
    if cmd == "has-session":
        sys.exit(0 if target in state else 1)
    if cmd == "new-session":
        state[args[args.index("-s") + 1]] = {"0": args[args.index("-n") + 1]}
    elif cmd == "new-window":
        session, _, index = target.partition(":")
        state[session][index] = args[args.index("-n") + 1]
        launch = args[-1].split("exec ", 1)[1].split()[0]
        state.setdefault("_panes", {})[target] = os.environ.get("FAKE_TMUX_PANE", launch)
    elif cmd == "display-message":
        print(state.get("_panes", {}).get(target, ""))
    elif cmd == "list-windows":
        print("\\n".join("%s %s" % kv for kv in state.get(target, {}).items()))
    elif cmd == "set-option":
        state.setdefault("_opts", {}).setdefault(target.rstrip(":"), {})[args[-2]] = args[-1]
    elif cmd == "kill-window":
        session, _, index = target.partition(":")
        state[session].pop(index)
        # FAKE_TMUX_USER_CONF: a user config with renumber-windows on and base-index 1, unless the session overrides it.
        opts = dict({"renumber-windows": "on", "base-index": "1"} if os.environ.get("FAKE_TMUX_USER_CONF") else {},
                    **state.get("_opts", {}).get(session, {}))
        if opts.get("renumber-windows") == "on":
            names = [state[session][k] for k in sorted(state[session], key=int)]
            state[session] = {str(int(opts["base-index"]) + i): n for i, n in enumerate(names)}
    elif cmd == "kill-session":
        state.pop(target)
    json.dump(state, open(path, "w"))
    """)

PROFILE = textwrap.dedent("""\
    [repo]
    owner = "acme"
    name = "widgets"
    [runtime]
    name = "{runtime}"
    [identities]
    owners = ["acme-owner"]
    coordinator = {{ gh_user = "acme-bot", name = "Ash" }}
    builder = {{ gh_user = "acme-bot", name = "Ben" }}
    reviewer = {{ gh_user = "acme-reviewer", name = "Vera" }}
    synthesizer = {{ gh_user = "acme-bot", name = "Sam" }}
    [engines]
    coordinator = "{engine}"
    [paths]
    state_dir = "{state}"
    worktree_root = "{state}/wt"
    toolchain_bin = "/opt/node/bin"
    """)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        bindir = os.path.join(self.tmp, "bin")
        os.makedirs(bindir)
        fake = os.path.join(bindir, "tmux")
        with open(fake, "w") as f:
            f.write(FAKE_TMUX)
        os.chmod(fake, 0o755)
        self.log = os.path.join(self.tmp, "tmux.log")
        self.state_file = os.path.join(self.tmp, "tmux.json")
        self.env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"],
                        FAKE_TMUX_LOG=self.log, FAKE_TMUX_STATE=self.state_file)
        self.project_dir = os.path.join(self.tmp, "project")
        os.makedirs(self.project_dir)
        self.state = os.path.join(self.tmp, "state", "acme__widgets")
        self.write_profile()

    def write_profile(self, runtime="tmux", engine="claude-code"):
        self.project = os.path.join(self.project_dir, "crew.toml")
        with open(self.project, "w") as f:
            f.write(PROFILE.format(runtime=runtime, engine=engine, state=os.path.join(self.tmp, "state")))

    def crew(self, *args, stdin=""):
        return subprocess.run([sys.executable, CREW, *args], input=stdin, capture_output=True, text=True, env=self.env)

    def up(self):
        return self.crew("up", "--project", self.project, "--inputs", INPUTS)

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return [json.loads(line) for line in f]

    def new_session(self):
        found = [c for c in self.calls() if c[0] == "new-session"]
        self.assertEqual(len(found), 1, self.calls())
        return found[0]

    def settings(self):
        with open(os.path.join(self.project_dir, ".claude", "settings.local.json")) as f:
            return json.load(f)

    def put(self, rel, text):
        path = os.path.join(self.state, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)


class Crew(Base):
    def test_up_creates_session_with_engine_and_brief(self):
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        call = self.new_session()
        brief = os.path.join(self.state, "render", "briefs", "coordinator.md")
        self.assertTrue(os.path.isfile(brief))
        self.assertEqual(call[call.index("-s") + 1], "crew-acme-widgets")
        self.assertEqual(call[call.index("-n") + 1], "ash")
        self.assertEqual(call[call.index("-c") + 1], self.project_dir)
        env = [call[i + 1] for i, a in enumerate(call) if a == "-e"]
        self.assertIn("CREW_BRIEF=" + brief, env)
        self.assertIn("CREW_IDENTITY=acme-bot", env)
        self.assertIn("CREW_ROLE=coordinator", env)
        self.assertIn("CREW_STATE=" + self.state, env)
        launch = call[-1]
        self.assertIn('GH_TOKEN="$(gh auth token --user "$CREW_IDENTITY")"', launch)
        self.assertIn('exec claude "Read your brief at $CREW_BRIEF and follow it."', launch)
        self.assertNotIn("GH_TOKEN", " ".join(env))
        self.assertIn(["move-window", "-s", "=crew-acme-widgets", "-t", "=crew-acme-widgets:0"], self.calls())
        opts = [c for c in self.calls() if c[0] == "set-option"]
        self.assertEqual(opts, [["set-option", "-t", "=crew-acme-widgets:", "renumber-windows", "off"],
                                ["set-option", "-t", "=crew-acme-widgets:", "base-index", "0"]])

    def test_up_installs_stop_hook_once_and_keeps_settings(self):
        os.makedirs(os.path.join(self.project_dir, ".claude"))
        with open(os.path.join(self.project_dir, ".claude", "settings.local.json"), "w") as f:
            json.dump({"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "other"}]}]}}, f)
        self.assertEqual(self.up().returncode, 0)
        self.crew("down", "--project", self.project)
        self.assertEqual(self.up().returncode, 0)
        s = self.settings()
        self.assertEqual(s["model"], "x")
        commands = [h["command"] for e in s["hooks"]["Stop"] for h in e["hooks"]]
        guard = [c for c in commands if " guard --state " in c]
        self.assertEqual(len(guard), 1, commands)
        self.assertIn("other", commands)
        self.assertIn(self.state, guard[0])

    def test_up_codex_engine_no_claude_settings(self):
        self.write_profile(engine="codex")
        self.assertEqual(self.up().returncode, 0)
        self.assertIn('exec codex "Read your brief at $CREW_BRIEF and follow it."', self.new_session()[-1])
        self.assertFalse(os.path.exists(os.path.join(self.project_dir, ".claude")))

    def test_up_is_idempotent(self):
        self.assertEqual(self.up().returncode, 0)
        r = self.up()
        self.assertEqual(r.returncode, 0)
        self.assertIn("already running", r.stdout)
        self.new_session()

    def test_up_refuses_other_runtime(self):
        self.write_profile(runtime="grok-bot")
        r = self.up()
        self.assertEqual(r.returncode, 1)
        self.assertIn("runtime.name is grok-bot", r.stdout)
        self.assertEqual(self.calls(), [])

    def test_down_kills_role_windows_then_session(self):
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash", "1": "sam", "10": "ben-7", "20": "vera-9-r1-review"}}, f)
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        kills = [c for c in self.calls() if c[0].startswith("kill-")]
        self.assertEqual(kills, [["kill-window", "-t", "=crew-acme-widgets:20"],
                                 ["kill-window", "-t", "=crew-acme-widgets:10"],
                                 ["kill-window", "-t", "=crew-acme-widgets:1"],
                                 ["kill-session", "-t", "=crew-acme-widgets"]])

    def test_down_refuses_while_land_lock_held(self):
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash", "1": "sam"}}, f)
        os.makedirs(os.path.join(self.state, "locks"))
        with open(os.path.join(self.state, "locks", "merge.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("land lock", r.stdout)
        self.assertEqual([c for c in self.calls() if c[0].startswith("kill-")], [])

    def test_down_without_session_is_noop(self):
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 0)
        self.assertIn("not running", r.stdout)

    def guard(self, stdin='{"stop_hook_active": false}'):
        r = self.crew("guard", "--state", self.state, stdin=stdin)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def test_guard_allows_stop_with_no_work(self):
        self.assertIsNone(self.guard())

    def test_guard_blocks_work_in_flight_without_watcher(self):
        self.put("runs/ben-7.json", "{}")
        self.assertEqual(self.guard()["decision"], "block")
        os.remove(os.path.join(self.state, "runs", "ben-7.json"))
        self.put("wake/queue.jsonl", '{"reason": "status:"}\n')
        self.assertEqual(self.guard()["decision"], "block")

    def test_guard_allows_stop_with_live_watcher(self):
        self.put("runs/ben-7.json", "{}")
        self.put("wake/watcher.pid", "%d\n" % os.getpid())
        self.assertIsNone(self.guard())
        self.put("wake/watcher.pid", "999999999\n")
        self.assertEqual(self.guard()["decision"], "block")

    def test_guard_blocks_at_most_once_per_stop_cycle(self):
        self.put("runs/ben-7.json", "{}")
        self.assertEqual(self.guard('{"stop_hook_active": false}')["decision"], "block")
        allowed = self.guard('{"stop_hook_active": true}')
        self.assertNotIn("decision", allowed)
        self.assertIn("no watcher is armed", allowed["systemMessage"])

    def test_guard_malformed_stdin_counts_as_not_active(self):
        self.put("runs/ben-7.json", "{}")
        for stdin in ["", "not json", "[1, 2]", "null"]:
            self.assertEqual(self.guard(stdin)["decision"], "block", stdin)
        os.remove(os.path.join(self.state, "runs", "ben-7.json"))
        for stdin in ["", "not json", '{"stop_hook_active": true}']:
            self.assertIsNone(self.guard(stdin), stdin)


SECRET = "ghp_" + "S3cr3tT0kenValue0000000000000000000000"  # built at run time; never in a file


class Spawn(Base):
    """crew spawn / kill against a temp git repo: a bare origin, the project as primary checkout, PR refs."""

    def git(self, *args, cwd=None):
        r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t", *args], cwd=cwd or self.project_dir,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def setUp(self):
        super().setUp()
        self.origin = os.path.join(self.tmp, "origin.git")
        self.git("init", "-q", "--bare", "-b", "main", self.origin, cwd=self.tmp)
        self.git("init", "-q", "-b", "main")
        self.git("remote", "add", "origin", self.origin)
        self.git("commit", "-q", "--allow-empty", "-m", "base")
        self.git("push", "-q", "origin", "main")
        bindir = os.path.join(self.tmp, "bin")
        with open(os.path.join(bindir, "gh"), "w") as f:  # spawn must never derive the token itself
            f.write("#!/bin/sh\necho called >> %s\necho %s\n" % (os.path.join(self.tmp, "gh.log"), SECRET))
        os.chmod(os.path.join(bindir, "gh"), 0o755)
        self.env["GH_TOKEN"] = SECRET
        self.assertEqual(self.up().returncode, 0)

    def pr(self, n, engine):
        """Push a PR head with one commit carrying an Engine trailer to refs/pull/<n>/head."""
        self.git("commit", "-q", "--allow-empty", "-m", "feat: x\n\nEngine: %s" % engine)
        self.git("push", "-q", "origin", "HEAD:refs/pull/%d/head" % n)
        sha = self.git("rev-parse", "HEAD")
        self.git("reset", "-q", "--hard", "origin/main")
        return sha

    def spawn(self, *args):
        return self.crew("spawn", *args, "--project", self.project, "--timeout", "1")

    def windows(self):
        found = [c for c in self.calls() if c[0] == "new-window"]
        return found

    def record(self, name):
        with open(os.path.join(self.state, "runs", name + ".json")) as f:
            return json.load(f)

    def test_builder_spawn_unique_worktree_identity_engine(self):
        self.env["CREW_SANDBOX_ENV"] = "CREW_TEST_SANDBOX=1"  # the org pack names the real variable
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        base = self.git("rev-parse", "origin/main")
        wt = os.path.join(self.tmp, "state", "wt", "7-%s-builder-build" % base[:7])
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=wt), base)
        call = self.windows()[0]
        self.assertEqual(call[:4], ["new-window", "-d", "-t", "=crew-acme-widgets:10"])
        self.assertEqual(call[call.index("-n") + 1], "ben-7")
        self.assertEqual(call[call.index("-c") + 1], wt)
        env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
        self.assertEqual(env["CREW_IDENTITY"], "acme-bot")
        self.assertEqual(env["CREW_ROLE"], "builder")
        self.assertEqual(env["CREW_ID"], "ben-7")
        self.assertEqual(env["CREW_INBOX"], os.path.join(self.state, "inbox", "ben-7.jsonl"))
        self.assertEqual(env["CREW_STATUS"], os.path.join(self.state, "status", "ben-7.status"))
        self.assertNotIn("GH_TOKEN", env)
        self.assertEqual(env["CREW_TEST_SANDBOX"], "1")
        launch = call[-1]
        self.assertIn(shlex.quote('projects."%s".trust_level="trusted"' % wt), launch)
        self.assertTrue(launch.startswith('export GH_TOKEN="$(gh auth token --user "$CREW_IDENTITY")"; exec codex '))
        self.assertIn("-m gpt-6.1-sol -c model_reasoning_effort=medium", launch)
        self.assertIn('"Read your brief at $CREW_BRIEF and follow it."', launch)
        with open(env["CREW_BRIEF"]) as f:
            brief = f.read()
        self.assertIn("Item: issue #7", brief)
        self.assertIn(wt, brief)
        rec = self.record("ben-7")
        self.assertEqual((rec["index"], rec["engine"], rec["harness"]), (10, "codex", "codex"))
        self.assertTrue(os.path.isfile(os.path.join(self.state, "claims", "builder-issue7")))

    def test_next_free_index_and_duplicate_refused(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("builder", "--issue", "8").returncode, 0)
        self.assertEqual([c[3] for c in self.windows()], ["=crew-acme-widgets:10", "=crew-acme-widgets:11"])
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("already", r.stdout)
        self.assertEqual(len(self.windows()), 2)

    def test_reviewer_engine_differs_from_builder_engine(self):
        sha = self.pr(9, "claude-code opus-5.5 default")
        r = self.spawn("reviewer", "--pr", "9")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        call = self.windows()[0]
        self.assertEqual(call[call.index("-n") + 1], "vera-9-r1-review")
        self.assertEqual(call[3], "=crew-acme-widgets:20")
        self.assertIn("exec codex ", call[-1])
        self.assertIn("-s read-only", call[-1])
        env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
        self.assertEqual(env["CREW_IDENTITY"], "acme-reviewer")
        wt = self.record("vera-9-r1-review")["worktree"]
        self.assertTrue(wt.endswith("9-%s-reviewer-review" % sha[:7]))
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=wt), sha)
        self.pr(10, "codex gpt-6.1-sol medium")
        self.assertEqual(self.spawn("reviewer", "--pr", "10", "--pass", "validate", "--round", "2").returncode, 0)
        call = self.windows()[1]
        self.assertEqual(call[call.index("-n") + 1], "vera-10-r2-validate")
        self.assertIn("exec claude --model sonnet --effort medium", call[-1])

    def test_reviewer_unknown_builder_engine_treated_as_non_claude(self):
        self.git("commit", "-q", "--allow-empty", "-m", "no trailer")
        self.git("push", "-q", "origin", "HEAD:refs/pull/11/head")
        self.assertEqual(self.spawn("reviewer", "--pr", "11").returncode, 0)
        self.assertIn("exec claude ", self.windows()[0][-1])

    def test_no_token_in_argv_env_or_files(self):
        self.pr(9, "claude-code opus-5.5 default")
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("reviewer", "--pr", "9").returncode, 0)
        with open(self.log) as f:
            self.assertNotIn(SECRET, f.read())
        for c in self.windows():
            self.assertFalse([a for i, a in enumerate(c) if c[i - 1] == "-e" and "TOKEN" in a], c)
        for root, dirs, names in os.walk(self.tmp):
            dirs[:] = [d for d in dirs if d not in ("objects", "bin")]  # bin: the fake gh holds the value
            for n in names:
                with open(os.path.join(root, n), "rb") as f:
                    self.assertNotIn(SECRET.encode(), f.read(), os.path.join(root, n))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "gh.log")))

    def test_refuses_primary_checkout_and_missing_session(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('worktree_root = "%s/wt"' % os.path.join(self.tmp, "state"),
                                 'worktree_root = "%s"' % self.project_dir))
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("primary checkout", r.stdout)
        self.crew("down", "--project", self.project)
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not reachable", r.stdout)
        self.assertEqual(self.windows(), [])
        self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))

    def test_failed_start_cleans_up(self):
        self.env["FAKE_TMUX_PANE"] = "bash"
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("failed:", r.stdout)
        self.assertIn(["kill-window", "-t", "=crew-acme-widgets:10"], self.calls())
        self.assertEqual(os.listdir(os.path.join(self.tmp, "state", "wt")), [])
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
        self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))

    def test_kill_removes_only_its_own_run(self):
        self.pr(9, "claude-code opus-5.5 default")
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("reviewer", "--pr", "9").returncode, 0)
        mine, other = self.record("ben-7"), self.record("vera-9-r1-review")
        os.makedirs(os.path.join(mine["worktree"], "target"))  # build output inside the run's worktree
        for d in ["inbox", "status"]:
            os.makedirs(os.path.join(self.state, d), exist_ok=True)
        self.put("inbox/ben-7.jsonl", "{}\n")
        self.put("status/ben-7.status", "done: x\n")
        self.put("status/vera-9-r1-review.status", "ack: y\n")
        r = self.crew("kill", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(["kill-window", "-t", "=crew-acme-widgets:10"], self.calls())
        self.assertFalse(os.path.exists(mine["worktree"]))
        self.assertNotIn(mine["worktree"], self.git("worktree", "list"))
        for rel in ["runs/ben-7.json", "runs/ben-7.brief.md", "inbox/ben-7.jsonl", "status/ben-7.status",
                    "claims/builder-issue7"]:
            self.assertFalse(os.path.exists(os.path.join(self.state, rel)), rel)
        self.assertTrue(os.path.isdir(other["worktree"]))
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "vera-9-r1-review.json")))
        self.assertTrue(os.path.exists(os.path.join(self.state, "status", "vera-9-r1-review.status")))
        self.assertTrue(os.path.exists(other["claim"]))

    def test_layout_pinned_on_spawn_and_ash_stays_0_after_kill(self):
        self.env["FAKE_TMUX_USER_CONF"] = "1"
        with open(self.state_file) as f:  # session made before pinning existed: no session options yet
            state = json.load(f)
        state.pop("_opts", None)
        with open(self.state_file, "w") as f:
            json.dump(state, f)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("builder", "--issue", "8").returncode, 0)
        self.assertEqual(self.crew("kill", "ben-7", "--project", self.project).returncode, 0)
        with open(self.state_file) as f:
            self.assertEqual(json.load(f)["crew-acme-widgets"], {"0": "ash", "11": "ben-8"})
        opts = [c for c in self.calls() if c[0] == "set-option"]
        self.assertTrue(opts and all(c[1:3] == ["-t", "=crew-acme-widgets:"] and "-g" not in c for c in opts), opts)

    def test_kill_refuses_coordinator_and_down_kills_runs(self):
        r = self.crew("kill", "ash", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        wt = self.record("ben-7")["worktree"]
        self.assertEqual(self.crew("down", "--project", self.project).returncode, 0)
        self.assertFalse(os.path.exists(wt))
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))


class KillLanded(Spawn):
    """crew kill removes a worktree only when its work has landed, or with --discard --reason (#172)."""

    def setUp(self):
        super().setUp()
        self.gh_log = os.path.join(self.tmp, "gh-calls.log")
        self.gh_exit = 0
        self.write_gh()

    def write_gh(self):
        with open(os.path.join(self.tmp, "bin", "gh"), "w") as f:
            f.write("#!/usr/bin/env python3\nimport json, sys\nopen(%r, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
                    "sys.exit(%d)\n" % (self.gh_log, self.gh_exit))

    def gh_calls(self):
        if not os.path.exists(self.gh_log):
            return []
        with open(self.gh_log) as f:
            return [json.loads(line) for line in f]

    def builder(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        return self.record("ben-7")["worktree"]

    def commit(self, wt, name="a.txt"):
        with open(os.path.join(wt, name), "w") as f:
            f.write("x\n")
        self.git("add", name, cwd=wt)
        self.git("commit", "-q", "-m", "feat: " + name, cwd=wt)
        return self.git("rev-parse", "HEAD", cwd=wt)

    def kill(self, *args):
        return self.crew("kill", "ben-7", "--project", self.project, *args)

    def assert_refused(self, r, wt, *shown):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("refusing to remove", r.stdout)
        for text in shown:
            self.assertIn(text, r.stdout)
        self.assertTrue(os.path.isdir(wt))
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
        self.assertIn(["kill-window", "-t", "=crew-acme-widgets:10"], self.calls())  # the window still stops

    def test_clean_and_pushed_branch_removed(self):
        wt = self.builder()
        self.git("checkout", "-q", "-b", "infra/7-x", cwd=wt)
        self.commit(wt)
        self.git("push", "-q", "origin", "infra/7-x", cwd=wt)
        r = self.kill()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(wt))
        self.assertEqual(self.gh_calls(), [])

    def test_uncommitted_refused(self):
        wt = self.builder()
        with open(os.path.join(wt, "staged.txt"), "w") as f:
            f.write("x\n")
        self.git("add", "staged.txt", cwd=wt)
        self.assert_refused(self.kill(), wt, "uncommitted: A  staged.txt")

    def test_untracked_refused(self):
        wt = self.builder()
        os.makedirs(os.path.join(wt, "new"))
        with open(os.path.join(wt, "new", "file.txt"), "w") as f:
            f.write("x\n")
        self.assert_refused(self.kill(), wt, "uncommitted: ?? new/file.txt")

    def test_local_only_commit_refused(self):
        wt = self.builder()
        self.git("checkout", "-q", "-b", "infra/7-x", cwd=wt)
        sha = self.commit(wt)
        self.assert_refused(self.kill(), wt, "commit: %s feat: a.txt" % sha)

    def test_merged_into_default_branch_removed(self):
        wt = self.builder()
        self.git("checkout", "-q", "-b", "infra/7-x", cwd=wt)
        self.commit(wt)
        self.git("push", "-q", "origin", "HEAD:main", cwd=wt)  # landed on main; the branch itself never pushed
        r = self.kill()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(wt))

    def test_discard_with_reason_removes_and_posts(self):
        wt = self.builder()
        sha = self.commit(wt)
        r = self.kill("--discard", "--reason", "owner: superseded by #8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(wt))
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
        (call,) = self.gh_calls()
        self.assertEqual(call[:4], ["issue", "comment", "7", "-R"])
        body = call[call.index("--body") + 1]
        self.assertIn("owner: superseded by #8", body)
        self.assertIn(sha, body)

    def test_discard_without_reason_refused(self):
        wt = self.builder()
        r = self.kill("--discard")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--reason", r.stdout)
        self.assertTrue(os.path.isdir(wt))
        self.assertNotIn(["kill-window", "-t", "=crew-acme-widgets:10"], self.calls())

    def test_discard_keeps_worktree_when_post_fails(self):
        wt = self.builder()
        self.commit(wt)
        self.gh_exit = 1
        self.write_gh()
        r = self.kill("--discard", "--reason", "x")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not recorded", r.stdout)
        self.assertTrue(os.path.isdir(wt))

    def test_reviewer_worktree_removed_and_pr_discard_posts_on_pr(self):
        self.pr(9, "claude-code opus-5.5 default")
        self.assertEqual(self.spawn("reviewer", "--pr", "9").returncode, 0)
        wt = self.record("vera-9-r1-review")["worktree"]
        r = self.crew("kill", "vera-9-r1-review", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)  # PR head is on the remote: nothing unlanded
        self.assertFalse(os.path.exists(wt))
        self.pr(10, "codex gpt-6.1-sol medium")
        self.assertEqual(self.spawn("reviewer", "--pr", "10").returncode, 0)
        wt = self.record("vera-10-r1-review")["worktree"]
        with open(os.path.join(wt, "notes.txt"), "w") as f:
            f.write("x\n")
        r = self.crew("kill", "vera-10-r1-review", "--project", self.project, "--discard", "--reason", "scratch")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(wt))
        (call,) = self.gh_calls()
        self.assertEqual(call[:4], ["pr", "review", "10", "--comment"])

    def test_down_refuses_and_names_windows_with_unlanded_work(self):
        wt = self.builder()
        with open(os.path.join(wt, "wip.txt"), "w") as f:
            f.write("x\n")
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ben-7", r.stdout)
        self.assertIn("refusing down", r.stdout)
        self.assertTrue(os.path.isdir(wt))
        self.assertNotIn("kill-session", [c[0] for c in self.calls()])


class Send(Base):
    """crew send / acked: one JSON line in the inbox, a fixed nudge, refs only, delivery proven by ack: <id>."""

    def setUp(self):
        super().setUp()
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash", "10": "ben-7"}}, f)
        self.env["CREW_ROLE"] = "coordinator"
        self.env.pop("CREW_ID", None)

    def send(self, *args):
        return self.crew("send", *args, "--project", self.project)

    def inbox(self, window="ben-7"):
        with open(os.path.join(self.state, "inbox", window + ".jsonl")) as f:
            return [json.loads(line) for line in f]

    def test_append_format_and_nudge(self):
        sha = "a" * 40
        r = self.send("ben-7", "fix", "#171", sha, "https://github.com/acme/widgets/pull/171", "docs/x.md")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r2 = self.send("ben-7", "ci-red", "#171")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        first, second = self.inbox()
        self.assertEqual(sorted(first), ["from", "id", "kind", "refs", "ts"])
        self.assertEqual(first["kind"], "fix")
        self.assertEqual(first["refs"], ["#171", sha, "https://github.com/acme/widgets/pull/171", "docs/x.md"])
        self.assertEqual(first["from"], "coordinator")
        self.assertRegex(first["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertNotEqual(first["id"], second["id"])
        self.assertIn("sent %s to ben-7" % first["id"], r.stdout)
        keys = [c for c in self.calls() if c[0] == "send-keys"]
        self.assertEqual(keys[:2], [["send-keys", "-t", "=crew-acme-widgets:10", "-l", "inbox: " + first["id"]],
                                    ["send-keys", "-t", "=crew-acme-widgets:10", "Enter"]])
        self.assertEqual(len(keys), 4)

    def test_oversized_or_payload_rejected(self):
        diff = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
        for refs in [["p" * 201], ["d/" + "y" * 198] * 5, [diff], ["---a/x"], ["@@"],
                     ["Traceback"], ["two words"], ["#171", "line\nbreak"]]:
            r = self.crew("send", "--project", self.project, "ben-7", "fix", "--", *refs)  # --: refs may start with -
            self.assertEqual(r.returncode, 2, (refs, r.stdout, r.stderr))
            self.assertIn("refusing send", r.stdout)
        self.assertIn("over 1024", self.send("ben-7", "fix", *["d/" + "y" * 198] * 5).stdout)  # each ref legal
        self.assertEqual(self.send("ben-7", "Fix it", "#1").returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ben-7.jsonl")))
        self.assertEqual([c for c in self.calls() if c[0] == "send-keys"], [])

    def test_unknown_window_refused(self):
        r = self.send("ben-8", "fix", "#1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no window ben-8", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ben-8.jsonl")))
        self.assertEqual([c for c in self.calls() if c[0] == "send-keys"], [])

    def test_ack_only_from_status_file(self):
        r = self.crew("send", "ben-7", "fix", "#1", "--wait-ack", "0.3", "--project", self.project)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        msg_id = self.inbox()[0]["id"]
        self.assertIn("no ack: " + msg_id, r.stdout)
        acked = ["acked", "ben-7", msg_id, "--project", self.project]
        self.assertEqual(self.crew(*acked).returncode, 3)
        self.put("status/ben-7.status", "ack: other-id #1\ndone: #1 inbox: %s\n" % msg_id)
        self.assertEqual(self.crew(*acked).returncode, 3)
        self.put("status/ben-7.status", "done: #1\nack: %s #1\n" % msg_id)
        r = self.crew(*acked)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("acked " + msg_id, r.stdout)

    def test_wait_ack_sees_late_ack(self):
        status = os.path.join(self.state, "status", "ben-7.status")
        os.makedirs(os.path.dirname(status), exist_ok=True)
        # A stand-in role: acks whatever id lands in the inbox, a moment after the send.
        role = subprocess.Popen([sys.executable, "-c", textwrap.dedent("""\
            import json, os, sys, time
            inbox, status = sys.argv[1:]
            while not os.path.exists(inbox):
                time.sleep(0.05)
            time.sleep(0.3)
            open(status, "a").write("ack: %s\\n" % json.loads(open(inbox).readline())["id"])
            """), os.path.join(self.state, "inbox", "ben-7.jsonl"), status])
        self.addCleanup(role.wait)
        r = self.crew("send", "ben-7", "review", "#9", "--wait-ack", "10", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("acked " + self.inbox()[0]["id"], r.stdout)



POLL = os.path.join(HERE, "fixtures", "poll")
HEAD = "1" * 40
# Fake gh: serves $FAKE_GH_DIR/{prs,issues,pr-<n>}.json for pr list / issue list / pr view; logs every call.
FAKE_GH = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    args, d = sys.argv[1:], os.environ["FAKE_GH_DIR"]
    with open(os.path.join(d, "gh.log"), "a") as f:
        f.write(json.dumps(args) + "\\n")
    name = {("pr", "list"): "prs", ("issue", "list"): "issues"}.get(tuple(args[:2])) or "pr-" + args[2]
    sys.stdout.write(open(os.path.join(d, name + ".json")).read())
    """)


def fixture(name):
    with open(os.path.join(POLL, name)) as f:
        return json.load(f)


def load_crew():
    from importlib.machinery import SourceFileLoader
    import importlib.util
    loader = SourceFileLoader("crew_cli", CREW)
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
    loader.exec_module(mod)
    return mod


class PollDecide(unittest.TestCase):
    """The pure decision function on recorded gh JSON fixtures: each change is one event for one consumer."""

    @classmethod
    def setUpClass(cls):
        cls.crew = load_crew()

    def decide(self, before, after, issues_before="issues-none.json", issues_after="issues-none.json"):
        _, state = self.crew.decide({}, fixture(before), fixture(issues_before))
        return self.crew.decide(state, fixture(after), fixture(issues_after))

    def only(self, before, after, **kw):
        events, _ = self.decide(before, after, **kw)
        return [(e["event"], e["consumer"], e["refs"]) for e in events]

    def test_ci_passed_to_reviewer(self):
        self.assertEqual(self.only("prs-pending.json", "prs-ci-passed.json"),
                         [("ci-passed", "reviewer", ["#171", HEAD])])

    def test_ci_failed_to_builder(self):
        self.assertEqual(self.only("prs-pending.json", "prs-ci-failed.json"),
                         [("ci-failed", "builder", ["#171", HEAD])])

    def test_changes_verdict_to_builder(self):
        self.assertEqual(self.only("prs-ci-passed.json", "prs-changes.json"),
                         [("review-changes-requested", "builder", ["#171", HEAD])])

    def test_pass_verdict_to_synthesizer(self):
        self.assertEqual(self.only("prs-ci-passed.json", "prs-approved.json"),
                         [("review-approved", "synthesizer", ["#171", HEAD])])

    def test_merged_to_coordinator_and_dropped(self):
        _, state = self.crew.decide({}, fixture("prs-approved.json"), [])
        events, state = self.crew.decide(state, fixture("prs-none.json") + [fixture("pr-171-merged.json")], [])
        self.assertEqual([(e["event"], e["consumer"]) for e in events], [("pr-merged", "coordinator")])
        self.assertNotIn("171", state["prs"])
        closed = dict(fixture("pr-171-merged.json"), state="CLOSED")
        self.assertEqual([e["event"] for e in self.crew.decide({"prs": {"171": {}}}, [closed], [])[0]], ["pr-closed"])

    def test_no_change_nothing(self):
        for name in ["prs-pending.json", "prs-ci-passed.json", "prs-ci-failed.json", "prs-changes.json",
                     "prs-approved.json"]:
            self.assertEqual(self.only(name, name, issues_before="issues-ready.json",
                                       issues_after="issues-ready.json"), [], name)

    def test_assigned_ready_issue_to_builder(self):
        self.assertEqual(self.only("prs-pending.json", "prs-pending.json", issues_after="issues-ready.json"),
                         [("issue-assigned", "builder", ["#134"])])

    def test_hidden_marker_at_head_only_and_non_crew_pr_ignored(self):
        _, state = self.crew.decide({}, fixture("prs-ci-passed.json"), [])
        self.assertEqual(state["prs"], {"171": {"head": HEAD, "ci": "passed", "verdict": None}})

    def test_every_event_has_exactly_one_consumer(self):
        self.assertEqual(sorted(self.crew.CONSUMER), sorted(["ci-passed", "ci-failed", "review-changes-requested",
                                                             "review-approved", "pr-merged", "pr-closed",
                                                             "issue-assigned"]))
        self.assertTrue(all(isinstance(v, str) for v in self.crew.CONSUMER.values()))


class Poll(Base):
    """crew poll --once against a fake gh: baseline, one wake record per change, read-only gh calls."""

    def setUp(self):
        super().setUp()
        self.gh_dir = os.path.join(self.tmp, "gh")
        os.makedirs(self.gh_dir)
        fake = os.path.join(self.tmp, "bin", "gh")
        with open(fake, "w") as f:
            f.write(FAKE_GH)
        os.chmod(fake, 0o755)
        self.env["FAKE_GH_DIR"] = self.gh_dir

    def serve(self, prs, issues="issues-none.json", **views):
        for dst, src in [("prs", prs), ("issues", issues)] + [("pr-" + n, s) for n, s in views.items()]:
            shutil.copy(os.path.join(POLL, src), os.path.join(self.gh_dir, dst + ".json"))
        r = self.crew("poll", "--once", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def queue(self):
        path = os.path.join(self.state, "wake", "queue.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f]

    def test_once_baseline_then_one_record_per_change(self):
        self.assertIn("baseline", self.serve("prs-pending.json"))
        self.assertEqual(self.queue(), [])
        out = self.serve("prs-ci-passed.json")
        self.assertIn("ci-passed -> reviewer #171 " + HEAD, out)
        (rec,) = self.queue()
        self.assertEqual(sorted(rec), ["consumer", "event", "id", "reason", "refs", "source", "ts"])
        self.assertEqual((rec["source"], rec["reason"], rec["event"], rec["consumer"], rec["refs"]),
                         ("poll", "poll", "ci-passed", "reviewer", ["#171", HEAD]))
        self.serve("prs-ci-passed.json")
        self.assertEqual(len(self.queue()), 1)
        self.serve("prs-none.json", **{"171": "pr-171-merged.json"})
        self.assertEqual([(r["event"], r["consumer"]) for r in self.queue()[1:]], [("pr-merged", "coordinator")])
        with open(os.path.join(self.state, "poll-state.json")) as f:
            self.assertEqual(json.load(f)["prs"], {})
        with open(os.path.join(self.gh_dir, "gh.log")) as f:
            calls = [json.loads(line) for line in f]
        self.assertTrue(all(c[:2] in (["pr", "list"], ["issue", "list"], ["pr", "view"]) for c in calls), calls)
        self.assertIn(["pr", "view", "171", "-R", "acme/widgets", "--json",
                       "number,state,headRefOid,labels,statusCheckRollup,reviews"], calls)


class Observe(Base):
    """crew attach / logs (#138) against the fake tmux: attach is read-only by default and never changes the layout."""

    def setUp(self):
        super().setUp()
        self.session = {"0": "ash", "1": "sam", "10": "ben-7", "11": "ben-8", "20": "vera-9-r1-review"}
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": self.session}, f)

    def attach(self, *args):
        return self.crew("attach", *args, "--project", self.project)

    def attaches(self):
        return [c for c in self.calls() if c[0] == "attach-session"]

    def test_attach_window_read_only_by_default(self):
        r = self.attach("ben-7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.attaches(), [["attach-session", "-r", "-t", "=crew-acme-widgets:10"]])
        self.assertEqual(self.attach("ben-8", "--rw").returncode, 0)
        self.assertEqual(self.attaches()[1], ["attach-session", "-t", "=crew-acme-widgets:11"])

    def test_attach_by_role(self):
        for role, index in [("reviewer", 20), ("coordinator", 0), ("synthesizer", 1)]:
            self.assertEqual(self.attach(role).returncode, 0, role)
            self.assertEqual(self.attaches()[-1], ["attach-session", "-r", "-t", "=crew-acme-widgets:%d" % index])
        r = self.attach("builder")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ben-7, ben-8", r.stdout)
        self.assertEqual(len(self.attaches()), 3)

    def test_attach_refuses_unknown_window_and_missing_session(self):
        r = self.attach("ben-99")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no window ben-99", r.stdout)
        os.remove(self.state_file)
        r = self.attach("ben-7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not running", r.stdout)
        self.assertEqual(self.attaches(), [])

    def test_attach_builders_temporary_tiled_view_keeps_layout(self):
        r = self.attach("builders")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.calls()
        new = [c for c in calls if c[0] == "new-session"]
        self.assertEqual(len(new), 1)
        view = new[0][new[0].index("-s") + 1]
        self.assertTrue(view.startswith("crew-acme-widgets-builders-"), view)
        splits = [c for c in calls if c[0] == "split-window"]
        self.assertEqual(len(splits), 1)
        self.assertIn("capture-pane -p -t '=crew-acme-widgets:10' ", new[0][-1])
        self.assertIn("capture-pane -p -t '=crew-acme-widgets:11' ", splits[0][-1])
        self.assertIn(["select-layout", "-t", "=%s:" % view, "tiled"], calls)
        self.assertEqual(self.attaches(), [["attach-session", "-r", "-t", "=" + view]])
        self.assertEqual(calls[-1], ["kill-session", "-t", "=" + view])
        crew_targets = [c for c in calls if "-t" in c and c[c.index("-t") + 1].startswith("=crew-acme-widgets")
                        and not c[c.index("-t") + 1].startswith("=" + view)]
        self.assertEqual({c[0] for c in crew_targets}, {"has-session", "list-windows"})
        with open(self.state_file) as f:
            self.assertEqual(json.load(f), {"crew-acme-widgets": self.session})

    def test_attach_builders_without_builders(self):
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash"}}, f)
        r = self.attach("builders")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no builder windows", r.stdout)
        self.assertEqual([c for c in self.calls() if c[0] in ("new-session", "attach-session")], [])

    def summary(self, wt, rel, lines, mtime):
        path = os.path.join(wt, ".crew", "runs", rel, "summary.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.utime(path, (mtime, mtime))
        return path

    def test_logs_tails_newest_summary_only(self):
        wt = os.path.join(self.tmp, "state", "wt", "7-abcdef0-builder-build")
        self.put("runs/ben-7.json", json.dumps({"worktree": wt}))
        self.summary(wt, "issue-7/r1", ["old step"], 1000)
        newest = self.summary(wt, "pr-12/r2", ["# Run summary", "- build ok", "- unit-tests fail"], 2000)
        steps = os.path.join(os.path.dirname(newest), "steps")
        os.makedirs(steps)
        with open(os.path.join(steps, "unit-tests.log"), "w") as f:
            f.write("RAW LOG LINE\n")
        r = self.crew("logs", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(newest, r.stdout)
        self.assertIn("- unit-tests fail", r.stdout)
        self.assertNotIn("old step", r.stdout)
        self.assertNotIn("RAW LOG LINE", r.stdout)
        r = self.crew("logs", "ben-7", "-n", "1", "--project", self.project)
        self.assertEqual(r.stdout.splitlines()[1:], ["- unit-tests fail"])

    def test_logs_follow_execs_tail(self):
        wt = os.path.join(self.tmp, "wt-7")
        self.put("runs/ben-7.json", json.dumps({"worktree": wt}))
        path = self.summary(wt, "issue-7/r1", ["- build ok"], 1000)
        tail = os.path.join(self.tmp, "bin", "tail")
        with open(tail, "w") as f:
            f.write('#!/bin/sh\necho "tail $*"\n')
        os.chmod(tail, 0o755)
        r = self.crew("logs", "ben-7", "-f", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "tail -n 20 -f " + path)

    def test_logs_refuses_without_run_or_summary(self):
        r = self.crew("logs", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no run ben-7", r.stdout)
        self.put("runs/ben-7.json", json.dumps({"worktree": os.path.join(self.tmp, "wt-7")}))
        r = self.crew("logs", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no step summary yet", r.stdout)


class LandLock(Base):
    """crew land-lock (#136): serial land under flock on locks/merge.lock."""

    def lock(self, action):
        return self.crew("land-lock", action, "--project", self.project)

    def test_second_acquire_fails_fast_and_down_refuses_until_release(self):
        self.addCleanup(self.lock, "release")
        r = self.lock("acquire")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("acquired", r.stdout)
        r = self.lock("acquire")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is held", r.stdout)
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash", "1": "sam"}}, f)
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("land lock", r.stdout)
        r = self.lock("release")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.state, "locks", "merge.pid")))
        self.assertEqual(self.lock("acquire").returncode, 0)
        self.assertEqual(self.lock("release").returncode, 0)
        self.assertEqual(self.crew("down", "--project", self.project).returncode, 0)

    def test_acquire_fails_fast_against_another_holder(self):
        os.makedirs(os.path.join(self.state, "locks"))
        with open(os.path.join(self.state, "locks", "merge.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            r = self.lock("acquire")
            self.assertEqual(r.returncode, 1)
            r = self.lock("release")
            self.assertEqual(r.returncode, 1)
            self.assertIn("nothing signalled", r.stdout)
        self.assertEqual(self.lock("release").returncode, 0)

    def pidfile(self, rec=None):
        path = os.path.join(self.state, "locks", "merge.pid")
        if rec is not None:
            with open(path, "w") as f:
                json.dump(rec, f)
        with open(path) as f:
            return json.load(f)

    def test_matching_holder_released_and_recorded_with_start_time(self):
        self.assertEqual(self.lock("acquire").returncode, 0)
        rec = self.pidfile()
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(rec["pid"])], capture_output=True, text=True).stdout
        self.assertEqual(rec["start"], out.strip())
        r = self.lock("release")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("released", r.stdout)

    def test_stale_pid_file_with_other_holder_signals_nothing(self):
        bystander = subprocess.Popen(["sleep", "30"])
        self.addCleanup(bystander.wait)
        self.addCleanup(bystander.kill)
        start = subprocess.run(["ps", "-o", "lstart=", "-p", str(bystander.pid)], capture_output=True,
                               text=True).stdout.strip()
        os.makedirs(os.path.join(self.state, "locks"))
        self.pidfile({"pid": bystander.pid, "start": start})  # live PID, matching start, but not a lock holder
        with open(os.path.join(self.state, "locks", "merge.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            r = self.lock("release")
        self.assertEqual(r.returncode, 1)
        self.assertIn("nothing signalled", r.stdout)
        self.assertIsNone(bystander.poll())

    def test_reused_pid_with_other_start_time_signals_nothing(self):
        self.addCleanup(self.lock, "release")
        self.assertEqual(self.lock("acquire").returncode, 0)
        rec = self.pidfile()
        self.pidfile(dict(rec, start="Thu Jan  1 00:00:00 1970"))
        r = self.lock("release")
        self.assertEqual(r.returncode, 1)
        self.assertIn("nothing signalled", r.stdout)
        os.kill(rec["pid"], 0)  # holder still alive
        self.assertEqual(self.lock("acquire").returncode, 1)
        self.pidfile(rec)
        self.assertEqual(self.lock("release").returncode, 0)


class CapQueue(Spawn):
    """Per-band caps (#136): beyond the profile cap, crew spawn queues; crew dequeue spawns when a slot frees."""

    def setUp(self):
        super().setUp()
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('name = "tmux"\n', 'name = "tmux"\noptions = { builders = 2 }\n'))

    def queue(self):
        path = os.path.join(self.state, "spawn-queue.jsonl")
        with open(path) as f:
            return [json.loads(line) for line in f]

    def test_cap_reached_queues_and_dequeue_spawns_after_kill(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("builder", "--issue", "8").returncode, 0)
        r = self.spawn("builder", "--issue", "9")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("queued: builder build issue #9"), r.stdout)
        self.assertEqual(len(self.windows()), 2)
        self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue9")))
        q = self.queue()
        self.assertEqual([(e["role"], e["issue"], e["pass"]) for e in q], [("builder", 9, "build")])
        r = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertIn("no free slot", r.stdout)
        self.assertEqual(self.queue(), q)
        self.assertEqual(self.crew("kill", "ben-7", "--project", self.project).returncode, 0)
        r = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("started ben-9 (window 10", r.stdout)
        self.assertEqual(self.queue(), [])

    def test_bands_capped_separately_and_dequeue_skips_full_band(self):
        self.pr(5, "claude-code opus-5.5 default")
        self.pr(6, "claude-code opus-5.5 default")
        self.pr(4, "claude-code opus-5.5 default")
        for issue in ["7", "8", "9"]:
            self.spawn("builder", "--issue", issue)
        for pr in ["5", "6", "4"]:
            self.spawn("reviewer", "--pr", pr)
        self.assertEqual([(e["role"], e["issue"] or e["pr"]) for e in self.queue()], [("builder", 9), ("reviewer", 4)])
        self.assertEqual(self.crew("kill", "vera-5-r1-review", "--project", self.project).returncode, 0)
        r = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertIn("started vera-4-r1-review (window 20", r.stdout)
        self.assertEqual([e["issue"] for e in self.queue()], [9])


# Liveness (#135): a tmux wrapper answers the probe's pane query from $FAKE_PANES and passes every other call to
# the fake above; a fake `ps` answers start times and foreground names from $FAKE_PS.
FAKE_TMUX_PANES = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    def load(var):
        return json.load(open(os.environ[var])) if os.path.exists(os.environ[var]) else {}
    if args[0] == "display-message" and "#{pane_id}" in args[-1]:
        target = args[args.index("-t") + 1].lstrip("=")
        session, _, index = target.partition(":")
        state = load("FAKE_TMUX_STATE")
        if index not in state.get(session, {}):
            sys.exit(1)
        p = dict({"id": "%" + index, "pid": "4" + index, "dead": "0", "activity": "0",
                  "command": state.get("_panes", {}).get(target, "")}, **load("FAKE_PANES").get(target, {}))
        print(p["id"], p["pid"], p["dead"], p["activity"], "/dev/ttyp" + index, p["command"])
        sys.exit(0)
    os.execv(os.path.join(os.path.dirname(sys.argv[0]), "tmux-base"), ["tmux"] + args)
    """)
FAKE_PS = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    ps = json.load(open(os.environ["FAKE_PS"])) if os.path.exists(os.environ["FAKE_PS"]) else {}
    if "-p" in args:
        print(ps.get("start", {}).get(args[args.index("-p") + 1], "Fri Oct 30 10:00:00 2026"))
    else:
        for stat, comm in ps.get("fg", {}).get(args[args.index("-t") + 1], []):
            print(stat, comm)
    """)


class Liveness(Spawn):
    """crew status / restart and the C5 probe, with fake tmux panes and a fake ps."""
    locals().update(dict.fromkeys([n for n in dir(Spawn) if n.startswith("test_")]))  # run Spawn's tests once

    def setUp(self):
        super().setUp()
        bindir = os.path.join(self.tmp, "bin")
        os.rename(os.path.join(bindir, "tmux"), os.path.join(bindir, "tmux-base"))
        for name, text in [("tmux", FAKE_TMUX_PANES), ("ps", FAKE_PS)]:
            with open(os.path.join(bindir, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(bindir, name), 0o755)
        self.panes, self.ps = os.path.join(self.tmp, "panes.json"), os.path.join(self.tmp, "ps.json")
        self.env.update(FAKE_PANES=self.panes, FAKE_PS=self.ps)
        loader = importlib.machinery.SourceFileLoader("crew_cli", CREW)
        self.mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
        loader.exec_module(self.mod)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.set_pane(10)

    def set_pane(self, index, **kv):
        with open(self.panes, "w") as f:
            json.dump({"crew-acme-widgets:%d" % index: kv}, f)

    def probe(self, name="ben-7"):
        with mock.patch.dict(os.environ, self.env):
            windows = dict((n, i) for i, n in self.mod.tmux.list_windows("crew-acme-widgets"))
            return self.mod.probe("crew-acme-widgets", name, self.record(name), windows)

    def test_spawn_records_run_identity(self):
        rec = self.record("ben-7")
        self.assertEqual((rec["pane_id"], rec["pane_pid"], rec["pane_start"]), ("%10", "410", "Fri Oct 30 10:00:00 2026"))
        self.assertEqual(rec["args"], {"issue": 7, "pr": None, "pass": "build", "round": 1, "tier": "default"})

    def test_probe_classes(self):
        self.assertEqual(self.probe(), "alive")
        self.set_pane(10, command="node")
        self.assertEqual(self.probe(), "ambiguous")
        with open(self.ps, "w") as f:
            json.dump({"fg": {"/dev/ttyp10": [["S+", "/usr/local/bin/codex"]]}}, f)
        self.assertEqual(self.probe(), "alive")
        os.remove(self.ps)
        self.set_pane(10, dead="1")
        self.assertEqual(self.probe(), "dead")
        self.set_pane(10)
        with open(self.ps, "w") as f:  # pid reused by another process
            json.dump({"start": {"410": "Fri Oct 30 11:00:00 2026"}}, f)
        self.assertEqual(self.probe(), "missing")
        os.remove(self.ps)
        self.set_pane(10, id="%99", pid="499")  # a new window with the same name and harness
        self.assertEqual(self.probe(), "missing")
        self.set_pane(10)
        with open(self.state_file) as f:
            state = json.load(f)
        state["crew-acme-widgets"].pop("10")
        with open(self.state_file, "w") as f:
            json.dump(state, f)
        self.assertEqual(self.probe(), "missing")

    def test_status_table(self):
        self.put("status/ben-7.status", "ack: m1\nblocked: needs a decision on #7\n")
        r = self.crew("status", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stderr)
        head, row = r.stdout.splitlines()
        self.assertEqual(head.split(), ["WINDOW", "ROLE", "ITEM", "HEAD", "BEAT", "LIVENESS", "LAST"])
        base = self.git("rev-parse", "--short=7", "origin/main")
        self.assertEqual(row.split()[:8], ["ben-7", "builder", "issue", "#7", base, "0m", "alive", "blocked:"])

    def test_restart_only_dead_or_missing_and_once(self):
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ben-7 is alive", r.stdout)
        self.set_pane(10, dead="1")
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.windows()), 2)
        self.assertEqual(self.record("ben-7")["restarts"], 1)
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("already restarted once; escalate", r.stdout)
        self.assertEqual(len(self.windows()), 2)

    def test_restart_refuses_finished_run(self):
        self.set_pane(10, dead="1")
        self.put("status/ben-7.status", "done: PR #12\n")
        r = self.crew("restart", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("finished", r.stdout)

    def test_up_rebuilds_ash_from_disk_without_respawning_runs(self):
        self.crew("down", "--project", self.project)
        self.put("runs/ben-7.json", json.dumps({"index": 10, "role": "builder", "item": "issue #7"}))
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("recorded runs now probe missing: ben-7", r.stdout)
        self.assertEqual(len(self.windows()), 1)  # only the original spawn, no respawn


if __name__ == "__main__":
    unittest.main()
