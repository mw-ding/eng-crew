#!/usr/bin/env python3
"""Away-mode permission auto-approve for crew role sessions (docs/permit.md, #646).

Usage:
  crew-permit.py hook --trust FILE              (Claude Code PermissionRequest hook; JSON on stdin)
  crew-permit.py check --trust FILE --project CREW_TOML [--cwd DIR] (--command TEXT | --tool NAME --path P)
  crew-permit.py log --trust FILE --project CREW_TOML [--entry ID]
  crew-permit.py install --project CREW_TOML [--org-profile FILE] [--trust-dir DIR] [--settings FILE]

The checker is an allowlist: a command is approved only when every part matches one rule
family (read, crew, write, tracker, assign, setup); anything else, including substitution,
eval, unknown variables and unparseable text, means ask. The hook approves only for a tagged
crew session (CREW_ROLE, CREW_PROJECT) while the project's away record is open and unexpired,
after sending an FYI; otherwise it prints nothing and the normal prompt stays. The trust file
and this hook's installed copy live outside every crew root. `check` is the checker alone and
does not read the away record: exit 0 approves, 1 asks. `install` is a human step: it refuses
inside a crew session or without a terminal and confirms before writing. Standard library only.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

ROLES = ("coordinator", "builder", "reviewer", "synthesizer")
CREW_VERBS = ("acked", "attach", "content", "dequeue", "drain", "guard", "handoff", "land-lock", "lead",
              "logs", "notify", "ownership", "poll", "restart", "reviewer-pool", "route", "schedule",
              "send", "spawn", "status", "train", "watch")
TRACKER_VERBS = ("issue comment", "issue create", "issue edit", "issue close", "issue reopen",
                 "pr comment", "pr create", "pr edit", "pr ready", "pr review")
UPSTREAM_VERBS = ("issue comment", "issue create")
READ = {"basename", "cat", "comm", "cut", "date", "diff", "dirname", "du", "echo", "egrep", "fgrep", "file",
        "grep", "head", "id", "jq", "ls", "nl", "printf", "pwd", "realpath", "stat", "tail", "test", "tr",
        "tree", "true", "uname", "uniq", "wc", "which", "whoami", "["}
GIT_READ = {"blame", "cat-file", "describe", "diff", "for-each-ref", "grep", "log", "ls-files", "ls-tree",
            "merge-base", "name-rev", "rev-list", "rev-parse", "shortlog", "show", "status"}
GIT_LOCAL = {"add", "checkout", "commit", "fetch", "merge", "mv", "pull", "restore", "rm", "switch"}
GH_READ = {("pr", "list"), ("pr", "view"), ("pr", "diff"), ("pr", "checks"), ("pr", "status"), ("issue", "list"),
           ("issue", "view"), ("issue", "status"), ("run", "list"), ("run", "view"), ("release", "list"),
           ("release", "view"), ("label", "list"), ("repo", "view")}
PROTECTED = {".git", ".claude", ".codex", ".mcp.json", ".envrc"}
CREDENTIAL = re.compile(r"\.ssh|\.aws|\.gnupg|\.netrc|\.pgpass|\.kube|\.docker|\.config/gh|Keychains|id_rsa|id_ed25519")
SED = re.compile(r"((\d+|\$)(,(\d+|\$))?|/[^/\n]*/(,/[^/\n]*/)?)p|\d+q")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ASSIGN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.S)
GLOB = set("*?[{")
VISIBLE = re.compile(r"CREW_\w+|HOME|USER|TMPDIR")
SHELL_VARS = re.compile(r"(GIT_|GH_|LD_|DYLD_|PYTHON)\w*|PATH|IFS|ENV|BASH_ENV|CDPATH|HOME|SHELL|PS4")


class Ask(Exception):
    pass


class Command:
    def __init__(self):
        self.words, self.globbed, self.redirects = [], set(), []


def commands(text, env):
    """Yield each simple command; raise Ask on anything a real shell would expand or run indirectly.

    Expansion reads env when the command is reached, so earlier assignments count at their effective value."""
    i, n = 0, len(text)
    cmd, word, quoted, glob, redirect = Command(), None, False, False, None

    def end_word():
        nonlocal word, quoted, glob, redirect
        if word is None:
            return
        if redirect:
            cmd.redirects.append((redirect, word, glob))
            redirect = None
        elif not cmd.words and not quoted and word in ("{", "}"):
            raise Ask("subshell or group")
        else:
            if glob:
                cmd.globbed.add(len(cmd.words))
            cmd.words.append(word)
        word, quoted, glob = None, False, False

    def expand(j, in_quotes):
        nonlocal word, glob
        if j + 1 < n and text[j + 1] == "{":
            close = text.find("}", j + 2)
            name, after = text[j + 2:close] if close > 0 else "", close + 1
        else:
            m = NAME.match(text, j + 1)
            name, after = (m.group(), m.end()) if m else ("", j + 1)
        if not NAME.fullmatch(name) or name not in env:
            raise Ask("unknown variable or substitution")
        value = env[name]
        if not in_quotes and (re.search(r"\s", value) or GLOB & set(value)):
            raise Ask("unquoted expansion splits or globs")
        word = (word or "") + value
        return after

    while i < n:
        c = text[i]
        if c in " \t":
            end_word()
            i += 1
        elif c in "\n;":
            end_word()
            if redirect:
                raise Ask("redirect without target")
            yield cmd
            cmd = Command()
            i += 1
        elif c in "&|":
            end_word()
            two = text[i:i + 2]
            if two in ("&&", "||"):
                i += 2
            elif c == "|" and two != "|&":
                i += 1
            elif two == "&>":
                redirect, i = ">", i + 2
                continue
            else:
                raise Ask("background or pipe-all")
            if redirect:
                raise Ask("redirect without target")
            yield cmd
            cmd = Command()
        elif c in "<>":
            if word is not None and word.isdigit() and not quoted:
                word = None  # fd number
            end_word()
            op = text[i:i + 2]
            if op in ("<<", "<(", ">(", "<>", ">|"):
                raise Ask("here-doc, process substitution or clobber")
            if op == ">>":
                i += 2
            else:
                i += 1
            if c == ">" and text[i:i + 1] == "&":
                m = re.match(r"&(\d+|-)", text[i:])
                if not m:
                    raise Ask("redirect")
                i += m.end()
                continue
            redirect = op if op == ">>" else c
        elif c == "'":
            close = text.find("'", i + 1)
            if close < 0:
                raise Ask("unterminated quote")
            word, quoted = (word or "") + text[i + 1:close], True
            i = close + 1
        elif c == '"':
            word, quoted, i = (word or ""), True, i + 1
            while True:
                if i >= n:
                    raise Ask("unterminated quote")
                d = text[i]
                if d == '"':
                    i += 1
                    break
                if d == "`":
                    raise Ask("command substitution")
                if d == "$":
                    i = expand(i, True)
                elif d == "\\" and i + 1 < n and text[i + 1] in '"$`\\\n':
                    word += text[i + 1] if text[i + 1] != "\n" else ""
                    i += 2
                else:
                    word += d
                    i += 1
        elif c == "\\":
            if i + 1 < n and text[i + 1] == "\n":
                i += 2
                continue
            if i + 1 >= n:
                raise Ask("trailing escape")
            word = (word or "") + text[i + 1]
            i += 2
        elif c == "$":
            i = expand(i, False)
        elif c == "`":
            raise Ask("command substitution")
        elif c == "#" and word is None:
            close = text.find("\n", i)
            i = n if close < 0 else close
        elif c in "()":
            raise Ask("subshell or group")
        else:
            if c == "~" and word is None and text[i + 1:i + 2] in ("", "/", " ", "\n", ";"):
                word, i = env.get("HOME", "~"), i + 1
                continue
            if c in GLOB:
                glob = True
            word = (word or "") + c
            i += 1
    end_word()
    if redirect:
        raise Ask("redirect without target")
    yield cmd


def realpath(path, cwd):
    return os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))


def under(path, root):
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


class Checker:
    def __init__(self, conf, project, trust_path):
        self.conf, self.project, self.trust = conf, os.path.realpath(project), os.path.realpath(trust_path)
        self.roots = [os.path.realpath(r) for r in conf.get("roots", []) if r]
        self.repo = conf.get("repo", "")

    def writable(self, path, cwd, recursive=False):
        target = realpath(path, cwd)
        if target == "/dev/null" and not recursive:
            return
        root = next((r for r in self.roots if under(target, r)), None)
        if root is None or under(target, os.path.dirname(self.trust)):
            raise Ask("write outside crew roots: " + target)
        if PROTECTED & set(Path(target).relative_to(root).parts) or (
                recursive and any(under(r, target) for r in self.roots)):
            raise Ask("protected write target: " + target)

    def check(self, text, cwd, env):
        """Return the rule families that approve every part of text; raise Ask otherwise."""
        if text.strip() in [s.strip() for s in self.conf.get("setup", []) if s.strip()]:
            return ["setup"]
        if CREDENTIAL.search(text) or self.trust in text:
            raise Ask("credential or trust path")
        self.inherited = set(env)
        env = {k: v for k, v in env.items() if VISIBLE.fullmatch(k)}
        env["PWD"], rules = cwd, []
        for cmd in commands(text, env):
            if not cmd.words:
                if cmd.redirects:
                    raise Ask("bare redirect")
                continue
            rule = self.command(cmd, cwd, env)
            if cmd.redirects:
                for op, target, globbed in cmd.redirects:
                    if op == "<":
                        continue
                    if globbed:
                        raise Ask("glob write target")
                    self.writable(target, cwd)
                if rule == "read":
                    rule = "write"
            if rule == "cd":
                cwd = realpath(cmd.words[1] if len(cmd.words) > 1 else env.get("HOME", cwd), cwd)
                rule = "read"
            rules.append(rule)
        if not rules:
            raise Ask("empty command")
        return sorted(set(rules))

    def command(self, cmd, cwd, env):
        words = cmd.words
        if words[0] == "export":
            words = words[1:]
        if not words:
            raise Ask("bare export")
        assigns = [ASSIGN.fullmatch(w) for w in words]
        if all(a and i not in cmd.globbed for i, a in enumerate(assigns)):
            for a in assigns:
                if a[1] in self.inherited or SHELL_VARS.fullmatch(a[1]):
                    raise Ask("assignment changes the environment: " + a[1])
                env[a[1]] = a[2]
            return "assign"
        if assigns[0]:
            raise Ask("command with environment prefix")
        name = words[0]
        if name == "cd" and len(words) <= 2:
            return "cd"
        if name in READ:
            return "read"
        if name == "sort" and not any(w.startswith(("-o", "--output")) for w in words):
            return "read"
        if name == "find" and not set(words) & {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint",
                                                "-fprint0", "-fprintf", "-fls"}:
            return "read"
        if name == "rg" and not any(w.startswith("--pre") for w in words):
            return "read"
        if name == "sed":
            return self.sed(words)
        if name == "git":
            return self.git(words, cwd)
        if name == "gh":
            return self.gh(words)
        if name in ("mkdir", "touch", "cp", "mv", "rm", "tee"):
            return self.write(cmd, cwd)
        crew = self.conf.get("crew", "")
        argv = words[1:] if name in ("python3", "python") else words
        if crew and argv and realpath(argv[0], cwd) == os.path.realpath(crew):
            return self.crew(argv, cwd)
        raise Ask("not on the allowlist: " + name)

    def sed(self, words):
        scripts, rest = [], iter(words[1:])
        for w in rest:
            if w == "-e":
                scripts.append(next(rest, ""))
            elif w in ("-n", "-E", "-r"):
                continue
            elif w.startswith("-"):
                raise Ask("sed option " + w)
            elif not scripts:
                scripts.append(w)
        if not scripts or not all(SED.fullmatch(s) for s in scripts):
            raise Ask("sed script")
        return "read"

    def git(self, words, cwd):
        i = 1
        while i < len(words) and words[i].startswith("-"):
            if words[i] == "-C" and i + 1 < len(words):
                cwd = realpath(words[i + 1], cwd)
                i += 2
            elif words[i] == "--no-pager":
                i += 1
            else:
                raise Ask("git global option " + words[i])
        verb, args = (words[i], words[i + 1:]) if i < len(words) else ("", [])
        if any(a.startswith(("--output", "--ext-diff", "--open-files-in-pager", "-O", "--exec")) for a in args):
            raise Ask("git option that writes or runs")
        if verb in GIT_READ or (verb == "branch" and all(a in ("-a", "-r", "-v", "-vv", "--list", "--show-current")
                                                          for a in args)):
            return "read"
        if verb in GIT_LOCAL:
            if any("://" in a or re.match(r"[\w.-]+@", a) for a in args):
                raise Ask("git URL operand")
            self.writable(".", cwd)
            return "write"
        if verb == "push":
            return self.push(args, cwd)
        raise Ask("git " + verb)

    def push(self, args, cwd):
        positional = [a for a in args if not a.startswith("-")]
        flags = [a for a in args if a.startswith("-")]
        if (not set(flags) <= {"-u", "--set-upstream", "-q", "--quiet", "--porcelain"} or len(positional) != 2 or
                positional[0] != "origin" or positional[1].startswith(("+", ":")) or not self.repo):
            raise Ask("push other than a plain push to origin")
        self.writable(".", cwd)
        url = subprocess.run(["git", "-C", cwd, "remote", "get-url", "--push", "origin"],
                             capture_output=True, text=True).stdout.strip()
        if not re.fullmatch(r"(https://github\.com/|git@github\.com:|ssh://git@github\.com/)%s(\.git)?/?" %
                            re.escape(self.repo), url):
            raise Ask("origin is not the project repo")
        return "tracker"

    def gh(self, words):
        repos, positional, flags, i = [], [], [], 1
        while i < len(words):
            w = words[i]
            if w in ("-R", "--repo"):
                repos.append(words[i + 1] if i + 1 < len(words) else "")
                i += 2
                continue
            if w.startswith("--repo="):
                repos.append(w.split("=", 1)[1])
            elif w.startswith("-R") and len(w) > 2:
                repos.append(w[2:])
            elif w.startswith("-"):
                flags.append(w)
            else:
                positional.append(w)
            i += 1
        for w in words:
            for owner_repo in re.findall(r"github\.com[/:]([^/\s]+/[^/\s#?]+)", w):
                if owner_repo.removesuffix(".git") != self.repo:
                    raise Ask("URL names another repo")
        pair = tuple(positional[:2])
        if pair and pair[0] == "api":
            return self.api(words[2:])
        if pair in GH_READ:
            return "read"
        verb = " ".join(pair)
        if len(repos) != 1:
            raise Ask("tracker write needs exactly one -R")
        if repos[0] == self.repo and verb in self.conf.get("tracker_verbs", []):
            if verb == "pr review" and not set(flags) <= {"--comment", "-c", "--body-file", "-F", "--body", "-b"}:
                raise Ask("pr review other than a comment")
            return "tracker"
        upstream = self.conf.get("upstream", "")
        if upstream and repos[0] == upstream and verb in UPSTREAM_VERBS:
            return "tracker"
        raise Ask("gh %s on %s" % (verb, repos[0]))

    def api(self, args):
        rest = iter(args)
        paths = []
        for a in rest:
            if a in ("-X", "--method"):
                if next(rest, "").upper() != "GET":
                    raise Ask("gh api write")
            elif a in ("--jq", "-q"):
                next(rest, None)
            elif a in ("--paginate", "--slurp") or a.startswith("--jq="):
                continue
            elif a.startswith("-"):
                raise Ask("gh api option " + a)
            else:
                paths.append(a)
        if len(paths) != 1 or paths[0].lstrip("/").startswith("graphql"):
            raise Ask("gh api path")
        return "read"

    def write(self, cmd, cwd):
        words = cmd.words
        name, flags, operands = words[0], [], []
        for i, w in enumerate(words[1:], 1):
            if w.startswith("-") and not operands and w != "-":
                flags.append(w)
            elif i in cmd.globbed:
                raise Ask("glob operand")
            else:
                operands.append(w)
        allowed = {"mkdir": {"-p"}, "touch": set(), "cp": {"-r", "-R", "-p", "-f", "-a"}, "mv": {"-f"},
                   "rm": {"-r", "-R", "-f", "-rf", "-fr", "-Rf", "-fR"}, "tee": {"-a"}}[name]
        if not set(flags) <= allowed or not operands:
            raise Ask("%s options or operands" % name)
        recursive = name == "rm" and any("r" in f.lower() for f in flags)
        targets = operands[-1:] if name == "cp" else operands
        for t in targets:
            self.writable(t, cwd, recursive)
        if name == "cp" and os.path.isdir(realpath(operands[-1], cwd)):
            for src in operands[:-1]:
                self.writable(os.path.join(operands[-1], os.path.basename(src.rstrip("/"))), cwd)
        return "write"

    def crew(self, argv, cwd):
        verb = argv[1] if len(argv) > 1 else ""
        projects = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--project"]
        projects += [a.split("=", 1)[1] for a in argv if a.startswith("--project=")]
        if verb not in CREW_VERBS or len(projects) != 1 or realpath(projects[0], cwd) != self.project:
            raise Ask("crew command not bound to this project")
        return "crew"

    def tool(self, name, tool_input, cwd, env):
        if name == "Bash":
            return self.check(tool_input.get("command", ""), cwd, env)
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path") or ""
        if name in ("Write", "Edit", "MultiEdit", "NotebookEdit") and path:
            self.writable(path, cwd)
            return ["write"]
        if name in ("Read", "Glob", "Grep") and not CREDENTIAL.search(path) and self.trust not in path:
            return ["read"]
        raise Ask("tool " + name)


def load_trust(path, project):
    """The project's trust table; raise Ask unless the file is a regular, owner-only, unlinked file."""
    real = os.path.realpath(path)
    if real != os.path.abspath(path):
        raise Ask("trust path has a symlink")
    st = os.stat(real)
    if st.st_uid != os.getuid() or st.st_mode & 0o022:
        raise Ask("trust file is writable by others")
    with open(real, "rb") as f:
        conf = tomllib.load(f).get("projects", {}).get(os.path.realpath(project))
    if not conf:
        raise Ask("project not in trust file")
    for root in [os.path.realpath(r) for r in conf.get("roots", []) if r]:
        if under(real, root) or under(os.path.realpath(__file__), root):
            raise Ask("trust file or hook inside a crew root")
    return conf


