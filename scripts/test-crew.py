#!/usr/bin/env python3
"""Tests for scripts/crew up / down / guard with a fake `tmux` binary on PATH (stdlib only)."""
import fcntl
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

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


if __name__ == "__main__":
    unittest.main()
