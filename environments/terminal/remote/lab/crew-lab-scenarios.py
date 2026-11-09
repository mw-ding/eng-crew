#!/usr/bin/env python3
"""Local lab runner scenarios over the real hardened SSH call, with failure injection (M20.1 lab F, #1360).

Usage: crew-lab-scenarios.py MANIFEST --stage DIR [--host ALIAS] [--only NAME ...]

MANIFEST is a campaign run manifest that crew-lab-docker.py setup brought up in loopback mode from --stage DIR. The
primary's client is that staged bundle, verified and extracted under lab/toolkit/ by scripts/crew-install.py, so
both ends run one version. macOS ssh reads ~/.ssh/config from the account's home, never HOME, so lab/bin/ssh adds
`-F lab/home/.ssh/config` to `ssh -G` only; each call still runs the client's own `-F none` argv. The sample repo
(branch `lab` of the sandbox repo) has check-repo and dev/tests/lab/test-lab.py, which can go red or sleep.
Every scenario prints PASS or FAIL; lab/scenarios.json keeps what it saw, and crew-lab-evidence.py writes the run's
evidence record under lab/runs/ (#1361). Exit 1 on any FAIL, 2 on a refusal.
  exact-head  a job at HEAD stores its result and matches the same commands run locally; the host job sees none of
              the decoy GH_TOKEN, GITHUB_TOKEN, SSH_AUTH_SOCK or CREW_* the client carries
  red         a red remote test is a red run, not a fallback, and is red locally too
  idempotent  a repeated request id returns its first reply; a new request id for a job id returns the first job
  stale       a head other than the checkout's is refused before any call; an unseeded head is refused by the host
  disconnect  network disconnect mid-job, container and runner pids kept: the client falls back locally; after
              reconnect the same job's result is pulled, and it ran once
  pause       pause mid-job (unresponsive host): the client falls back locally; after unpause the job finishes
  runner      runner-only kill once it is up: SSH still answers with sshd's pid kept; a new runner pid writes the
              heartbeat and `version` reports it up (never seen by the timeout is a FAIL); then a job passes
  recreate    container recreated mid-job (new ID, host key and port): the client falls back locally (unreachable
              while it is down, or the lost job refused), the host never reports that job done, and a fresh job passes
  partition   a role host behind a network disconnect is unreachable over SSH; placement queues a role run that
              needs that host and never places it elsewhere, and the item's claim file is unchanged
  attach      a run planted as crew in the runner's session (spawn needs a forge, #345): over real SSH `capture`
              shows its pane and `logs` its step summary tail; a client on a pty attaches read-only (typed keys
              never reach the pane) and detaches with exit 0; attach without a TTY and another verb with one are
              refused (#348)
Each disconnect and pause is confirmed by a `version` call that fails while it holds and answers once it is lifted;
runner and recreate prove their own outage as above.
"""
import argparse
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import select
import shutil
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE)))), "scripts")
DECOYS = dict(GH_TOKEN="lab-decoy", GITHUB_TOKEN="lab-decoy", SSH_AUTH_SOCK="/nonexistent/agent", CREW_LAB_DECOY="1")
ROOT, CHECKS = "~/.mdstack", ["check-repo", "test-lab.py"]
SPEC = [dict(command="check-repo"), dict(command="tests", files=["test-lab.py"])]
SAMPLE = {
    "scripts/check-repo.py": "import os, platform, re\nseen = sorted(k for k in os.environ if re.match("
                             "r'(GH_|GITHUB_|CREW_|SSH_AUTH_SOCK)', k))\nprint('check-repo ok on ' + "
                             "platform.system().lower())\nprint('env: ' + (' '.join(seen) or 'clean'))\n",
    "scripts/run-tests.py": "import os, subprocess, sys\nsys.exit(any(subprocess.run([sys.executable, os.path.join("
                            "'dev', 'tests', 'lab', t)]).returncode for t in sys.argv[1:]))\n",
}
TEST = "import sys, time\ntime.sleep(%d)\nprint('test-lab %s')\nsys.exit(%d)\n"
SSH = "/usr/bin/ssh"
SHIM = '#!/bin/sh\ncase " $* " in *" -G "*) exec %s -F %s "$@";; esac\nexec %s "$@"\n'