def away_record(comments, login):
    """Current open away record; mirrors notify.away_record in crew.d so this file can run on its own."""
    current, seen = None, set()
    for comment in comments:
        body = comment.get("body") or ""
        if comment.get("user", {}).get("login") != login or not re.search(r"^— .+ · .+ · .+$", body, re.M):
            continue
        if comment.get("updated_at") != comment.get("created_at"):
            continue
        for line in re.findall(r"<!-- crew:v1 ([^>]*?) -->", body):
            marker = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if (marker.get("role"), marker.get("pass"), marker.get("round"), marker.get("verdict")) != (
                    "coordinator", "steer", "n/a", "n/a") or not re.fullmatch(r"[0-9a-f]{40}", marker.get("sha", "")):
                continue
            source = marker.get("cmd-id")
            if not source or source in seen:
                continue
            for text in re.findall(r"```json\s*\n(.*?)\n```", body, re.S) + re.findall(r"`(\{[^`\n]+\})`", body):
                record = json.loads(text)
                if marker.get("cmd") == "away" and record.get("state") == "away" and record.get("entry") == source:
                    datetime.datetime.fromisoformat(record["started"])
                    current = record
                    seen.add(source)
                elif marker.get("cmd") == "away-return" and record.get("state") == "returned" and current and record.get("entry") == current["entry"]:
                    current = None
                    seen.add(source)
    return current


