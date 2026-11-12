"""`mdstack migrate` previews, then applies, moving a stopped crew from one profile's layout to another's (#1178).

Usage: mdstack migrate --project OLD (--to NEW | --rename-to OWNER/NAME) [--org-profile FILE] [--apply]

OLD is the profile the crew runs from today; NEW is the relocated profile the owner wrote (for example
~/.mdstack/config.toml with paths.root). Both must resolve and name the same repo. Either may be a team reference
FILE#<repo> (#1347): the file is the profile that moves and is rewritten, outside any clone, with the repo's declared
checkout as its git repository; only that repo's state and [repos.<repo>] section change, never a sibling repo's. The preview writes nothing and
prints, one per line: each path mapping (`map OLD -> NEW`, most specific first), each operation (`move` of the
project's state directory and the live dir, `copy-move` of each builder run copy under the old worktree root (its own
clone borrowing the checkout's objects, #1252), `worktree-move` of each registered role worktree there, `keep` of each
other directory there, `archive` of the old lead and watcher process identities,
`rewrite FILE (N refs)` of every operational state file and the new profile that cite an old path, `copy` of the
home's .claude/settings.local.json with its paths rewritten), then `owner:` steps it never takes (Claude Code
memory and Codex trust are keyed by absolute path), then `blocked:` lines. Historical evidence (verdicts, trains,
retained, ci, triage, schedule logs) moves with the state directory unchanged.

Blocked, exit 1: the old session or watcher is still live (run `mdstack down --preserve` first), the land lock is held,
the two checkouts are not the same git repository, a destination already exists, or a settings hook other than
the mdstack guard cites an old path whose new path would need shell quoting (edit it by hand). Otherwise exit 0.

--apply runs the same plan, refusing while anything is blocked: it moves the state directory, archives the process
identities and saves each file's original before rewriting it under `<new state>/migration/<stamp>/`, moves each
builder run copy as a directory, then repairs its own linked worktrees (a nested evidence tree) with `git worktree
repair`, and each registered worktree with `git worktree move`, rewrites the operational files (each status file's watcher offset is
recomputed from its rewritten prefix, so nothing replays or is skipped; message ids and ack/done lines are kept) and
copies the settings (the mdstack guard is rewritten per argument and re-quoted; every other hook keeps its shell text
with only the paths replaced). Each completed step goes to that directory's journal.json; on a failure it prints the
completed steps and their shell-quoted rollback commands and exits 1. It ends with map.json (old -> new, rewritten
and kept paths) and the next steps: `mdstack layout --write`, then `mdstack up --coordinator-only` with the new profile.

--rename-to OWNER/NAME plans a repo rename (#1234; docs/runbooks/repo-rename.md) in place of --to: the new profile is
OLD with the repo name changed, so the state directory `<owner>__<name>` moves and nothing else does. The owner stays.
On top of the plan above it prints `name` lines for each name derived from the repo (repo slug, tmux session, each
host's job root), `keep` lines for profile paths that hold the old name by choice, a rewrite of the profile ([repo]
name, quoted slugs, state paths) and of the home's .claude/settings.local.json (the guard's --state) in place, and `owner:` steps: the GitHub rename itself, which must
come first and which the runbook checks, each host's job root and the optional remote URL.
"""
import contextlib
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import time
import tomllib
from crew_shared import checkout, commands, crew_render, profile, tmux

OPERATIONAL = ["runs/*.json", "runs/*.md", "leads/*.md", "leads/*-events/*", "leads/reclaimed-workers/*",
               "inbox/*.jsonl", "status/*.status", "spawn-queue.jsonl", "wake/queue.jsonl", "wake/watch-state.json"]
IDENTITIES = ["leads/builder.json", "leads/reviewer.json", "wake/watcher.pid"]
SETTINGS = os.path.join(".claude", "settings.local.json")
CLAUDE_KEY = re.compile(r"[^A-Za-z0-9]")  # Claude Code's per-project directory name for an absolute cwd


def register(sub):
    p = sub.add_parser("migrate")
    p.add_argument("--project", help="the profile the crew runs from today")
    p.add_argument("--to", help="the relocated profile")
    p.add_argument("--rename-to", metavar="OWNER/NAME", help="plan a repo rename in place of --to (#1234)")
    p.add_argument("--org-profile")
    p.add_argument("--apply", action="store_true", help="run the plan; refused while anything is blocked")


