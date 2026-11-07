#!/usr/bin/env python3
"""Hardened remote call: host entrypoint, runner and primary-side client (docs/runtimes/multi-device.md#remote-call-and-runner).

Usage: crew-remote.py --root DIR                                  (forced command: JSON request on stdin, reply on stdout)
       crew-remote.py --root DIR runner [--once] [--interval SECS]  (the host's user-level runner service)

Install on a host: the crew key's authorized_keys line is
`command="python3 <bundle>/scripts/crew-remote.py --root <root>",restrict <key>`. The client (`call`) runs
`ssh <host> crew-host` with batch mode, strict host keys, no forwarding and bounded dead-peer timeouts. It takes only
the host's auth and host-key settings from the SSH config (`ssh -G`) and then runs with `-F none`, so no SendEnv,
SetEnv, forwarding or proxy from any config reaches the call; the entrypoint reads no environment but SSH_ORIGINAL_COMMAND.
A request is one JSON object {verb, version, request_id?, ...}, never a shell string, never evaluated. Every reply
is {"result": "ok", ...}, {"result": "refused", "reason"} or {"result": "failed", "error"}, exit 0; only the client
yields {"result": "unreachable"}, on a transport failure. Refused: a verb outside the closed set or not built yet, a
different eng-crew version, an SSH command other than crew-host, a `root` or path outside root, and a mutating verb
without a request id. Built verbs: `version`; `check` (host readiness rows tools, project mirror, logins, runner and
capacity, with projects and load, the reply crew host check reads); `prepare` (create or fetch
mirrors/<owner>__<repo>.git with the host's gh login) and `seed` (a forge-less host: fetch the primary's base64
one-ref git bundle into the mirror as refs/crew/heads/<sha>, and refs/heads/<branch> when given); both then make wt/
and state/<owner>__<repo>/, and a failed reply names its `step`. With a `toolkit` pin (tag, bundle_sha256,
transport) both also install that release into toolkit/eng-crew-<v>/ with the shared verifier (docs/bootstrap.md Host toolkit, #945): staged under
toolkit/.staging-*, its record toolkit/eng-crew-<v>.json (pin, bundle digest, SHA-256 of every file) written last,
then state/<owner>__<repo>/toolkit.json names the version; a verified existing version is reused, any other is
moved aside only after the replacement verifies, so a refused one leaves the previous install in place. The
entrypoint writes no bytecode, so running it from the toolkit keeps every file hash. `prune` (with prepare or seed) then removes the toolkit versions and staging
leftovers that no state/*/toolkit.json names and lists them. `version` with a `toolkit` pin and `project` also
reports whether that project's pinned toolkit, its record and every file hash match the pin (host check row 2); `job` (refused unless `head` is a commit in the project mirror: a detached worktree
jobs/<job_id>/wt/ at head runs the closed command set in the background with a scrubbed env and writes
jobs/<job_id>/result.json; a retried job_id returns the first job; jobs past JOB_RETENTION are removed) and `result`
(`running`, or the result with capped log tails). A retried request id returns its first reply. The runner keeps the host's crew tmux session
alive, so runs outlive the SSH session, and writes runner.json under root as its heartbeat.
"""
import argparse
import base64
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import uuid

sys.dont_write_bytecode = True  # loading crew-install.py must not add a .pyc to the hash-verified toolkit it runs from
HERE = os.path.dirname(os.path.abspath(__file__))
VERBS = {"version", "check", "prepare", "spawn", "probe", "pull", "send", "kill", "logs", "capture", "attach",
         "seed", "job", "result"}