def open_away(conf, now):
    """(away record, tracking issue) while a non-quiet away entry is open and before its until; else Ask."""
    control = Path(conf["state_dir"]) / "away-control.json"
    if not control.exists():
        raise Ask("no away record")
    issue = json.loads(control.read_text())["issue"]
    result = subprocess.run(["gh", "api", "--paginate", "--slurp", "repos/%s/issues/%s/comments" % (conf["repo"], issue)],
                            capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise Ask("away record unavailable")
    away = away_record([c for page in json.loads(result.stdout) for c in page], conf["coordinator"])
    if not away or away.get("quiet") or not away.get("until"):
        raise Ask("no open bounded away entry")
    if now >= datetime.datetime.fromisoformat(away["until"]):
        raise Ask("away entry expired")
    return away, issue


def fyi(conf, issue, text):
    argv = conf.get("fyi") or ["gh", "issue", "comment", str(issue), "-R", conf["repo"], "--body-file", "-"]
    if subprocess.run(argv, input=text, capture_output=True, text=True, timeout=20).returncode:
        raise Ask("FYI not delivered")


def hook(args):
    try:
        event = json.load(sys.stdin)
        role, project = os.environ.get("CREW_ROLE"), os.environ.get("CREW_PROJECT")
        if role not in ROLES or not project:
            raise Ask("not a crew role session")
        conf = load_trust(args.trust, project)
        checker = Checker(conf, project, args.trust)
        name, tool_input = event.get("tool_name", ""), event.get("tool_input") or {}
        rules = checker.tool(name, tool_input, event.get("cwd") or os.getcwd(), dict(os.environ))
        now = datetime.datetime.now(datetime.timezone.utc)
        away, issue = open_away(conf, now)
        what = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        who = os.environ.get("CREW_ID", role)
        fyi(conf, issue, "Auto-approved (FYI) for %s (%s), rule %s, %s:\n\n```text\n%s\n```\n" % (
            who, role, "+".join(rules), name, what))
        log = Path(conf["state_dir"]) / "permit" / "approvals.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as f:
            f.write(json.dumps(dict(ts=now.strftime("%Y-%m-%dT%H:%M:%SZ"), entry=away["entry"], id=who, role=role,
                                    tool=name, rules=rules, command=what)) + "\n")
    except (Ask, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired, tomllib.TOMLDecodeError):
        return 0  # The normal prompt stays.
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}))
    return 0


