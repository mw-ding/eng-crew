"""mdstack runner tests on a fake SSH transport and a temp checkout with fake local checks; no network or real host.

Usage: python3 dev/tests/environments/test-crew-runner.py
"""
import json
import os
import subprocess
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base, CREW

FAKE_SSH = '''#!/usr/bin/env python3
import json, os, sys
if "-G" in sys.argv:
    print("hostname " + sys.argv[-1])
    sys.exit(0)
request, host = json.load(sys.stdin), sys.argv[-2]
with open(os.environ["FAKE_SSH_LOG"], "a") as f:
    f.write(json.dumps(dict(request, host=host)) + "\\n")
with open(os.environ["FAKE_SSH_LOG"]) as f:
    n = sum(json.loads(line)["verb"] == request["verb"] and json.loads(line)["host"] == host for line in f) - 1
script = json.loads(os.environ["FAKE_RUNNER"])
replies = script.get(host + ":" + request["verb"]) or script[request["verb"]]
reply = replies[min(n, len(replies) - 1)]
if reply == 255:
    sys.exit(255)
print(json.dumps(reply))
'''
CHECK = dict(result="ok", checks=[dict(status="ok", check=n, detail="passed") for n in ("tools", "project mirror")],
             projects=["acme__widgets"], load=1)
RUNNING = dict(result="ok", status="running")


def done(*codes):
    return dict(result="ok", status="done", job_id="j", head="h", commands=[
        dict(command=c, exit=code, duration=0.1, log="jobs/j/%d-%s.log" % (i, c), tail="%s tail\n" % c)
        for i, (c, code) in enumerate(zip(("check-repo", "tests"), codes))])


