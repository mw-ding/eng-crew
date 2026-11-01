"""Shared helpers for the crew commands in this directory (docs/runtimes/tmux.md). Python 3.11+ stdlib only.

scripts/crew is the entry point; it loads this module as `crew_shared`, which the commands import from.
Helpers: profile resolve (refusing a `<placeholder>` in a path key the command uses) and state paths, the harness
launch line and window variables (every window gets `CREW_BIN`, `CREW_PROJECT` and the pack's `CREW_SANDBOX_ENV`
variable), run removal with the unlanded-work check, the pane stop (SIGTERM then SIGKILL the process group),
liveness probe and dialog check, queue lock and the command loader."""
import argparse
import contextlib
import fcntl
import glob
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # scripts/


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


crew_render, tmux = load("crew_render", "crew-render.py"), load("crew_tmux", "crew-tmux.py")


ownership_module = load("crew_ownership", "crew.d/_ownership.py")
ownership, require_ownership = ownership_module.ownership, ownership_module.require_ownership


POINTER = "Read your brief at $CREW_BRIEF and follow it."
# The token is derived inside the window's shell: never in argv, -e or a file (tmux.md Q5).
LAUNCH = 'export GH_TOKEN="$(gh auth token --user "$CREW_IDENTITY")"; exec %s "%s"'
ENGINE_CMD = {"claude-code": "claude", "codex": "codex"}
CREW_BIN = os.path.join(HERE, "crew")  # this checkout's CLI, for briefs to call as $CREW_BIN (#139 F1)
# Role windows (tmux.md Layout and naming): index band, passes (first is the default), default name.
BANDS = {"builder": (10, 19), "reviewer": (20, 29), "synthesizer": (1, 1)}
PASSES = {"builder": ["build", "fix"], "reviewer": ["review", "validate"], "synthesizer": ["land"]}
NAMES = {"builder": "ben", "reviewer": "vera", "synthesizer": "sam"}


def brief_src(state, role):
    """Rendered role brief: briefs/<role>.md from core/, else the runtime binding's runtime/<role>.md (#137)."""
    core = os.path.join(state, "render", "briefs", role + ".md")
    return core if os.path.exists(core) else os.path.join(state, "render", "runtime", role + ".md")


def placeholder_paths(args, values, keys):
    """Path keys this command uses whose resolved value still holds a <placeholder>, whichever layer set it (#265):
    an omitted key falls back to the shipped default. A key the command does not use is not checked."""
    return ["%s:paths.%s: still the placeholder %s; set it in the project or org profile, or use the project file "
            "given to crew up ($CREW_PROJECT)" % (args.project, k, values.get("paths." + k)) for k in keys
            if re.search(r"<[^<>]+>", str(values.get("paths." + k, "")))]


def profile(args, *keys):
    """Resolved profile, session name and state dir; exit 1 on a resolve problem, a non-tmux runtime, or a placeholder
    in paths.state_dir or another path key the command uses (keys)."""
    values, problems = crew_render.resolve(args.project, args.org_profile)
    if values and values["runtime.name"] != "tmux":
        problems = ["%s:runtime.name: runtime.name is %s, not tmux" % (args.project, values["runtime.name"])]
    elif values:  # an unrendered copy (a worktree's crew.toml) would put locks and state in the wrong place (#139 F5)
        problems = placeholder_paths(args, values, ("state_dir",) + keys)
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    owner, repo = values["repo.owner"], values["repo.name"]
    session = values.get("runtime.options.session") or "crew-%s-%s" % (owner, repo)
    return values, session, os.path.join(os.path.abspath(values["paths.state_dir"]), "%s__%s" % (owner, repo))


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("crew: git %s failed: %s" % (args[0], r.stderr.strip()))
    return r.stdout.strip()


def fetch(repo, ref):
    """Fresh base: always the just-fetched remote ref, never a possibly stale local one."""
    git(repo, "fetch", "-q", "origin", ref)
    return git(repo, "rev-parse", "FETCH_HEAD")