def check(args):
    try:
        conf = load_trust(args.trust, args.project)
        checker = Checker(conf, args.project, args.trust)
        cwd = os.path.realpath(args.cwd or os.getcwd())
        if args.command is not None:
            rules = checker.check(args.command, cwd, dict(os.environ))
        else:
            rules = checker.tool(args.tool, {"file_path": args.path}, cwd, dict(os.environ))
    except Ask as e:
        print("ask: %s" % e)
        return 1
    print("allow: %s" % "+".join(rules))
    return 0


def log(args):
    conf = load_trust(args.trust, args.project)
    path = Path(conf["state_dir"]) / "permit" / "approvals.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    rows = [r for r in rows if args.entry in (None, r["entry"])]
    for r in rows:
        print("- %s %s (%s) %s via %s: `%s`" % (r["ts"], r["id"], r["role"], "+".join(r["rules"]), r["tool"],
                                               r["command"].replace("`", "'").replace("\n", " ")))
    if not rows:
        print("None")
    return 0


def toml_section(project, conf):
    lines = ["", "[projects.%s]" % json.dumps(project)]
    lines += ["%s = %s" % (k, json.dumps(v)) for k, v in conf.items()]
    return "\n".join(lines) + "\n"


def install_plan(values, project, root, trust_dir, settings_path):
    """{path: text} for the trust file, the hook copy and the harness settings; ValueError when unsafe."""
    project = os.path.realpath(project)
    state = os.path.join(values["paths.state_dir"], values["repo.owner"] + "__" + values["repo.name"])
    roots = [os.path.realpath(state), os.path.realpath(values["paths.worktree_root"])]
    trust_dir = os.path.realpath(trust_dir)
    for r in roots + [os.path.dirname(project), os.path.realpath(root)]:
        if under(trust_dir, r):
            raise ValueError("trust dir must be outside every crew root: " + r)
    trust, copy = os.path.join(trust_dir, "trust.toml"), os.path.join(trust_dir, "crew-permit.py")
    text = Path(trust).read_text() if os.path.exists(trust) else "# Owner-installed; crews never edit this file.\n"
    if os.path.realpath(project) in tomllib.loads(text).get("projects", {}):
        raise ValueError("project already in %s; edit it by hand" % trust)
    conf = dict(repo=values["repo.owner"] + "/" + values["repo.name"],
                coordinator=values["identities.coordinator.gh_user"], state_dir=roots[0], roots=roots,
                crew=os.path.join(os.path.realpath(root), "scripts", "crew"), upstream="",
                tracker_verbs=list(TRACKER_VERBS), setup=[], fyi=[])
    settings = json.loads(Path(settings_path).read_text()) if os.path.exists(settings_path) else {}
    command = "python3 %s hook --trust %s" % (copy, trust)
    entries = settings.setdefault("hooks", {}).setdefault("PermissionRequest", [])
    if not any(h.get("command") == command for e in entries for h in e.get("hooks", [])):
        entries.append({"matcher": "*", "hooks": [{"type": "command", "command": command, "timeout": 60}]})
    return {trust: text + toml_section(project, conf), copy: Path(__file__).read_text(),
            settings_path: json.dumps(settings, indent=2) + "\n"}