def module(name, path):
    spec = importlib.util.spec_from_loader(name, importlib.machinery.SourceFileLoader(name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


labd = module("crew_lab_docker", os.path.join(HERE, "crew-lab-docker.py"))
labe = module("crew_lab_evidence", os.path.join(HERE, "crew-lab-evidence.py"))


class Lab:
    def __init__(self, manifest, stage, host):
        self.path, self.stage, self.host = manifest, stage, host
        self.m = json.loads(Path(manifest).read_text())
        self.d, self.repo = labd.lab_dir(self.m), os.path.dirname(self.m["profile"]["path"])
        self.conf = os.path.join(self.d, "home", ".ssh", "config")
        self.project = "campaign__" + self.m["repo"].split("/", 1)[1]
        self.client_sha = None

    def refusals(self):
        lab = self.m.get("lab") or {}
        return labd.guard.refusals(self.m) + ([] if "port" in lab.get("hosts", {}).get(self.host, {}) else [
            "lab: no loopback host %s recorded; run crew-lab-docker.py setup without --n3" % self.host])

    def prepare(self):
        """The verified client toolkit, the ssh shim, both org profiles and the sample branch; then the lab env."""
        tag, toolkit = self.m["lab"]["tag"], os.path.join(self.d, "toolkit")
        shutil.rmtree(toolkit, ignore_errors=True)
        shutil.copytree(self.stage, toolkit + "-stage", dirs_exist_ok=True)
        install = module("crew_install", os.path.join(SCRIPTS, "crew-install.py"))
        sha, _ = install.verify(toolkit + "-stage", tag, toolkit)
        if sha not in self.m["lab"]["stage"].values():
            raise ValueError("bundle %s is not the one the lab hosts activated" % sha)
        self.client_sha = sha
        self.remote = module("lab_remote", os.path.join(toolkit, "environments/terminal/remote/crew-remote.py"))
        self.mdstack = module("lab_mdstack", os.path.join(toolkit, "cli", "mdstack"))
        os.makedirs(os.path.join(self.d, "bin"), exist_ok=True)
        Path(self.d, "bin", "ssh").write_text(SHIM % (SSH, self.conf, SSH))
        os.chmod(os.path.join(self.d, "bin", "ssh"), 0o755)
        primary = '[hosts.primary]\nprimary = true\nmax_runs = 2\ncapabilities = { os = "macos", arch = "arm64", ' \
                  'engines = ["claude-code"] }\n[hosts.%s]\nmax_runs = 2\nroot = "%s"\n' % (self.host, ROOT)
        Path(self.d, "org.toml").write_text(
            primary + 'forge = false\ncapabilities = { os = "linux", arch = "arm64" }\n')
        Path(self.d, "org-role.toml").write_text(
            primary + 'roles = ["builder"]\ncapabilities = { os = "linux", arch = "arm64", engines = ["claude-code"] }'
            '\n[[placement.rules]]\nrole = "builder"\nneeds = { os = "linux" }\n'
            '[identities]\nbuilder = { gh_user = "lab-bot", name = "Ben" }\n')
        env = labd.child_env(self.m)
        env["PATH"] = os.path.join(self.d, "bin") + os.pathsep + env.get("PATH", "/usr/bin:/bin")
        os.environ.clear()
        os.environ.update(env)
        self.git("checkout", "-q", "-B", "lab")
        for name, text in SAMPLE.items():
            os.makedirs(os.path.join(self.repo, os.path.dirname(name)), exist_ok=True)
            Path(self.repo, name).write_text(text)
        return self.commit()

    def git(self, *argv):
        return subprocess.run(["git", "-C", self.repo, "-c", "user.name=lab", "-c", "user.email=lab@lab", *argv],
                              check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, red=False, sleep=0):
        os.makedirs(os.path.join(self.repo, "dev", "tests", "lab"), exist_ok=True)
        Path(self.repo, "dev", "tests", "lab", "test-lab.py").write_text(TEST % (sleep, "red" if red else "ok", red))
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "lab: red=%s sleep=%d" % (red, sleep))
        return self.git("rev-parse", "HEAD")

    def client(self, head, org="org.toml", wait=True):
        argv = [sys.executable, os.path.join(self.d, "toolkit", "cli", "mdstack"), "runner", "run", "--poll", "1",
                "--project", self.m["profile"]["path"], "--org-profile", os.path.join(self.d, org), "--head", head,
                "--host", self.host, "--", *CHECKS]
        p = subprocess.Popen(argv, cwd=self.repo, env=dict(os.environ, **DECOYS), stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return p.communicate()[0].splitlines() + ["exit %d" % p.returncode] if wait else p

    def local(self):
        return [subprocess.run(self.remote.job_argv(c, self.repo), cwd=self.repo, stdin=subprocess.DEVNULL,
                               capture_output=True).returncode for c in SPEC]

    def call(self, verb, **fields):
        return self.remote.call(self.host, verb, config=self.conf, root=ROOT, **fields)

    def up(self):
        return self.call("version").get("result") == "ok"

    def cid(self):
        return self.m["lab"]["hosts"][self.host]["container"]

    def docker(self, *argv):
        return labd.docker(self.m, *argv)

    def pids(self):
        ps = self.docker("exec", self.cid(), "ps", "-eo", "pid=,args=").splitlines()
        find = lambda pat: next((int(line.split()[0]) for line in ps if re.search(pat, line)), None)
        return dict(runner=find(r"crew-remote\.py --root \S+ runner$"), sshd=find(r"sshd: .*\[listener\]"))

    def jobs(self):
        return set(self.docker("exec", "-u", "crew", self.cid(), "sh", "-c", "ls ~/.mdstack/jobs 2>/dev/null || true")
                   .split())

    def beat(self):
        """The host runner's runner.json heartbeat, or {} while it has none."""
        text = self.docker("exec", "-u", "crew", self.cid(), "sh", "-c",
                           "cat ~/.mdstack/runner.json 2>/dev/null || true")
        return json.loads(text) if text.strip() else {}

    def started(self, before, timeout=60):
        for _ in range(timeout):
            new = self.jobs() - before
            if new:
                return new.pop()
            time.sleep(1)
        return None

    def result(self, job_id, timeout=90):
        for _ in range(timeout):
            reply = self.call("result", job_id=job_id)
            if reply.get("status") != "running":
                return reply
            time.sleep(1)
        return reply

    def recreate(self):
        """Remove the host's recorded container and network (label-checked), then bring the host up again as setup
        does; the manifest and the per-run SSH config take the new IDs, port and host key."""
        lab, host = self.m["lab"], self.m["lab"]["hosts"][self.host]
        for rid in (host["container"], host["network"]):
            labels = json.loads(self.docker("inspect", rid))[0]
            labels = (labels.get("Config") or labels).get("Labels") or {}
            if (labels.get("mdstack.lab.owner"), labels.get("mdstack.lab.run")) != (lab["owner"], lab["run"]):
                raise RuntimeError("%s no longer carries run %s's labels; nothing removed" % (rid, lab["run"]))
        self.docker("rm", "-f", "-v", host["container"])
        self.docker("network", "rm", host["network"])
        lab["networks"].remove(host["network"])
        args = argparse.Namespace(manifest=self.path, n3=False, stage=self.stage, tag=lab["tag"],
                                  source_sha=lab["source_sha"])
        labels = [x for k, v in (("run", lab["run"]), ("owner", lab["owner"]))
                  for x in ("--label", "mdstack.lab.%s=%s" % (k, v))]
        labd.add_host(args, self.m, self.host, "crew-lab-%s-%s" % (lab["run"], self.host), labels,
                      os.path.join(self.d, "id_ed25519.pub"))
        labd.write_ssh(self.m, os.path.join(self.d, "id_ed25519"))


class Seen:
    def __init__(self):
        self.failures, self.obs, self.events = [], {}, []

    def event(self, control, phase):
        self.events.append(labe.event(control, phase))

    def check(self, ok, failure):
        if not ok:
            self.failures.append(failure)
        return ok


def run_line(lines, host, head):
    """The job id from `runner:<host>/<job> head=<head>`, or None."""
    m = next((re.fullmatch(r"runner:%s/(\S+) head=%s" % (re.escape(host), head), x) for x in lines
              if x.startswith("runner:")), None)
    return m and m.group(1)


def exits(lines):
    return [int(x.rsplit(" ", 1)[1]) for x in lines if re.fullmatch(r"(check-repo|tests) exit \d+", x)]


def injected(lab, s, name, inject, lift, during=None):
    """Apply an injection, prove it breaks the SSH path, run `during`, lift it and prove the path answers again."""
    s.event(name, "inject")
    inject()
    try:
        reply = lab.call("version")
        s.obs[name + "_version"] = reply
        s.check(reply["result"] == "unreachable", "%s did not break the SSH path: %s" % (name, reply))
        out = during() if during else None
    finally:
        lift()
        s.event(name, "lift")
    for _ in range(30):
        if lab.up():
            break
        time.sleep(1)
    else:
        s.check(False, "the SSH path stayed down after %s was lifted" % name)
    return out


def exact_head(lab, s):
    head = lab.commit()
    out = s.obs["client"] = lab.client(head)
    job = run_line(out, lab.host, head)
    s.check(job and exits(out) == [0, 0] and out[-1] == "exit 0", "the remote run at head did not pass")
    stored = Path(lab.m["roots"]["state_dir"], lab.project, "runner", str(job), "result.json")
    done = json.loads(stored.read_text()) if stored.exists() else {}
    s.check(done.get("head") == head and done.get("host") == lab.host, "no stored result at head for job %s" % job)
    tails = s.obs["host_check_repo"] = (done.get("commands") or [{}])[0].get("tail", "").splitlines()
    s.check(tails == ["check-repo ok on linux", "env: clean"], "the host job did not run clean on linux")
    s.obs["local"] = lab.local()
    s.check(s.obs["local"] == exits(out), "local exits %s differ from remote %s" % (s.obs["local"], exits(out)))


def red(lab, s):
    head = lab.commit(red=True)
    out = s.obs["client"] = lab.client(head)
    s.check(run_line(out, lab.host, head) and exits(out) == [0, 1] and out[-1] == "exit 1"
            and not any("ran locally" in x for x in out), "a red remote test was not a red remote run")
    s.obs["local"] = lab.local()
    s.check(s.obs["local"] == [0, 1], "the same commands locally were not red: %s" % s.obs["local"])


def idempotent(lab, s):
    head = lab.git("rev-parse", "HEAD")
    job = lambda rid: lab.call("job", request_id=rid, project=lab.project, job_id="lab-dup", head=head,
                               commands=SPEC[:1])
    first, again, other = job("rid-1"), job("rid-1"), job("rid-2")
    s.obs.update(first=first, again=again, other=other)
    s.check(first.get("status") == "running" and again == first, "a repeated request id did not return its first reply")
    s.check(other.get("retried") is True and other.get("head") == head, "a new request id started a second job")


def stale(lab, s):
    head = lab.git("rev-parse", "HEAD")
    out = s.obs["client"] = lab.client(lab.git("rev-parse", "HEAD~1"))
    s.check(out[-1] == "exit 2" and any("the checkout is at %s" % head in x for x in out),
            "a stale head was not refused")
    unseeded = lab.git("commit-tree", "-p", head, "-m", "unseeded", head + "^{tree}")
    reply = s.obs["unseeded"] = lab.call("job", project=lab.project, job_id="lab-unseeded", head=unseeded,
                                         commands=SPEC[:1])
    s.check(reply == dict(result="refused", reason="head not in the host mirror"), "an unseeded head was not refused")


def mid_job(lab, s, name, inject, lift):
    """A slow job at a new head, `inject` once it runs, wait for the client's local fallback, then `lift`."""
    head, before = lab.commit(sleep=20), lab.jobs()
    client, pids = lab.client(head, wait=False), lab.pids()
    job = s.obs["job"] = lab.started(before)
    out = injected(lab, s, name, inject, lift, lambda: client.communicate()[0].splitlines() + [
        "exit %d" % client.returncode])
    s.obs["client"] = out
    s.check(job and "runner: %s unreachable; ran locally" % lab.host in out and exits(out) == [0, 0],
            "the client did not fall back locally while %s held" % name)
    return job, pids


def disconnect(lab, s):
    net = lab.m["lab"]["hosts"][lab.host]["network"]
    state = lambda: lab.docker("inspect", "--format", "{{.State.Status}} {{.State.Pid}}", lab.cid())
    before = state()
    job, pids = mid_job(lab, s, "disconnect", lambda: lab.docker("network", "disconnect", net, lab.cid()),
                        lambda: lab.docker("network", "connect", "--alias", lab.host, net, lab.cid()))
    s.obs["state"], s.obs["pids"] = [before, state()], [pids, lab.pids()]
    s.check(s.obs["state"][0] == s.obs["state"][1] and pids == s.obs["pids"][1], "the container or runner restarted")
    done = s.obs["result"] = lab.result(job)
    s.check([c["exit"] for c in done.get("commands", [])] == [0, 0], "the job's result was not pulled after reconnect")
    s.check(job and [j[:7] for j in lab.jobs()].count(job[:7]) == 1, "the client started a second job at the head")


def pause(lab, s):
    job, _ = mid_job(lab, s, "pause", lambda: lab.docker("pause", lab.cid()), lambda: lab.docker("unpause", lab.cid()))
    done = s.obs["result"] = lab.result(job)
    s.check([c["exit"] for c in done.get("commands", [])] == [0, 0], "the paused job did not finish after unpause")


def runner(lab, s):
    """Once the runner is up, kill it alone: SSH still answers; then a new runner must beat and report up."""
    for _ in range(120):
        if lab.call("version").get("runner") == "up":
            break
        time.sleep(1)
    else:
        return s.check(False, "the runner was never up before the kill")
    before = lab.pids()
    s.event("runner", "inject")
    lab.docker("exec", lab.cid(), "kill", str(before["runner"]))
    outage = s.obs["runner_version"] = lab.call("version")
    s.check(outage.get("result") == "ok" and lab.pids()["sshd"] == before["sshd"],
            "SSH did not answer while only the runner was down: %s" % outage)
    health = s.obs["health"] = []
    for _ in range(120):
        after, beat = lab.pids(), lab.beat()
        health.append(lab.call("version").get("runner"))
        if after["runner"] not in (None, before["runner"]) and beat.get("pid") == after["runner"] \
                and health[-1] == "up":
            break
        time.sleep(1)
    s.event("runner", "restarted")
    s.obs["pids"], s.obs["beat"] = [before, after], beat
    s.check(after["runner"] not in (None, before["runner"]) and after["sshd"] == before["sshd"],
            "the runner was not restarted alone")
    s.check(beat.get("pid") == after["runner"] and health[-1:] == ["up"],
            "the restarted runner never reported up: %s" % health[-3:])
    out = s.obs["client"] = lab.client(lab.commit())
    s.check(out[-1] == "exit 0" and not any("ran locally" in x for x in out), "no job passed after the restart")


def recreate(lab, s):
    host = lab.m["lab"]["hosts"][lab.host]
    old = dict(container=host["container"], host_key=host["host_key"], port=host["port"], pids=lab.pids())
    head, before = lab.commit(sleep=20), lab.jobs()
    client = lab.client(head, wait=False)
    job = s.obs["job"] = lab.started(before)
    s.event("recreate", "inject")
    lab.recreate()
    s.event("recreate", "lift")
    out = s.obs["client"] = client.communicate()[0].splitlines() + ["exit %d" % client.returncode]
    host = lab.m["lab"]["hosts"][lab.host]
    s.obs["identity"] = [old, dict(container=host["container"], host_key=host["host_key"], port=host["port"],
                                   pids=lab.pids())]
    s.check(all(old[k] != host[k] for k in ("container", "host_key", "port")), "the container was not recreated")
    s.check(job and any(re.fullmatch(r"runner: %s (unreachable|refused: unknown job); ran locally" % lab.host, x)
                        for x in out) and exits(out) == [0, 0], "the lost job did not fall back locally")
    s.obs["lost"] = lab.call("result", job_id=str(job))
    s.check(s.obs["lost"].get("status") != "done", "the recreated host reported the lost job done")
    out = s.obs["fresh"] = lab.client(lab.commit())
    s.check(out[-1] == "exit 0" and not any("ran locally" in x for x in out), "no fresh job passed after recreate")


def partition(lab, s):
    claim = Path(lab.m["roots"]["state_dir"], lab.project, "claims", "builder-issue1")
    claim.parent.mkdir(parents=True, exist_ok=True)
    claim.write_text("item: issue #1\nhost: %s\nheartbeat: lab\n" % lab.host)
    before, net = hashlib.sha256(claim.read_bytes()).hexdigest(), lab.m["lab"]["hosts"][lab.host]["network"]
    args = argparse.Namespace(project=lab.m["profile"]["path"], org_profile=os.path.join(lab.d, "org-role.toml"))

    def placed():
        values, session, state = lab.mdstack.profile(args)
        return lab.mdstack.placement.place(dict(role="builder", paths=[], order=[["claude-code", "opus"]], host=None,
                                                **{"pass": "build"}), values, lab.mdstack.host_facts(
            args, values, session, state))
    s.obs["placed"] = injected(lab, s, "disconnect", lambda: lab.docker("network", "disconnect", net, lab.cid()),
                               lambda: lab.docker("network", "connect", "--alias", lab.host, net, lab.cid()), placed)
    s.check(s.obs["placed"] == dict(result="queue", reason="%s: unreachable" % lab.host),
            "placement did not queue the role run behind the partition: %s" % s.obs["placed"])
    s.check(hashlib.sha256(claim.read_bytes()).hexdigest() == before, "the claim file changed")


PLANT = """set -e
wt=$HOME/.mdstack/wt/lab-attach; mkdir -p "$wt/.crew/runs/issue-1/build" "$HOME/.mdstack/state/%(project)s/runs"
printf '# Run summary\\n- build ok\\n- tests ok\\n' > "$wt/.crew/runs/issue-1/build/summary.md"
printf '{"window": "ben-1", "primary": "primary", "worktree": "%%s"}' "$wt" > "$HOME/.mdstack/state/%(project)s/runs/ben-1.json"
tmux new-window -d -t crew-host: -n %(project)s/ben-1 "echo lab-attach-pane; exec tail -f /dev/null"
"""


def on_pty(argv, until, keys=b"", timeout=30):
    """Run argv on a fresh 40x120 pty; once `until` shows, type keys then C-b d. (exit code, everything it printed)."""
    primary, secondary = os.openpty()
    fcntl.ioctl(secondary, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    p = subprocess.Popen(argv, stdin=secondary, stdout=secondary, stderr=secondary, start_new_session=True)
    os.close(secondary)
    out, sent, deadline = b"", False, time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if select.select([primary], [], [], 0.5)[0]:
                chunk = os.read(primary, 65536)
                if not chunk:
                    break
                out += chunk
            elif p.poll() is not None:
                break
            if not sent and until in out:
                sent = True
                os.write(primary, keys)
                time.sleep(1)
                os.write(primary, b"\x02d")
        except OSError:  # the client exited and its pty closed (EIO)
            break
    if p.poll() is None:
        p.kill()
    code = p.wait()
    os.close(primary)
    return code, out.decode(errors="replace")


def attach(lab, s):
    for _ in range(120):
        if lab.call("version").get("runner") == "up":
            break
        time.sleep(1)
    else:
        return s.check(False, "the runner was never up")
    lab.docker("exec", "-u", "crew", lab.cid(), "sh", "-c", PLANT % dict(project=lab.project))
    scope = dict(project=lab.project, window="ben-1", primary="primary")
    try:
        cap = s.obs["capture"] = lab.call("capture", **scope)
        s.check(cap.get("result") == "ok" and "lab-attach-pane" in cap.get("text", ""), "capture: %s" % cap)
        logs = s.obs["logs"] = lab.call("logs", lines=2, **scope)
        s.check(logs == dict(result="ok", path="wt/lab-attach/.crew/runs/issue-1/build/summary.md",
                             lines=["- build ok", "- tests ok"]), "logs: %s" % logs)
        client = [sys.executable, "-c", "import importlib.util as u, json, sys; s = u.spec_from_file_location('r', "
                  "sys.argv[1]); m = u.module_from_spec(s); s.loader.exec_module(m); "
                  "sys.exit(m.attach(sys.argv[2], config=sys.argv[3], **json.loads(sys.argv[4])))",
                  lab.remote.__file__, lab.host, lab.conf, json.dumps(dict(scope, root=ROOT))]
        code, out = on_pty(client, b"lab-attach-pane", keys=b"lab-typed-keys")
        s.obs["attach"] = dict(exit=code, tail=out[-400:])
        s.check(code == 0 and "lab-attach-pane" in out, "the pty attach did not show the pane and detach cleanly")
        after = s.obs["capture_after"] = lab.call("capture", **scope).get("text", "")
        s.check("lab-attach-pane" in after and "lab-typed-keys" not in after, "a read-only attach reached the pane")
        r = subprocess.run(client, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        s.obs["no_tty"] = dict(exit=r.returncode, stdout=r.stdout.strip())
        s.check(r.returncode == 1 and '"attach needs a TTY"' in r.stdout, "attach without a TTY was not refused")
        payload = lab.remote.base64.urlsafe_b64encode(json.dumps(dict(
            verb="version", version=lab.remote.version())).encode()).decode()
        argv = lab.remote.ssh_argv(lab.host, lab.conf)
        argv = ["-tt" if a == "-T" else a for a in argv[:-1]] + ["crew-host " + payload]
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        s.obs["tty_version"] = dict(exit=r.returncode, stdout=r.stdout.strip())
        s.check(r.returncode == 1 and '"only attach takes a TTY"' in r.stdout, "a verb other than attach took a TTY")
    finally:
        s.obs["kill"] = lab.call("kill", refs=["refs/heads/lab"], discard=True, **scope)


SCENARIOS = dict((f.__name__.replace("_", "-"), f) for f in (
    exact_head, red, idempotent, stale, disconnect, pause, runner, recreate, partition, attach))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest")
    ap.add_argument("--stage", required=True)
    ap.add_argument("--host", default="lab-a")
    ap.add_argument("--only", action="append", choices=sorted(SCENARIOS))
    a = ap.parse_args(argv)
    lab = Lab(a.manifest, a.stage, a.host)
    try:
        problems = lab.refusals()
        if not problems:
            lab.prepare()
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        problems = ["prepare: %s" % e]
    if problems:
        print("\n".join("refused: " + p for p in problems))
        return 2
    report, timeline, started = {}, [], labe.now()
    for name, scenario in SCENARIOS.items():
        if a.only and name not in a.only:
            continue
        s, start = Seen(), time.monotonic()
        timeline.append(dict(t=labe.now(), scenario=name, event=name, phase="start"))
        try:
            scenario(lab, s)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, SystemExit, subprocess.CalledProcessError) as e:
            s.failures.append("%s: %s" % (type(e).__name__, e))
        report[name] = dict(passed=not s.failures, failures=s.failures, seconds=round(time.monotonic() - start),
                            **s.obs)
        timeline += [dict(e, scenario=name) for e in s.events]
        timeline.append(dict(t=labe.now(), scenario=name, event=name, phase="pass" if not s.failures else "fail"))
        print("%s %s (%ds)%s" % ("PASS" if not s.failures else "FAIL", name, report[name]["seconds"],
                                 "".join("\n  " + f for f in s.failures)), flush=True)
    labd.save(a.manifest, lab.m)
    Path(lab.d, "scenarios.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print("evidence: " + labe.write(lab.d, labe.record(lab.m, a.host, lab.client_sha, started, timeline, report,
                                                       list(SCENARIOS))))
    return 0 if all(r["passed"] for r in report.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