def layout(values, ref, state):
    """The crew's paths; a team reference FILE#<repo> (#1347) splits into the file ("project") and its repo."""
    project, repo = crew_render.crew_config.split_ref(ref)
    home = os.path.dirname(os.path.abspath(project))
    return {"ref": os.path.abspath(ref), "repo": repo, "project": os.path.abspath(project), "home": home,
            "checkout": checkout(values, project), "state": state,
            "worktree_root": os.path.abspath(values["paths.worktree_root"]),
            "live_dir": os.path.abspath(values["paths.live_dir"]) if values.get("paths.live_dir") else None,
            "mdstack": os.path.abspath(values["paths.mdstack"]) if values.get("paths.mdstack") else None}


# Most specific first: a whole-path reference to the old directory is the checkout (a run record's repo) before the
# home, while a path under it is the state, worktree root, live dir or bundle (docs, scripts) before the home.
EXACT = ["project", "state", "worktree_root", "live_dir", "checkout", "home", "mdstack"]
UNDER = ["project", "state", "worktree_root", "live_dir", "mdstack", "home", "checkout"]


def mappings(old, new):
    """{old path: [new path for a whole-path reference, new path for a path under it]}. An unchanged key maps to
    itself, so it keeps its precedence: the old home that is also the unchanged checkout stays a whole-path checkout."""
    maps = {}
    for order, slot in ((EXACT, 0), (UNDER, 1)):
        for key in order:
            if old[key] and new[key]:
                maps.setdefault(old[key], [None, None])
                if maps[old[key]][slot] is None:
                    maps[old[key]][slot] = new[key]
    for path, pair in list(maps.items()):
        pair[0], pair[1] = pair[0] or pair[1], pair[1] or pair[0]
        maps.setdefault(os.path.realpath(path), pair)  # git reports a checkout by its resolved path
    moves = ((p, pair) for p, pair in maps.items() if any(os.path.realpath(v) != os.path.realpath(p) for v in pair))
    return dict(sorted(moves, key=lambda kv: -len(kv[0])))


def pattern(maps):
    return re.compile(r"(?<![\w.~/-])(%s)(?=(/)|[^\w.-]|$)" % "|".join(re.escape(p) for p in maps)) if maps else None


def rewrite(text, maps, rx=None):
    """text with every old path at a path boundary replaced; (new text, count)."""
    rx = rx or pattern(maps)
    if rx is None:
        return text, 0
    count = 0

    def sub(m):
        nonlocal count
        value = maps[m.group(1)][1 if m.group(2) else 0]
        count += value != m.group(1)
        return value
    return rx.sub(sub, text), count


def worktrees(repo):
    r = subprocess.run(["git", "-C", repo, "worktree", "list", "--porcelain"], capture_output=True, text=True)
    return [line[9:] for line in r.stdout.splitlines() if line.startswith("worktree ")] if r.returncode == 0 else []


def run_copy(path, objects):
    """Whether path is a builder run copy (#1252): its own .git borrowing objects (the checkout's object store)."""
    try:
        with open(os.path.join(path, ".git", "objects", "info", "alternates"), encoding="utf-8") as f:
            return objects is not None and os.path.realpath(f.readline().strip()) == objects
    except OSError:
        return False


def nested(copy, old, new):
    """A run copy's existing linked worktrees (a nested evidence tree), each at its path once the copy is at new."""
    root = os.path.realpath(old)
    paths = [os.path.realpath(p) for p in worktrees(copy)[1:]]
    return [new + p[len(root):] if p.startswith(root + os.sep) else p for p in paths if os.path.isdir(p)]