def install(args):
    if any(os.environ.get(k) for k in ("CREW_ID", "CREW_ROLE", "CREW_PROJECT")):
        print("crew-permit: refusing inside a crew session; the owner installs this hook", file=sys.stderr)
        return 1
    if not sys.stdin.isatty():
        print("crew-permit: install needs a terminal and a person to confirm", file=sys.stderr)
        return 1
    import importlib.util
    spec = importlib.util.spec_from_file_location("crew_render", Path(__file__).with_name("crew-render.py"))
    crew_render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(crew_render)
    values, problems = crew_render.resolve(args.project, args.org_profile)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    try:
        plan = install_plan(values, args.project, Path(__file__).resolve().parent.parent,
                            os.path.expanduser(args.trust_dir), os.path.expanduser(args.settings))
    except ValueError as e:
        print("crew-permit: %s" % e, file=sys.stderr)
        return 1
    for path, text in plan.items():
        print("== %s\n%s" % (path, text if not path.endswith(".py") else "(copy of %s)\n" % __file__))
    if input("Install the away permission hook? [y/N] ").strip().lower() != "y":
        print("crew-permit: not installed")
        return 1
    for path, text in plan.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        os.chmod(path, 0o600 if path.endswith(".toml") else 0o644)
    print("crew-permit: installed; review %s and restart role sessions" % next(iter(plan)))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hook")
    h.add_argument("--trust", required=True)
    c = sub.add_parser("check")
    c.add_argument("--trust", required=True)
    c.add_argument("--project", required=True)
    c.add_argument("--cwd")
    c.add_argument("--command")
    c.add_argument("--tool")
    c.add_argument("--path")
    lg = sub.add_parser("log")
    lg.add_argument("--trust", required=True)
    lg.add_argument("--project", required=True)
    lg.add_argument("--entry")
    i = sub.add_parser("install")
    i.add_argument("--project", required=True)
    i.add_argument("--org-profile")
    i.add_argument("--trust-dir", default="~/.config/eng-crew/permit")
    i.add_argument("--settings", default="~/.claude/settings.json")
    args = p.parse_args(argv)
    if args.cmd == "check" and (args.command is None) == (args.tool is None):
        p.error("check needs exactly one of --command or --tool")
    try:
        return {"hook": hook, "check": check, "log": log, "install": install}[args.cmd](args)
    except Ask as e:
        print("crew-permit: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