class Runner(Base):
    def setUp(self):
        super().setUp()
        with open(self.project, "a") as f:
            f.write('[hosts.host-a]\nprimary = true\nmax_runs = 2\n'
                    'capabilities = { os = "linux", arch = "x86_64", engines = ["codex"] }\n'
                    '[hosts.host-c]\nforge = false\nmax_runs = 4\ncapabilities = { os = "linux", arch = "x86_64" }\n')
        os.makedirs(os.path.join(self.project_dir, "scripts"))
        os.makedirs(os.path.join(self.project_dir, "dev", "tests", "x"))
        for name in ("scripts/check-repo.py", "scripts/run-tests.py", "dev/tests/x/test-a.py"):
            with open(os.path.join(self.project_dir, name), "w") as f:
                f.write("import os, sys\nopen(os.environ.get('LOCAL_LOG', os.devnull), 'a').write(' '.join(sys.argv) + '\\n')\n"
                        "print('local %s')\nsys.exit(int(os.environ.get('LOCAL_EXIT', '0')))\n" % os.path.basename(name))
        git = ["git", "-c", "user.name=t", "-c", "user.email=t", "-C", self.project_dir]
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "init"]):
            subprocess.run(git + args, check=True, capture_output=True)
        self.head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        with open(os.path.join(self.tmp, "bin", "ssh"), "w") as f:
            f.write(FAKE_SSH)
        os.chmod(os.path.join(self.tmp, "bin", "ssh"), 0o755)
        self.ssh_log, self.local_log = os.path.join(self.tmp, "ssh.log"), os.path.join(self.tmp, "local.log")
        self.env.update(FAKE_SSH_LOG=self.ssh_log, LOCAL_LOG=self.local_log, CREW_PROJECT=self.project)
        self.script(result=[RUNNING, done(0, 0)])

    def script(self, hosts=None, **verbs):
        """Replies per verb, or per `host:verb` in hosts; each call takes the next, the last repeats; 255 = no transport."""
        base = dict(check=[CHECK], seed=[dict(result="ok", step="seed", tip="t")], job=[RUNNING])
        self.env["FAKE_RUNNER"] = json.dumps(dict(base, **verbs, **(hosts or {})))

    def runner(self, *args, head=None):
        argv = args or ("run", "--head", head or self.head, "--poll", "0", "--", "check-repo", "dev/tests/x/test-a.py")
        return subprocess.run([sys.executable, CREW, "runner", *argv], capture_output=True, text=True,
                              env=self.env, cwd=self.project_dir)

    def requests(self, verb=None):
        if not os.path.exists(self.ssh_log):
            return []
        with open(self.ssh_log) as f:
            return [r for r in map(json.loads, f) if verb in (None, r["verb"])]

    def local(self):
        if not os.path.exists(self.local_log):
            return []
        with open(self.local_log) as f:
            return [line.split()[0].rsplit("/", 1)[1] for line in f]

    def stored(self):
        path = os.path.join(self.state, "runner")
        return os.listdir(path) if os.path.isdir(path) else []

    def test_remote_pass_stores_result_and_prints_reference(self):
        r = self.runner()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        job = self.requests("job")[0]
        self.assertRegex(job["job_id"], "^%s-[0-9a-f]{12}$" % self.head[:7])
        self.assertIn("runner:host-c/%s head=%s\ncheck-repo exit 0\ntests exit 0\n" % (job["job_id"], self.head), r.stdout)
        self.assertEqual((job["head"], job["project"], job["root"]), (self.head, "acme__widgets", "~/.mdstack"))
        self.assertEqual(job["commands"], [dict(command="check-repo"), dict(command="tests", files=["test-a.py"])])
        seed = self.requests("seed")[0]
        self.assertTrue(seed["bundle"] and "branch" not in seed)
        self.assertEqual([r["verb"] for r in self.requests()], ["check", "seed", "job", "result", "result"])
        self.assertEqual(self.stored(), [job["job_id"]])
        with open(os.path.join(self.state, "runner", job["job_id"], "result.json")) as f:
            stored = json.load(f)
        self.assertEqual(stored["host"], "host-c")
        self.assertEqual(stored["spec"], job["commands"])
        self.assertEqual(self.local(), [])
        r = self.runner("logs", job["job_id"], "tests")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout, "== tests exit 0 (jobs/j/1-tests.log)\ntests tail\n\n")

    def test_address_is_the_ssh_destination(self):
        """#1034: every runner call goes to the host's `address`; the stored result keeps the label."""
        with open(self.project) as f:
            text = f.read().replace("[hosts.host-c]\n", '[hosts.host-c]\naddress = "host-c.region.example.com"\n')
        with open(self.project, "w") as f:
            f.write(text)
        r = self.runner()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual({req["host"] for req in self.requests()}, {"host-c.region.example.com"})
        job_id = self.requests("job")[0]["job_id"]
        self.assertIn("runner:host-c/%s" % job_id, r.stdout)
        self.assertEqual(self.runner("logs", job_id).returncode, 0)
        self.assertEqual(self.requests()[-1]["host"], "host-c.region.example.com")

    def test_remote_red_is_a_red_run_not_a_fallback(self):
        self.script(result=[done(0, 1)])
        r = self.runner()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("check-repo exit 0\ntests exit 1\n", r.stdout)
        self.assertNotIn("ran locally", r.stdout)
        self.assertEqual(self.local(), [])

    def test_unreachable_three_polls_in_a_row_runs_locally(self):
        self.script(result=[RUNNING, 255, 255, 255, done(0, 0)])
        r = self.runner()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("runner: host-c unreachable; ran locally\nlocal head=%s\n" % self.head, r.stdout)
        self.assertIn("check-repo exit 0\ntests exit 0\n", r.stdout)
        self.assertEqual(self.local(), ["check-repo.py", "run-tests.py"])
        self.assertEqual(len(self.requests("result")), 4)

    def test_transport_blip_under_three_keeps_the_remote_run(self):
        self.script(result=[255, 255, done(0, 0)])
        r = self.runner()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("runner:host-c/", r.stdout)
        self.assertEqual(self.local(), [])

    def test_late_remote_result_is_discarded(self):
        self.script(job=[255], result=[done(1, 1)])
        r = self.runner()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("runner: host-c unreachable; ran locally", r.stdout)
        jobs = self.requests("job")
        self.assertEqual(len(jobs), 3)
        self.assertEqual({j["request_id"] for j in jobs}, {jobs[0]["request_id"]})
        self.assertEqual(self.requests("result"), [])
        self.assertEqual(self.stored(), [])
        self.assertNotIn("exit 1", r.stdout)

    def test_refused_runs_locally_with_the_reason(self):
        for verb in ("seed", "job"):
            if os.path.exists(self.local_log):
                os.remove(self.local_log)
            self.script(**{verb: [dict(result="refused", reason="head not in the host mirror")]})
            self.env["LOCAL_EXIT"] = "1"
            r = self.runner()
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("runner: host-c refused: head not in the host mirror; ran locally", r.stdout)
            self.assertIn("check-repo exit 1\ntests exit 1\n", r.stdout)
            self.assertEqual(self.local(), ["check-repo.py", "run-tests.py"])
        self.assertEqual(self.stored(), [])

    def test_no_forge_less_host_runs_locally(self):
        self.write_profile()
        r = self.runner()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(r.stdout.startswith("runner: no forge-less host; ran locally\nlocal head="), r.stdout)
        self.assertEqual(self.local(), ["check-repo.py", "run-tests.py"])
        self.assertEqual(self.requests(), [])

    def test_picks_lowest_load_ready_host_or_named_host(self):
        with open(self.project, "a") as f:
            f.write('[hosts.host-d]\nforge = false\nmax_runs = 8\ncapabilities = { os = "linux", arch = "x86_64" }\n'
                    '[hosts.host-e]\nforge = false\nmax_runs = 1\ncapabilities = { os = "linux", arch = "x86_64" }\n')
        self.script({"host-d:check": [dict(CHECK, load=1)], "host-e:check": [dict(CHECK, load=0, projects=[])]},
                    result=[done(0, 0)])
        r = self.runner()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.requests("job")[0]["host"], "host-d")
        r = self.runner("run", "--host", "host-c", "--head", self.head, "--poll", "0", "--", "check-repo")
        self.assertIn("runner:host-c/", r.stdout)
        self.assertEqual(self.requests("job")[-1]["commands"], [dict(command="check-repo")])

    def test_loopback_through_the_real_entrypoint(self):
        """The fake SSH hands the request to crew-remote.py itself: real seed, job and result verbs on a temp root."""
        root = os.path.join(self.tmp, "host-root")
        with open(self.project, "a") as f:
            f.write('[hosts.host-l]\nforge = false\nmax_runs = 1\nroot = "%s"\n'
                    'capabilities = { os = "linux", arch = "x86_64" }\n' % root)
        with open(os.path.join(self.tmp, "bin", "ssh"), "w") as f:
            f.write("#!/bin/sh\ncase \"$*\" in *-G*) echo hostname host-l; exit 0;; esac\n"
                    "exec %s %s --root %s\n" % (sys.executable, os.path.join(os.path.dirname(os.path.dirname(CREW)), "environments", "terminal", "remote", "crew-remote.py"), root))
        r = self.runner("run", "--host", "host-l", "--head", self.head, "--poll", "0.2", "--", "check-repo", "test-a.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, "^runner:host-l/%s-[0-9a-f]{12} head=%s\ncheck-repo exit 0\ntests exit 0\n$"
                         % (self.head[:7], self.head))
        self.assertEqual(self.local(), [])
        job = self.stored()[0]
        r = self.runner("logs", job, "check-repo")
        self.assertEqual(r.stdout, "== check-repo exit 0 (jobs/%s/0-check-repo.log)\nlocal check-repo.py\n\n" % job)

    def test_bad_head_or_check_name_refused_before_any_call(self):
        r = self.runner(head="0" * 40)
        self.assertEqual(r.returncode, 2)
        self.assertIn("crew runner: the checkout is at %s, not --head %s" % (self.head, "0" * 40), r.stdout)
        r = self.runner("run", "--head", self.head, "--", "check-repo", "rm -rf")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not check-repo or a dev/tests/*/test-*.py name: rm -rf", r.stdout)
        self.assertEqual(self.runner("logs", "nope").stdout, "crew runner: no stored job nope\n")
        r = self.runner("run", "--host", "host-x", "--head", self.head, "--", "check-repo")
        self.assertEqual((r.returncode, r.stdout), (2, "crew runner: unknown inventory host host-x\n"))
        self.assertEqual(self.requests() + self.local(), [])


if __name__ == "__main__":
    unittest.main()