# runtime.options.permission_mode (tmux.md crew spawn): bypass runs any command in the worktree without asking (#293).
PERMISSION = {
    "claude-code": {"bypass": ["--permission-mode", "bypassPermissions",  # no warning screen, set per process only
                               "--settings", '{"skipDangerousModePermissionPrompt":true}'],
                    "auto": ["--permission-mode", "auto"], "safe": ["--permission-mode", "acceptEdits"]},
    "codex": {"bypass": ["--dangerously-bypass-approvals-and-sandbox"],
              "auto": ["-s", "workspace-write", "-a", "on-request", "-c", "sandbox_workspace_write.network_access=true"],
              "safe": ["-s", "workspace-write", "-c", "sandbox_workspace_write.network_access=true"]}}


def codex_trust(path):
    """Codex `-c` pre-trust for path and, in a git repo, its repo root: a whole projects table for this process, since
    the projects."<dir>".trust_level key form did not stop the trust dialog (#262); a linked worktree's trust is its
    repo root's (#288)."""
    dirs = [os.path.realpath(path)]
    with contextlib.suppress(RuntimeError):  # a crew up project dir need not be a git repo
        dirs.append(os.path.dirname(git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")))
    return "projects={%s}" % ",".join('"%s"={trust_level="trusted"}' % d for d in dict.fromkeys(dirs))


def codex_hooks():
    """Check stored trust for host hooks.json and inline config.toml hooks without hashing or writing config.
    Edited hooks with stale hashes, plugin hooks and project hooks remain the live dialog check's responsibility."""
    def read(path, reader):
        try:
            with open(path, "rb") as f:
                return reader(f)
        except FileNotFoundError:
            return {}

    home = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    path = os.path.join(home, "hooks.json")
    config_path = os.path.join(home, "config.toml")
    inline = read(config_path, tomllib.load).get("hooks", {})
    trusted = inline.get("state", {})
    sources = [(path, read(path, json.load).get("hooks", {})), (config_path, inline)]
    keys = ["%s:%s:%d:%d" % (path, re.sub(r"(?<!^)(?=[A-Z])", "_", event).lower(), i, j)
            for path, hooks in sources for event, groups in hooks.items() if event != "state"
            for i, group in enumerate(groups) for j, _ in enumerate(group.get("hooks", []))]
    bad = [k for k in keys if not trusted.get(k, {}).get("trusted_hash")]
    if bad:
        paths = ", ".join(dict.fromkeys(k.rsplit(":", 3)[0] for k in bad))
        return [("human", "codex hooks", "%d untrusted in %s" % (len(bad), paths), "before crew up, run codex once on "
                 "the host and trust every hook under Review hooks (answering a crew window does not persist)")]
    return [("ok", "codex hooks", "%d trusted" % len(keys), "")]


def harness(engine, model, effort, wt, state, mode):
    """Role window argv; --add-dir state: every pass reads its brief and writes $CREW_STATUS, verdicts/ (#234 F15)."""
    if engine == "claude-code":  # Claude's --add-dir takes several values, so a flag must end it before the prompt
        return ["claude", "--model", model, "--effort", effort, "--add-dir", state, *PERMISSION[engine][mode]]
    add_dirs = [state]
    with contextlib.suppress(RuntimeError):  # a linked worktree's refs and objects live in the common dir (#384)
        add_dirs.append(os.path.realpath(git(wt, "rev-parse", "--path-format=absolute", "--git-common-dir")))
    return ["codex", "-m", model, "-c", "model_reasoning_effort=" + effort,
            "-c", codex_trust(wt), *PERMISSION[engine][mode], *[a for d in add_dirs for a in ("--add-dir", d)]]


def unlanded(values, rec, wt):
    """Uncommitted or untracked paths, and commits not on the fetched default branch, run branch or PR head."""
    items = ["uncommitted: " + line for line in git(wt, "status", "--porcelain", "--untracked-files=all").split("\n")
             if line]
    landed = [fetch(wt, values["repo.default_branch"])]
    branch = subprocess.run(["git", "-C", wt, "symbolic-ref", "-q", "--short", "HEAD"], capture_output=True, text=True)
    refs = [branch.stdout.strip()] if branch.returncode == 0 else []
    refs += ["pull/%s/head" % n for n in re.findall(r"PR #(\d+)", rec.get("item", ""))]
    for ref in refs:
        try:
            landed.append(fetch(wt, ref))
        except RuntimeError:  # not on the remote: its commits count as unlanded
            pass
    log = git(wt, "log", "--format=%H %s", "HEAD", "--not", *landed)
    return items + ["commit: " + line for line in log.split("\n") if line]


def record_discard(values, rec, name, reason, items):
    """Post the owner's discard reason on the run's PR (narrative post) or issue; False if it was not posted."""
    pr, issue = re.search(r"PR #(\d+)", rec.get("item", "")), re.search(r"issue #(\d+)", rec.get("item", ""))
    body = "[%s/kill] discarded unlanded work in %s\n\nReason: %s\n\n%s" % (
        values.get("identities.coordinator.name", "Ash"), name, reason, "\n".join("- `%s`" % i for i in items))
    repo = "%s/%s" % (values["repo.owner"], values["repo.name"])
    cmd = (["gh", "pr", "review", pr.group(1), "--comment", "-R", repo] if pr else
           ["gh", "issue", "comment", issue.group(1), "-R", repo] if issue else None)
    return cmd is not None and subprocess.run(cmd + ["--body", body], capture_output=True).returncode == 0


def stop_pane(session, index, grace=2.0):
    """SIGTERM the pane's process group, SIGKILL what is left after grace seconds; return the pgid if it survives.

    kill-window alone sends SIGHUP, which Codex ignores (#139 F2). The caller's own group (crew down run from
    window 0) is left to kill-session."""
    try:
        pgid = os.getpgid(int((tmux.pane(session, index) or {})["pid"]))
    except (KeyError, ValueError, ProcessLookupError):
        return None
    if pgid <= 1 or pgid == os.getpgrp():
        return None
    for sig in (signal.SIGTERM, signal.SIGKILL):
        with contextlib.suppress(ProcessLookupError, PermissionError):  # EPERM: a group still exiting (macOS)
            os.killpg(pgid, sig)
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                return None
            except PermissionError:
                pass
            time.sleep(0.05)
    return pgid


def kill_run(values, session, state, name, reason=None):
    """Stop the window, then remove only this run's worktree (build output inside it) and state files.

    Removal needs the window's processes gone and the work landed, or a discard reason recorded on the item;
    otherwise keep the worktree and state files and return the blocking items."""
    for index, n in tmux.list_windows(session):
        if n == name:
            pgid = stop_pane(session, index)
            if pgid:
                print("crew: refusing to remove %s: process group %d survived SIGKILL" % (name, pgid))
                return ["alive: process group %d" % pgid]
            tmux.kill_window(session, index)
    path = os.path.join(state, "runs", name + ".json")
    rec = {}
    if os.path.exists(path):
        with open(path) as f:
            rec = json.load(f)
    wt = rec.get("worktree")
    if wt and os.path.dirname(os.path.realpath(wt)) == os.path.realpath(values["paths.worktree_root"]):
        try:
            items = unlanded(values, rec, wt) if os.path.isdir(wt) else []
        except RuntimeError as e:
            items = ["unchecked: %s" % e]
        if items and (reason is None or not record_discard(values, rec, name, reason, items)):
            print("crew: refusing to remove %s: unlanded work in %s%s:\n  %s" % (
                wt, name, "" if reason is None else " (discard reason not recorded on the item)", "\n  ".join(items)))
            return items
        subprocess.run(["git", "-C", rec["repo"], "worktree", "remove", "--force", wt], capture_output=True)
        shutil.rmtree(wt, ignore_errors=True)
        subprocess.run(["git", "-C", rec["repo"], "worktree", "prune"], capture_output=True)
    scratch = [p for p in glob.glob(os.path.join(state, "runs", "**", glob.escape(name) + "[.-]*"), recursive=True)
               if os.path.isfile(p)]  # record, brief, PR body, also under subdirectories (#139 F7, N6)
    for p in scratch + [os.path.join(state, "inbox", name + ".jsonl"),
                        os.path.join(state, "status", name + ".status"), rec.get("claim")] + verdict_files(state, name, rec):
        if p and os.path.exists(p):
            os.remove(p)
    return []


def verdict_files(state, name, rec):
    """A reviewer run's disposable sections; keep the review file until head moves or the PR closes so a
    re-validation can reuse it. The coordinator removes the retained review files on those events."""
    own = rec.get("verdict")
    if not own:
        return []
    keep = rec["pass"] == "review"
    base = own[:-len("validate.md")]  # validate also writes the round's -verdict file (#139 N6)
    return ([] if keep else [own]) + ([base + "verdict.md"] if rec["pass"] == "validate" else [])


def sandbox_env(values):
    """NAME=VALUE from CREW_SANDBOX_ENV or the profile, propagated to every window and future launches."""
    setting = os.environ.get("CREW_SANDBOX_ENV", values.get("runtime.options.sandbox_env", ""))
    key, sep, value = setting.partition("=")
    return {"CREW_SANDBOX_ENV": setting, key: value} if key and sep else {}


def window_env(values, state, role, name, brief, project):
    """The role window's -e variables: names, paths and the login only, never a token (tmux.md Q5)."""
    return {"CREW_ROLE": role, "CREW_ID": name, "CREW_STATE": state, "CREW_BRIEF": brief, "CREW_BIN": CREW_BIN,
            "CREW_PROJECT": os.path.abspath(project),
            "CREW_STATUS": os.path.join(state, "status", name + ".status"),
            "CREW_INBOX": os.path.join(state, "inbox", name + ".jsonl"),
            "CREW_IDENTITY": values["identities.%s.gh_user" % role], **sandbox_env(values)}


def wait_harness(session, index, name, expected, timeout):
    """Verify start: the expected harness must reach the foreground within timeout seconds, on harness_up's evidence:
    the pane command or a foreground process name of the pane's tty. Through a symlinked install the pane command is
    the resolved file's name (`claude` -> `2.1.314`, #286), so that name counts as the pane command too."""
    path = shutil.which(expected)
    names = {expected} | ({os.path.basename(os.path.realpath(path))} if path else set())
    deadline = time.monotonic() + timeout
    while (seen := tmux.pane_command(session, index)) not in names:
        p = None if seen == "dead" else tmux.pane(session, index)
        if p and expected in tmux.foreground(p["tty"]):
            return
        if seen == "dead" or time.monotonic() > deadline:  # a dead pane never starts (#139 F20)
            raise RuntimeError("failed: %s: foreground is %r, not %s, after %ss; cleaned up" % (
                name, seen, expected, timeout))
        time.sleep(0.2)


def acked(state, window, msg_id):
    """Delivery proof: an `ack: <msg-id>` line in the window's status file, nothing else."""
    try:
        with open(os.path.join(state, "status", window + ".status"), encoding="utf-8") as f:
            return any(line.split()[:2] == ["ack:", msg_id] for line in f)
    except FileNotFoundError:
        return False


def wait_ack(state, window, msg_id, secs):
    deadline = time.monotonic() + secs
    while not acked(state, window, msg_id):
        if time.monotonic() >= deadline:
            print("crew: no ack: %s from %s after %ss" % (msg_id, window, secs))
            return 3
        time.sleep(0.2)
    print("crew: acked %s by %s" % (msg_id, window))
    return 0


@contextlib.contextmanager
def queue_lock(state):
    """wake/queue.lock: held around every queue.jsonl append and crew drain's rename, so no append is lost."""
    os.makedirs(os.path.join(state, "wake"), exist_ok=True)
    with open(os.path.join(state, "wake", "queue.lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


CAPS = {"builder": "runtime.options.builders", "reviewer": "runtime.options.reviewers"}


def over_cap(values, role, windows):
    """True when the role's band holds its profile cap of windows, or is full (tmux.md Q6)."""
    used = [i for i in windows.values() if BANDS[role][0] <= i <= BANDS[role][1]]
    return role in CAPS and len(used) >= min(values[CAPS[role]], BANDS[role][1] - BANDS[role][0] + 1)


def identity(session, index):
    """Run identity for the probe: pane handle, pane pid and that process's start time (tmux.md Q7)."""
    p = tmux.pane(session, index) or {}
    return {"pane_id": p.get("id"), "pane_pid": p.get("pid"), "pane_start": tmux.proc_start(p["pid"]) if p else None}


def runs(state):
    d = os.path.join(state, "runs")
    for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if n.endswith(".json"):
            with open(os.path.join(d, n)) as f:
                yield n[:-5], json.load(f)


def heartbeat(state, name):
    """Last status line and the time of the run's last progress (status file, else run record)."""
    status = os.path.join(state, "status", name + ".status")
    if not os.path.exists(status) or not os.path.getsize(status):
        return "", os.path.getmtime(os.path.join(state, "runs", name + ".json"))
    with open(status) as f:
        return f.read().splitlines()[-1], os.path.getmtime(status)


def probe(session, name, rec, windows):
    """C5 liveness from tmux, never from the agent: alive | dead | missing | ambiguous (tmux.md Q7)."""
    if windows.get(name) != rec.get("index"):
        return "missing"
    p = tmux.pane(session, rec["index"])
    if p is None:
        return "ambiguous"
    if (p["id"], p["pid"]) != (rec.get("pane_id"), rec.get("pane_pid")):
        return "missing"  # same name, another run
    if p["dead"] == "1":
        return "dead"
    if tmux.proc_start(p["pid"]) != rec.get("pane_start"):
        return "missing"
    return harness_up(session, rec["index"], p, [rec["harness"]])


# Blocking prompts (#289): the heading on a line of its own and the prompt's footer as the last line on screen, so a
# prompt echo, diff or file quoting the same text, with the composer below it, never counts.
PROMPTS = [(re.compile(head), re.compile(foot)) for head, foot in [
    (r"Would you like to .+\?", r"Press enter to confirm or esc to cancel"),  # Codex approval: command, edits
    (r"Trust this folder\?", r"enter continue · esc "),  # Codex folder trust: 1. Trust and continue
    (r"Do you want to .+\?", r"Esc to cancel"),  # Claude Code permission: proceed, make this edit, create
]]
# A harness's own fatal API error line, after which it idles at its prompt (#289): Codex
# `■ {"type":"error","status":400,...}`, Claude Code `⎿  API Error: 400 {"type":"error",...}`.
FATAL = re.compile(r'■\s(?=.*"type": ?"error")(?=.*"status": ?[45]\d\d\b)'
                   r'|⎿\s+API Error: [45]\d\d\b.*"type": ?"error"')


def dialog(session, index):
    """A blocking prompt or a fatal API error on the pane's screen (#139 F6, F7; #289)."""
    screen = tmux.capture(session, index)
    if "trust" in screen.lower() and "No, exit" in screen or "hooks need review" in screen.lower():
        return True
    lines = [line.strip().lstrip("›❯> ") for line in screen.splitlines() if line.strip()]
    return any(FATAL.match(line) for line in lines) or bool(lines) and any(
        foot.match(lines[-1]) and any(head.match(line) for line in lines) for head, foot in PROMPTS)


def harness_up(session, index, p, harnesses):
    """alive with a harness in the foreground and no dialog on screen, else ambiguous."""
    if dialog(session, index):
        return "ambiguous"
    return "alive" if set(harnesses) & {p["command"], *tmux.foreground(p["tty"])} else "ambiguous"


def finished(rec, last):
    """Terminal: failed: for any run; done: only for reviewer and synthesizer runs, since a builder stays for fixes."""
    return last.startswith("failed:") or last.startswith("done:") and rec["role"] in ("reviewer", "synthesizer")


DESCRIPTION = "tmux crew CLI (docs/runtimes/tmux.md). Python 3.11+ stdlib only."
_COMMANDS = {}


def commands():
    """The crew.d/<cmd>.py modules by command name, loaded once in sorted file order; _-prefixed files are not
    commands. Each module's register(subparsers) adds the subparser named after its file; run(args) runs it."""
    if not _COMMANDS:
        for path in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "[!_]*.py"))):
            name = os.path.basename(path)[:-3]
            spec = importlib.util.spec_from_file_location("crew_cmd_" + name.replace("-", "_"), path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _COMMANDS[name] = mod
    return _COMMANDS


def main(argv=None):
    ap = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, mod in commands().items():
        mod.register(sub)
        # `crew <cmd> --help` prints the command module's docstring, its usage doc (#325)
        sub.choices[name].description = mod.__doc__
        sub.choices[name].formatter_class = argparse.RawDescriptionHelpFormatter
    args = ap.parse_args(argv)
    guarded = args.cmd in ("spawn", "restart", "send", "train") or (
        args.cmd == "land-lock" and args.action == "acquire" or args.cmd == "kill" and args.discard)
    if guarded:
        values, _, _ = profile(args)
        action = "land" if args.cmd in ("train", "land-lock") else "start"
        if not require_ownership(values, action):
            return 1
    return commands()[args.cmd].run(args)