MUTATING = {"prepare", "spawn", "send", "kill", "seed", "job"}
REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
PROJECT = re.compile(r"[A-Za-z0-9-]+__[A-Za-z0-9._-]+")  # owner__repo; a GitHub owner has no underscore
SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
TAG = re.compile(r"v\d+\.\d+\.\d+(-rc\.\d+)?")
TEST_NAME = re.compile(r"test-[A-Za-z0-9._-]+\.py")  # scripts/test-*.py, a basename only
COMMANDS = {"check-repo", "tests", "evidence"}
JOB_ENV = {"PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "USER", "LOGNAME"}  # no token, agent or profile
JOB_RETENTION, TAIL = 7 * 86400, 4000
PREPARE_TIMEOUT = 600
DISK_FLOOR = 1 << 30  # free bytes under root below which the capacity row fails
LOGGED_IN = r"Logged in to \S+ (account|as) %s(\s|$)"  # a `gh auth status` line, as crew doctor reads it
SESSION, INTERVAL = "crew-host", 30
SSH = ["ssh", "-F", "none", "-T", "-a", "-x", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
       "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=5",
       "-o", "ServerAliveCountMax=2"]
KEEP = {"hostname", "user", "port", "identityfile", "identitiesonly", "certificatefile", "identityagent",
        "userknownhostsfile", "globalknownhostsfile", "hostkeyalias"}  # auth and host keys; never env, forwards, proxies


def version():
    path = os.path.join(os.path.dirname(HERE), "VERSION")  # the release bundle's tag; a checkout is "dev"
    if not os.path.exists(path):
        return "dev"
    with open(path) as f:
        return f.read().strip()


def tmux():
    spec = importlib.util.spec_from_file_location("crew_tmux", os.path.join(HERE, "session.d", "tmux.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_harnesses():
    spec = importlib.util.spec_from_file_location("crew_harness", os.path.join(HERE, "crew-harness.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runner_state(root):
    try:
        with open(os.path.join(root, "runner.json")) as f:
            beat = json.load(f)
        fresh = time.time() - beat["beat"] <= 3 * beat["interval"]
    except (OSError, ValueError, KeyError, TypeError):
        return "down"
    return "up" if fresh and tmux().has_session(SESSION) else "down"


def sh(step, *argv):
    r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=PREPARE_TIMEOUT)
    if r.returncode:
        raise Failed(step, r.stderr.strip()[-200:] or "exit %d" % r.returncode)
    return r.stdout


class Failed(Exception):
    def __init__(self, step, error):
        super().__init__(error)
        self.reply = dict(result="failed", step=step, error=error)


def project_step(handler):
    """Shared by prepare and seed: an owner__repo check, a failure that names its step, then the run directories."""
    def run(request, root):
        project = request.get("project")
        if not isinstance(project, str) or not PROJECT.fullmatch(project):
            return dict(result="refused", reason="project must be owner__repo")
        mirror = os.path.join(root, "mirrors", project + ".git")
        try:
            reply = handler(request, root, project, mirror)
        except Failed as e:
            return e.reply
        for path in ("wt", *(os.path.join("state", project, d) for d in ("status", "inbox", "verdicts"))):
            os.makedirs(os.path.join(root, path), exist_ok=True)
        if "toolkit" in request:
            try:
                reply["toolkit"] = install_toolkit(root, project, request["toolkit"], request["request_id"])
            except Failed as e:
                return e.reply
        if request.get("prune"):
            reply["pruned"] = prune_toolkit(root)
        return dict(reply, result="ok", mirror=os.path.relpath(mirror, root))
    return run


def crew_install():
    spec = importlib.util.spec_from_file_location("crew_install", os.path.join(HERE, "crew-install.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pin_install(pin):
    """The checked toolkit pin's [install] table: the primary's transport, with its SHA256SUMS digest or commit as
    the pin. Raises ValueError for a malformed pin."""
    transport = pin.get("transport") if isinstance(pin, dict) else None
    if not isinstance(pin, dict) or not isinstance(pin.get("tag"), str) or not TAG.fullmatch(pin["tag"]) or \
            not isinstance(pin.get("bundle_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", pin["bundle_sha256"]):
        raise ValueError("toolkit pin needs a release tag and bundle_sha256")
    if transport is None:
        return {}
    kind = transport.get("kind") if isinstance(transport, dict) else None
    if kind not in ("url", "mirror", "git") or not isinstance(transport.get("location"), str):
        raise ValueError("toolkit pin transport needs kind url, mirror or git and a location")
    if kind == "git":
        if not isinstance(transport.get("commit"), str) or not SHA.fullmatch(transport["commit"]):
            raise ValueError("toolkit pin transport git needs a full commit")
        return {"source": kind, "location": transport["location"], "git_commit": transport["commit"]}
    if not isinstance(transport.get("sha256sums_sha256"), str) or \
            not re.fullmatch(r"[0-9a-f]{64}", transport["sha256sums_sha256"]):
        raise ValueError("toolkit pin transport needs sha256sums_sha256")
    return {"source": kind, "location": transport["location"], "sha256sums_digest": transport["sha256sums_sha256"]}


def file_hashes(bundle):
    """{relative path: sha256} for every entry under bundle; a symlink or special file hashes as its type."""
    hashes = {}
    for folder, dirs, files in os.walk(bundle):
        for name in files + [d for d in dirs if os.path.islink(os.path.join(folder, d))]:
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, bundle)
            hashes[rel] = crew_install().digest(path) if os.path.isfile(path) and not os.path.islink(path) \
                else "not a regular file"
    return hashes


def toolkit_verified(root, pin):
    """None when toolkit/eng-crew-<v> and its record match the pin and every file hash, else why not."""
    name = "eng-crew-" + pin["tag"][1:]
    bundle, record_path = os.path.join(root, "toolkit", name), os.path.join(root, "toolkit", name + ".json")
    try:
        record = load(record_path)
    except (OSError, ValueError):
        return "%s has no record" % name
    want = dict(tag=pin["tag"], transport=pin.get("transport"))
    if (pin.get("transport") or {}).get("kind") != "git":
        want["bundle_sha256"] = pin["bundle_sha256"]
    if any(record.get(k) != v for k, v in want.items()):
        return "%s record differs from the primary's pin" % name
    if os.path.islink(bundle) or not os.path.isdir(bundle) or file_hashes(bundle) != record.get("files"):
        return "%s files differ from its record" % name
    return None


def toolkit_status(request, root):
    """Host check row 2: the project's toolkit.json names the pin's tag, and that version matches the pin."""
    pin, project = request["toolkit"], request.get("project")
    try:
        pin_install(pin)
    except ValueError as e:
        return dict(status="fail", detail=str(e))
    if not isinstance(project, str) or not PROJECT.fullmatch(project):
        return dict(status="fail", detail="project must be owner__repo")
    try:
        tag = load(os.path.join(root, "state", project, "toolkit.json"))["tag"]
    except (OSError, ValueError, KeyError, TypeError):
        return dict(status="fail", detail="%s pins no toolkit on this host; run crew host prepare" % project)
    if tag != pin["tag"]:
        return dict(status="fail", detail="%s pins %s on this host, the primary %s" % (project, tag, pin["tag"]))
    why = toolkit_verified(root, pin)
    return dict(status="fail", detail=why) if why else dict(status="ok", detail="eng-crew %s verified" % tag)


def prune_toolkit(root):
    """Remove toolkit versions and staging leftovers that no project's toolkit.json names; return their names."""
    toolkit, state = os.path.join(root, "toolkit"), os.path.join(root, "state")
    pinned = set()
    for project in os.listdir(state) if os.path.isdir(state) else []:
        try:
            pinned.add("eng-crew-" + load(os.path.join(state, project, "toolkit.json"))["tag"][1:])
        except (OSError, ValueError, KeyError, TypeError):
            pass
    removed = []
    for name in sorted(os.listdir(toolkit)) if os.path.isdir(toolkit) else []:
        if not (name.startswith(".staging-") or name.startswith("eng-crew-")) or name.removesuffix(".json") in pinned:
            continue
        path = os.path.join(toolkit, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        removed.append(name)
    return removed


def install_toolkit(root, project, pin, request_id):
    """Install the pinned release into toolkit/ (reuse a verified one), then point the project at it."""
    try:
        install = pin_install(pin)
    except ValueError as e:
        raise Failed("toolkit", str(e))
    toolkit, name = os.path.join(root, "toolkit"), "eng-crew-" + pin["tag"][1:]
    bundle, record_path = os.path.join(toolkit, name), os.path.join(toolkit, name + ".json")
    state = "reused"
    if toolkit_verified(root, pin):
        state = "installed"
        staging = os.path.join(toolkit, ".staging-" + request_id)
        os.makedirs(staging, exist_ok=True)
        try:
            try:
                sha, _, _ = crew_install().fetch(install, pin["tag"], os.path.join(staging, name))
            except (OSError, ValueError, tarfile.TarError) as e:
                raise Failed("toolkit", str(e)[-200:])
            if install.get("source") != "git" and sha != pin["bundle_sha256"]:
                raise Failed("toolkit", "bundle sha256 %s differs from the primary's pin %s" % (sha, pin["bundle_sha256"]))
            record = dict(tag=pin["tag"], transport=pin.get("transport"), bundle_sha256=sha,
                          files=file_hashes(os.path.join(staging, name)))
            save(os.path.join(staging, name + ".json"), record)
            if os.path.lexists(record_path):
                os.replace(record_path, os.path.join(staging, "old.json"))
            if os.path.lexists(bundle):
                os.replace(bundle, os.path.join(staging, "old"))
            os.replace(os.path.join(staging, name), bundle)
            os.replace(os.path.join(staging, name + ".json"), record_path)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(os.path.join(root, "state", project), exist_ok=True)
    save(os.path.join(root, "state", project, "toolkit.json"), dict(tag=pin["tag"]))
    return dict(tag=pin["tag"], state=state)


@project_step
def prepare(request, root, project, mirror):
    """Create the project mirror with the host's own gh login, or fetch it."""
    if os.path.isdir(mirror):
        sh("fetch", "git", "-C", mirror, "fetch", "--quiet", "--prune", "origin")
        return dict(step="fetch")
    sh("clone", "gh", "repo", "clone", project.replace("__", "/", 1), mirror, "--", "--mirror", "--quiet")
    return dict(step="clone")


@project_step
def seed(request, root, project, mirror):
    """Forge-less host: fetch the primary's one-ref bundle into the mirror as refs/crew/heads/<sha> (and `branch`)."""
    data = base64.b64decode(request.get("bundle", ""), validate=True)
    bundle = os.path.join(root, "requests", request["request_id"] + ".bundle")
    os.makedirs(os.path.dirname(bundle), exist_ok=True)
    with open(bundle, "wb") as f:
        f.write(data)
    try:
        if not os.path.isdir(mirror):
            sh("init", "git", "init", "--quiet", "--bare", mirror)
        heads = sh("verify", "git", "-C", mirror, "bundle", "list-heads", bundle).split()
        if len(heads) != 2:
            raise Failed("verify", "bundle must carry exactly one ref")
        sh("fetch", "git", "-C", mirror, "fetch", "--quiet", bundle, heads[1])
        sh("fetch", "git", "-C", mirror, "update-ref", "refs/crew/heads/" + heads[0], heads[0])
        if request.get("branch"):
            sh("branch", "git", "-C", mirror, "update-ref", "refs/heads/" + str(request["branch"]), heads[0])
    finally:
        os.remove(bundle)
    return dict(step="seed", tip=heads[0])


def load(path):
    with open(path) as f:
        return json.load(f)


def save(path, data):
    with open(path + ".tmp", "w") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)


def job_refusal(commands, tests):
    """Why the command list falls outside the closed set, or None; `tests` is the head's scripts/ file names."""
    if not isinstance(commands, list) or not commands:
        return "commands must be a non-empty list"
    for c in commands:
        kind = c.get("command") if isinstance(c, dict) else None
        if kind not in COMMANDS:
            return "command %r not in the closed set" % (kind,)
        files = c.get("files")
        if kind == "tests" and not (isinstance(files, list) and files and all(
                isinstance(f, str) and TEST_NAME.fullmatch(f) and f in tests for f in files)):
            return "tests must name scripts/test-*.py files at head"
        argv, extra = c.get("argv"), [c.get("setup"), c.get("label")]
        if kind == "evidence" and not (isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv)
                                       and all(x is None or isinstance(x, str) for x in extra)):
            return "evidence needs an argv list and optional setup and label strings"
    if sum(c["command"] == "evidence" for c in commands) > 1:
        return "one evidence capture per job"
    return None


def job_argv(c, job_dir):
    if c["command"] == "check-repo":
        return [sys.executable, "scripts/check-repo.py"]
    if c["command"] == "tests":
        return [sys.executable, "scripts/run-tests.py", *("scripts/" + f for f in c["files"])]
    return [sys.executable, "scripts/evidence-cli.py", *(["--label", c["label"]] if c.get("label") else []),
            *(["--setup", os.path.join(job_dir, "setup.sh")] if c.get("setup") else []), "--", *c["argv"]]


def sweep(root):
    jobs = os.path.join(root, "jobs")
    for name in os.listdir(jobs) if os.path.isdir(jobs) else []:
        path = os.path.join(jobs, name)
        if time.time() - os.path.getmtime(path) > JOB_RETENTION:
            shutil.rmtree(path)
    for mirror in [os.path.join(root, "mirrors", m) for m in os.listdir(os.path.join(root, "mirrors"))] \
            if os.path.isdir(os.path.join(root, "mirrors")) else []:
        subprocess.run(["git", "-C", mirror, "worktree", "prune"], stdin=subprocess.DEVNULL, capture_output=True)


def job(request, root):
    """Start the closed command set at `head` in jobs/<job_id>/wt/, detached; a retried job_id returns the first."""
    job_id = request.get("job_id")
    if not isinstance(job_id, str) or not REQUEST_ID.fullmatch(job_id):
        return dict(result="refused", reason="job_id must match %s" % REQUEST_ID.pattern)
    sweep(root)
    job_dir = os.path.join(root, "jobs", job_id)
    if os.path.exists(os.path.join(job_dir, "job.json")):
        first = load(os.path.join(job_dir, "job.json"))
        done = os.path.exists(os.path.join(job_dir, "result.json"))
        return dict(result="ok", job_id=job_id, head=first["head"], status="done" if done else "running", retried=True)
    project, head = request.get("project"), request.get("head")
    mirror = os.path.join(root, "mirrors", "%s.git" % project)
    if not isinstance(project, str) or not PROJECT.fullmatch(project) or not os.path.isdir(mirror):
        return dict(result="refused", reason="project mirror not prepared")
    if not (isinstance(head, str) and SHA.fullmatch(head) and subprocess.run(
            ["git", "-C", mirror, "cat-file", "-e", head + "^{commit}"], capture_output=True).returncode == 0):
        return dict(result="refused", reason="head not in the host mirror")
    tests = sh("tree", "git", "-C", mirror, "ls-tree", "--name-only", head, "scripts/").split()
    reason = job_refusal(request.get("commands"), {os.path.basename(t) for t in tests})
    if reason:
        return dict(result="refused", reason=reason)
    os.makedirs(job_dir, exist_ok=True)
    try:
        sh("worktree", "git", "-C", mirror, "worktree", "add", "--quiet", "--detach", os.path.join(job_dir, "wt"), head)
    except Failed as e:
        return e.reply
    setup = next((c["setup"] for c in request["commands"] if c.get("setup")), None)
    if setup:
        with open(os.path.join(job_dir, "setup.sh"), "w") as f:
            f.write(setup)
    save(os.path.join(job_dir, "job.json"), dict(project=project, head=head, commands=request["commands"]))
    env = {k: v for k, v in os.environ.items() if k in JOB_ENV}
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "--root", root, "job", job_id], env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return dict(result="ok", job_id=job_id, head=head, status="running")


def run_job(root, job_id):
    """The detached job runner: each command in turn, its output in a log on the host, then result.json."""
    job_dir = os.path.join(root, "jobs", job_id)
    spec, results = load(os.path.join(job_dir, "job.json")), []
    for i, c in enumerate(spec["commands"]):
        log, start = os.path.join("jobs", job_id, "%d-%s.log" % (i, c["command"])), time.monotonic()
        with open(os.path.join(root, log), "w") as f:
            code = subprocess.run(job_argv(c, job_dir), cwd=os.path.join(job_dir, "wt"), stdin=subprocess.DEVNULL,
                                  stdout=f, stderr=subprocess.STDOUT).returncode
        results.append(dict(command=c["command"], exit=code, duration=round(time.monotonic() - start, 1), log=log))
    save(os.path.join(job_dir, "result.json"), dict(job_id=job_id, head=spec["head"], commands=results))
    return 0


def result(request, root):
    job_id = request.get("job_id")
    job_dir = os.path.join(root, "jobs", str(job_id))
    if not isinstance(job_id, str) or not REQUEST_ID.fullmatch(job_id) or not os.path.isdir(job_dir):
        return dict(result="refused", reason="unknown job")
    if not os.path.exists(os.path.join(job_dir, "result.json")):
        return dict(result="ok", job_id=job_id, status="running")
    done = load(os.path.join(job_dir, "result.json"))
    for c in done["commands"]:
        with open(os.path.join(root, c["log"]), errors="replace") as f:
            c["tail"] = f.read()[-TAIL:]
    return dict(done, result="ok", status="done")


def version_verb(request, root):
    reply = dict(result="ok", version=version(), runner=runner_state(root))
    if "toolkit" in request:
        reply["toolkit"] = toolkit_status(request, root)
    return reply


def probe(*argv):
    """(exit code, stdout and stderr) of a read-only command; 127 when it is missing or hangs."""
    try:
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return r.returncode, r.stdout + r.stderr


def row(status, check, detail, hint=None):
    return dict(status=status, check=check, detail=detail, **({"hint": hint} if hint else {}))


def check_verb(request, root):
    """Host readiness for one project, read-only: rows tools, project mirror, logins, runner and capacity, the
    prepared projects (mirrors/) and the load (jobs still running). `fix` repairs nothing yet; hints name the step."""
    project, branch = request.get("project"), request.get("default_branch")
    if not isinstance(project, str) or not PROJECT.fullmatch(project) or not isinstance(branch, str):
        return dict(result="refused", reason="check needs project=owner__repo and default_branch")
    forge = request.get("forge", True) is not False
    engines = (request.get("capabilities") or {}).get("engines") or []
    harnesses = load_harnesses()  # engine name -> CLI and login check, from the harness adapters
    tools = ["git", "tmux"] + (["gh"] if forge else []) + [harnesses.CLI.get(e, e) for e in engines]
    missing = [t for t in tools if not shutil.which(t)]
    checks = [row("fail", "tools", "missing " + ", ".join(missing), "install them on the host") if missing
              else row("ok", "tools", ", ".join(tools))]
    mirror, bin_dir = os.path.join(root, "mirrors", project + ".git"), request.get("toolchain_bin")
    if probe("git", "-C", mirror, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch)[0]:
        checks.append(row("fail", "project mirror", "%s has no %s" % (project, branch), "run crew host prepare"))
    elif bin_dir and not os.path.isdir(os.path.expanduser(str(bin_dir))):
        checks.append(row("fail", "project mirror", "toolchain_bin %s missing" % bin_dir, "fix toolchain_bin"))
    else:
        checks.append(row("ok", "project mirror", "%s has %s" % (project, branch)))
    code, out = probe("gh", "auth", "status")
    if not forge:
        checks.append(row("fail", "logins", "gh logged in") if code == 0 else row("ok", "logins", "no forge login"))
    else:
        users = sorted(set((request.get("identities") or {}).values()))
        absent = [u for u in users if not re.search(LOGGED_IN % re.escape(str(u)), out)]
        absent += [e for e in engines if probe(*harnesses.login_status(e))[0]]
        checks.append(row("human", "logins", "not logged in: " + ", ".join(absent), "log in on the host") if absent
                      else row("ok", "logins", "logged in: " + ", ".join(users + list(engines))))
    checks.append(row("ok", "runner", "up") if runner_state(root) == "up" else
                  row("fail", "runner", "down", "start crew-remote.py --root <root> runner as a user service"))
    jobs = os.path.join(root, "jobs")
    load = sum(not os.path.exists(os.path.join(jobs, j, "result.json")) for j in
               (os.listdir(jobs) if os.path.isdir(jobs) else []))
    free = shutil.disk_usage(root).free
    checks.append(row("ok" if free >= DISK_FLOOR else "fail", "capacity", "%.1f GiB free, %d running" % (
        free / (1 << 30), load), None if free >= DISK_FLOOR else "free disk under root"))
    mirrors = os.path.join(root, "mirrors")
    projects = sorted(m[:-4] for m in (os.listdir(mirrors) if os.path.isdir(mirrors) else []) if m.endswith(".git"))
    return dict(result="ok", checks=checks, projects=projects, load=load)


HANDLERS = {"version": version_verb, "check": check_verb,
            "prepare": prepare, "seed": seed, "job": job, "result": result}


def confined(root, path):
    real = os.path.realpath(os.path.join(root, path))
    return real == os.path.realpath(root) or real.startswith(os.path.realpath(root) + os.sep)


def handle(request, root, command=None):
    if command not in (None, "", "crew-host"):
        return dict(result="refused", reason="SSH command must be crew-host")
    if not isinstance(request, dict) or request.get("verb") not in VERBS:
        return dict(result="refused", reason="unknown verb")
    verb = request["verb"]
    if verb != "version" and request.get("version") != version():
        return dict(result="refused", reason="version skew: host %s, call %s" % (version(), request.get("version")))
    if "root" in request and os.path.realpath(os.path.expanduser(str(request["root"]))) != os.path.realpath(root):
        return dict(result="refused", reason="root differs from the host's root")
    paths = [v for k, v in request.items() if k == "path" or k.endswith("_path")]
    if any(not isinstance(p, str) or not confined(root, p) for p in paths):
        return dict(result="refused", reason="path outside root")
    rid = request.get("request_id")
    if verb in MUTATING and not (isinstance(rid, str) and REQUEST_ID.fullmatch(rid)):
        return dict(result="refused", reason="mutating verb needs a request id")
    if verb not in HANDLERS:
        return dict(result="refused", reason="verb %s not built on this host" % verb)
    done = os.path.join(root, "requests", "%s.json" % rid) if verb in MUTATING else None
    if done and os.path.exists(done):
        with open(done) as f:
            return json.load(f)
    try:
        reply = HANDLERS[verb](request, root)
    except Exception as e:  # noqa: BLE001 - the caller gets a structured failure, never a traceback
        reply = dict(result="failed", error="%s: %s" % (type(e).__name__, e))
    if done:
        os.makedirs(os.path.dirname(done), exist_ok=True)
        with open(done + ".tmp", "w") as f:
            json.dump(reply, f)
        os.replace(done + ".tmp", done)
    return reply


def runner(root, once=False, interval=INTERVAL):
    adapter = tmux()
    while True:
        if not adapter.has_session(SESSION):
            adapter.new_session(SESSION, "runner", root, {}, "tail -f /dev/null")
        with open(os.path.join(root, "runner.json.tmp"), "w") as f:
            json.dump(dict(pid=os.getpid(), beat=time.time(), interval=interval, session=SESSION), f)
        os.replace(os.path.join(root, "runner.json.tmp"), os.path.join(root, "runner.json"))
        if once:
            return 0
        time.sleep(interval)


def ssh_argv(host, config=None):
    """The hardened argv, or None if the SSH config does not resolve. The config only supplies KEEP settings."""
    r = subprocess.run(["ssh", "-G", *(["-F", config] if config else []), host], capture_output=True, text=True,
                       timeout=10)
    settings = [line.split(" ", 1) for line in r.stdout.splitlines() if line.split(" ", 1)[0] in KEEP]
    return None if r.returncode else [*SSH, *[x for k, v in settings for x in ("-o", k + "=" + v)], host, "crew-host"]


def call(host, verb, request_id=None, timeout=45, config=None, **fields):
    """One hardened SSH call; a mutating verb gets a request id, reused on retry so the host acts once."""
    request = dict(fields, verb=verb, version=version())
    if verb in MUTATING:
        request["request_id"] = request_id or uuid.uuid4().hex
    try:
        argv = ssh_argv(host, config)
        if argv is None:
            return dict(result="failed", error="ssh -G: SSH config does not resolve " + host)
        r = subprocess.run(argv, input=json.dumps(request), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return dict(result="unreachable", error="%s: %s" % (type(e).__name__, e), request_id=request.get("request_id"))
    if r.returncode == 255:
        return dict(result="unreachable", error=r.stderr.strip()[-200:], request_id=request.get("request_id"))
    try:
        reply = json.loads(r.stdout)
        if r.returncode == 0 and reply.get("result") in ("ok", "refused", "failed"):
            return reply
    except (ValueError, AttributeError):
        pass
    return dict(result="failed", error="entrypoint exit %d: no structured reply" % r.returncode)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", required=True)
    p.add_argument("mode", nargs="?", choices=["runner", "job"])
    p.add_argument("job_id", nargs="?")
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=int, default=INTERVAL)
    args = p.parse_args()
    root = os.path.expanduser(args.root)
    os.makedirs(root, exist_ok=True)
    if args.mode == "runner":
        return runner(root, args.once, args.interval)
    if args.mode == "job":
        return run_job(root, args.job_id)
    try:
        request = json.load(sys.stdin)
    except ValueError:
        request = None
    print(json.dumps(handle(request, root, os.environ.get("SSH_ORIGINAL_COMMAND"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