def repair(copy, paths):
    """git worktree repair in copy for paths: both directions of each link, after the copy or its trees moved."""
    if paths:
        r = subprocess.run(["git", "-C", copy, "worktree", "repair", *paths], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("git worktree repair in %s: %s" % (copy, r.stderr.strip()))


def common_dir(repo):
    r = subprocess.run(["git", "-C", repo, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                       capture_output=True, text=True)
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 else None


def files(state, globs):
    return sorted({p for g in globs for p in glob.glob(os.path.join(state, g)) if os.path.isfile(p)})


HEADER = re.compile(r"(?m)^([ \t]*\[[^\]\n]+\][ \t]*(?:#.*)?)$")  # TOML allows an indented header


def rewrite_profile(text, maps, repo, rx=None):
    """rewrite() of a profile, leaving every other repo's [repos.<name>] section of a team file as it is (#1347)."""
    if repo is None:
        return rewrite(text, maps, rx)
    parts, count = HEADER.split(text), 0
    for i in range(0, len(parts), 2):
        header = parts[i - 1].split("#")[0].strip()[1:-1].strip() if i else ""
        section = [key.strip().strip('"\'') for key in header.split(".")]
        if section[0] == "repos" and len(section) > 1 and section[1] != repo:
            continue
        parts[i], n = rewrite(parts[i], maps, rx)
        count += n
    return "".join(parts), count


def plan(old, new, session, maps):
    """(operations, owner steps, blockers); each operation is a tuple naming its kind first."""
    ops, owner, blocked = [], [], []
    if tmux.has_session(session):
        blocked.append("session %s is running; run mdstack down --preserve --project %s" % (session, old["project"]))
    if commands()["watch"].armed(os.path.join(old["state"], "wake", "watcher.pid")):
        blocked.append("the watcher is armed; run mdstack down --preserve --project %s" % old["project"])
    lock = commands()["down"].land_locked(old["state"])
    if lock:
        blocked.append("the land lock %s is held" % lock)
    if common_dir(old["checkout"]) is None or common_dir(old["checkout"]) != common_dir(new["checkout"]):
        blocked.append("checkouts %s and %s are not the same git repository" % (old["checkout"], new["checkout"]))
    if old["state"] != new["state"]:
        ops.append(("move", old["state"], new["state"]))
    for path in files(old["state"], IDENTITIES):
        ops.append(("archive", path))
    registered = {os.path.realpath(p) for p in worktrees(old["checkout"])}
    objects = common_dir(old["checkout"]) and os.path.join(common_dir(old["checkout"]), "objects")
    if os.path.isdir(old["worktree_root"]) and old["worktree_root"] != new["worktree_root"]:
        for name in sorted(os.listdir(old["worktree_root"])):
            path, dest = os.path.join(old["worktree_root"], name), os.path.join(new["worktree_root"], name)
            if not os.path.isdir(path):
                continue
            if os.path.realpath(path) in registered:
                ops.append(("worktree-move", path, dest))
            elif run_copy(path, objects):  # #1252
                ops.append(("copy-move", path, dest))
            else:
                ops.append(("keep", path, "not a registered worktree or run copy of %s" % old["checkout"]))
    if old["live_dir"] and new["live_dir"] and old["live_dir"] != new["live_dir"] and os.path.isdir(old["live_dir"]):
        ops.append(("move", old["live_dir"], new["live_dir"]))
    rx = pattern(maps)
    for path in files(old["state"], OPERATIONAL) + [new["project"]]:
        with open(path, encoding="utf-8", errors="surrogateescape") as f:
            text = f.read()
        count = (rewrite_profile(text, maps, new["repo"], rx) if path == new["project"] else rewrite(text, maps, rx))[1]
        if count:
            ops.append(("rewrite", path, count))
    settings = os.path.join(old["home"], SETTINGS)
    if old["home"] != new["home"] and os.path.isfile(settings):
        ops.append(("copy", settings, os.path.join(new["home"], SETTINGS)))
        hooks = []
        try:
            with open(settings, encoding="utf-8") as f:
                hooks = commands_in(json.load(f))
        except (OSError, ValueError) as e:
            blocked.append("cannot read %s: %s" % (settings, e))
        for command in hooks:
            if unquotable(command, maps, rx):
                blocked.append("hook command in %s cites an old path whose new path needs shell quoting; edit it by "
                               "hand first: %s" % (settings, command))
    for op in ops:
        if op[0] in ("move", "copy-move", "worktree-move", "copy") and os.path.lexists(op[2]):
            blocked.append("destination exists: %s" % op[2])
    for key in ("home", "checkout"):
        if old[key] != new[key]:
            owner.append("Claude Code memory for %s lives under ~/.claude/projects/%s/; carry it to %s/ with the "
                         "owner's go" % (old[key], CLAUDE_KEY.sub("-", old[key]), CLAUDE_KEY.sub("-", new[key])))
    if old["home"] != new["home"]:
        owner.append("trust %s in Claude Code and Codex on first start (crew writes no user-level config)" % new["home"])
    return ops, owner, blocked


def rename_profile(text, values, name):
    """Profile text with its [repo] name and every quoted old slug changed to the new name; (new text, count)."""
    slug, count = "%s/%s" % (values["repo.owner"], values["repo.name"]), 0
    parts = re.split(r"(?m)^(\[[^\]\n]+\][ \t]*(?:#.*)?)$", text)
    for i in range(2, len(parts), 2):
        if parts[i - 1].split("#")[0].strip() == "[repo]":
            parts[i], n = re.subn(r"""(?m)^(\s*name\s*=\s*)(["'])%s\2""" % re.escape(values["repo.name"]),
                                  lambda m: m.group(1) + m.group(2) + name + m.group(2), parts[i])
            count += n
    text, n = re.subn(r"""(["'])%s\1""" % re.escape(slug),
                      lambda m: "%s%s/%s%s" % (m.group(1), values["repo.owner"], name, m.group(1)), "".join(parts))
    return text, count + n


def rename(values, name, old, session, maps):
    """(operations, notes, owner steps, blockers) a repo rename adds to the plan: names derived from the repo slug."""
    ops, notes, owner, blocked = [], [], [], []
    slug, new_slug = "%s/%s" % (values["repo.owner"], values["repo.name"]), "%s/%s" % (values["repo.owner"], name)
    notes.append("name repo %s -> %s" % (slug, new_slug))
    pinned = values.get("runtime.options.session")
    notes.append("keep session %s (runtime.options.session pins it)" % pinned if pinned else
                 "name session %s -> crew-%s-%s (from the next mdstack up)" % (session, values["repo.owner"], name))
    host = commands()["host"]
    for h in host.inventory(values):
        root = host.setting(values, h, "root", "~/.mdstack")
        owner.append("on host %s, move %s/%s__%s to %s/%s__%s before the next mdstack host prepare" % (
            h, root, values["repo.owner"], values["repo.name"], root, values["repo.owner"], name))
    for key in sorted(k for k in values if k.startswith("paths.")):
        path = values[key]
        if isinstance(path, str) and values["repo.name"] in path and not maps.get(os.path.abspath(path)) and \
                not os.path.abspath(path).startswith(old["state"] + os.sep):
            notes.append("keep %s = %s (holds the old name by choice; move it with mdstack migrate --to)" % (key, path))
    with open(old["project"], encoding="utf-8") as f:
        text, count = rewrite(f.read(), maps)
    renamed, n = rename_profile(text, values, name)
    try:
        resolved = tomllib.loads(renamed).get("repo", {}).get("name")
    except tomllib.TOMLDecodeError:
        resolved = None
    if resolved != name:  # the state would move while the profile still derives the old name
        blocked.append("cannot rewrite the repo name in %s (it would read %r); set it by hand" % (old["project"], resolved))
    ops.append(("rewrite", old["project"], count + n))
    for path in files(old["state"], ["install.json"]):  # bootstrap's record of rendered targets under the state
        with open(path, encoding="utf-8") as f:
            count = rewrite(f.read(), maps)[1]
        if count:
            ops.append(("rewrite", path, count))
    settings = os.path.join(old["home"], SETTINGS)
    if os.path.isfile(settings):
        try:
            with open(settings, encoding="utf-8") as f:
                text = f.read()
            hooks = commands_in(json.loads(text))
        except (OSError, ValueError) as e:
            blocked.append("cannot read %s: %s" % (settings, e))
        else:
            rx = pattern(maps)
            if rewrite(text, maps, rx)[1]:
                ops.append(("rewrite", settings, rewrite(text, maps, rx)[1]))
            for command in hooks:
                if unquotable(command, maps, rx):
                    blocked.append("hook command in %s cites an old path whose new path needs shell quoting; edit it "
                                   "by hand first: %s" % (settings, command))
    owner.insert(0, "before --apply, rename %s to %s on GitHub and check that the old URLs redirect "
                    "(docs/runbooks/repo-rename.md steps 3 and 4)" % (slug, new_slug))
    owner.append("optional: git -C %s remote set-url origin https://github.com/%s.git (the old URL redirects)" % (
        old["checkout"], new_slug))
    return ops, notes, owner, blocked


def show(op):
    if op[0] == "rewrite":
        return "rewrite %s (%d refs)" % (op[1], op[2])
    if op[0] == "keep":
        return "keep %s (%s)" % (op[1], op[2])
    return " ".join(op[:2]) + (" -> " + op[2] if len(op) > 2 else "")


def run(args):
    if bool(args.to) == bool(args.rename_to):
        print("crew: migrate needs one of --to or --rename-to")
        return 1
    values, session, state = profile(args, "worktree_root")
    name = None
    if args.rename_to:
        owner_part, _, name = args.rename_to.partition("/")
        if owner_part != values["repo.owner"] or not re.fullmatch(r"[\w.-]+", name) or name == values["repo.name"]:
            print("crew: refusing migrate: --rename-to must keep the owner %s and give a new repo name" % values["repo.owner"])
            return 1
        args.to, new_values = args.project, dict(values, **{"repo.name": name})
    else:
        new_values, problems = crew_render.resolve(args.to, args.org_profile)
        if problems:
            print("\n".join(problems))
            return 1
        if (new_values["repo.owner"], new_values["repo.name"]) != (values["repo.owner"], values["repo.name"]):
            print("crew: refusing migrate: %s and %s name different repos (a rename uses --rename-to)" % (args.project, args.to))
            return 1
    new_state = os.path.join(os.path.abspath(new_values["paths.state_dir"]),
                             "%s__%s" % (new_values["repo.owner"], new_values["repo.name"]))
    old, new = layout(values, args.project, state), layout(new_values, args.to, new_state)
    maps = mappings(old, new)
    ops, owner, blocked = plan(old, new, session, maps)
    notes, retext = [], None
    if name:
        extra_ops, notes, extra_owner, extra_blocked = rename(values, name, old, session, maps)
        ops = [op for op in ops if not (op[0] == "rewrite" and op[1] == old["project"])] + extra_ops
        owner, blocked = owner + extra_owner, blocked + extra_blocked
        retext = lambda path, text: rename_profile(text, values, name)[0] if path == old["project"] else text
    for path, (whole, under) in maps.items():
        print("map %s -> %s" % (path, whole) + ("" if whole == under else " (under it: %s)" % under))
    for line in notes:
        print(line)
    for op in ops:
        print(show(op))
    for step in owner:
        print("owner: " + step)
    for reason in blocked:
        print("blocked: " + reason)
    if not args.apply:
        print("crew migrate: preview; nothing written")
        return 1 if blocked else 0
    if blocked:
        print("crew: refusing migrate --apply: blocked")
        return 1
    return apply(old, new, ops, maps, retext)


def apply(old, new, ops, maps, retext=None):
    """Run the plan's operations in order with a journal; exit code."""
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    work = os.path.join(new["state"], "migration", stamp)
    moved = lambda path: new["state"] + path[len(old["state"]):] if path.startswith(old["state"] + os.sep) else path
    journal, rewritten, offsets = [], [], {}

    def save(name, data):
        os.makedirs(work, exist_ok=True)
        with open(os.path.join(work, name), "w") as f:
            json.dump(data, f, indent=2)

    def done(op, undo):
        journal.append({"op": show(op), "rollback": undo})
        if os.path.isdir(new["state"]):
            save("journal.json", journal)

    def original(path):
        rel = os.path.relpath(path, new["state"]) if path.startswith(new["state"] + os.sep) else \
            os.path.join("profile", os.path.basename(path))
        return os.path.join(work, "originals", rel)

    try:
        for op in ops:
            if op[0] == "move":
                os.makedirs(os.path.dirname(op[2]), exist_ok=True)
                shutil.move(op[1], op[2])
                done(op, shlex.join(["mv", op[2], op[1]]))
            elif op[0] == "copy-move":  # its nested trees hold absolute paths to its .git, and it to them
                trees, back = nested(op[1], op[1], op[2]), nested(op[1], op[1], op[1])
                os.makedirs(os.path.dirname(op[2]), exist_ok=True)
                shutil.move(op[1], op[2])
                done(op, shlex.join(["mv", op[2], op[1]]) + (" && " + shlex.join(
                    ["git", "-C", op[1], "worktree", "repair", *back]) if back else ""))
                repair(op[2], trees)
            elif op[0] == "archive":
                src, dst = moved(op[1]), os.path.join(work, "identities", os.path.relpath(op[1], old["state"]))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.replace(src, dst)
                done(op, shlex.join(["mv", dst, src]))
            elif op[0] == "worktree-move":
                os.makedirs(os.path.dirname(op[2]), exist_ok=True)
                r = subprocess.run(["git", "-C", new["checkout"], "worktree", "move", op[1], op[2]],
                                   capture_output=True, text=True)
                if r.returncode:
                    raise RuntimeError("git worktree move %s: %s" % (op[1], r.stderr.strip()))
                done(op, shlex.join(["git", "-C", new["checkout"], "worktree", "move", op[2], op[1]]))
            elif op[0] == "rewrite":
                path = moved(op[1])
                with open(path, "rb") as f:
                    data = f.read()
                os.makedirs(os.path.dirname(original(path)), exist_ok=True)
                shutil.copy2(path, original(path))
                text = data.decode("utf-8", "surrogateescape")
                text = (rewrite_profile(text, maps, new["repo"]) if path == new["project"] else rewrite(text, maps))[0]
                text = retext(path, text) if retext else text
                if path.startswith(os.path.join(new["state"], "status") + os.sep):
                    offsets[os.path.basename(path)[:-len(".status")]] = data
                with open(path, "w", encoding="utf-8", errors="surrogateescape") as f:
                    f.write(text)
                rewritten.append(path)
                done(op, shlex.join(["cp", original(path), path]))
            elif op[0] == "copy":
                with open(op[1], encoding="utf-8") as f:
                    settings = rewrite_settings(json.load(f), maps)
                os.makedirs(os.path.dirname(op[2]), exist_ok=True)
                with open(op[2], "w", encoding="utf-8") as f:
                    json.dump(settings, f, indent=2)
                    f.write("\n")
                done(op, shlex.join(["rm", op[2]]))
        reconcile_offsets(new["state"], offsets, maps)
    except (OSError, RuntimeError, ValueError) as e:
        print("crew: migrate --apply failed: %s" % e)
        for entry in journal:
            print("completed: " + entry["op"])
        for entry in reversed(journal):
            print("rollback: " + entry["rollback"])
        return 1
    save("map.json", {"from": old, "to": new, "map": maps, "rewritten": rewritten,
                      "kept": [op[1] for op in ops if op[0] == "keep"]})
    for entry in journal:
        print("done: " + entry["op"])
    print("crew migrate: applied; journal and originals in %s" % work)
    print("next: mdstack layout --project %s --write" % new["ref"])
    print("next: mdstack up --project %s --coordinator-only" % new["ref"])
    return 0


def is_guard(argv):
    """A crew turn-end guard command line: python3 <path>/mdstack guard --state <state>."""
    return len(argv) == 5 and argv[0] == "python3" and os.path.basename(argv[1]) == "mdstack" and argv[2:4] == ["guard", "--state"]


def guard_argv(command):
    with contextlib.suppress(ValueError):
        argv = shlex.split(command)
        return argv if is_guard(argv) else None
    return None


def commands_in(value, key=None):
    """Every hook `command` string in a settings object."""
    if isinstance(value, dict):
        return [c for k, v in value.items() for c in commands_in(v, k)]
    if isinstance(value, list):
        return [c for v in value for c in commands_in(v)]
    return [value] if isinstance(value, str) and key == "command" else []


def unquotable(command, maps, rx):
    """Whether a non-guard command cites an old path whose new path would need shell quoting."""
    if rx is None or guard_argv(command):
        return False
    targets = [maps[m.group(1)][1 if m.group(2) else 0] for m in rx.finditer(command)]
    return any(shlex.quote(path) != path for path in targets)


def rewrite_settings(value, maps, key=None):
    """Settings JSON with its paths rewritten. A mdstack guard command is rewritten per argument and re-quoted, so a new
    path with a space stays one argument; any other command keeps its shell text, with only the paths replaced (the
    plan refuses one whose new path would need quoting)."""
    if isinstance(value, dict):
        return {k: rewrite_settings(v, maps, k) for k, v in value.items()}
    if isinstance(value, list):
        return [rewrite_settings(v, maps) for v in value]
    if isinstance(value, str) and key == "command" and guard_argv(value):
        return shlex.join(rewrite(word, maps)[0] for word in guard_argv(value))
    return rewrite(value, maps)[0] if isinstance(value, str) else value


def reconcile_offsets(state, offsets, maps):
    """The watcher's byte offset into each rewritten status file: the length of its rewritten prefix."""
    path = os.path.join(state, "wake", "watch-state.json")
    if not offsets or not os.path.exists(path):
        return
    with open(path) as f:
        seen = json.load(f)
    for name, data in offsets.items():
        if name in seen.get("offsets", {}):
            prefix = data[:seen["offsets"][name]].decode("utf-8", "surrogateescape")
            seen["offsets"][name] = len(rewrite(prefix, maps)[0].encode("utf-8", "surrogateescape"))
            seen.get("digests", {}).pop(name, None)  # the recomputed offset is trusted, not the old prefix (#819)
    with open(path + ".tmp", "w") as f:
        json.dump(seen, f)
    os.replace(path + ".tmp", path)
