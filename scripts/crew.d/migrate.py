"""`crew migrate` previews moving a stopped crew from one profile's layout to another's (#1178).

Usage: crew migrate --project OLD --to NEW [--org-profile FILE]

OLD is the profile the crew runs from today; NEW is the relocated profile the owner wrote (for example
~/crew-home/crew.toml with paths.root). Both must resolve and name the same repo. The preview writes nothing and
prints, one per line: each path mapping (`map OLD -> NEW`, most specific first), each operation (`move` of the
project's state directory and the live dir, `worktree-move` of each registered role worktree under the old worktree
root, `keep` of each unregistered directory there, `archive` of the old lead and watcher process identities,
`rewrite FILE (N refs)` of every operational state file and the new profile that cite an old path, `copy` of the
home's .claude/settings.local.json with its paths rewritten), then `owner:` steps it never takes (Claude Code
memory and Codex trust are keyed by absolute path), then `blocked:` lines. Historical evidence (verdicts, trains,
retained, ci, triage, schedule logs) moves with the state directory unchanged.

Blocked, exit 1: the old session or watcher is still live (run `crew down --preserve` first), the land lock is held,
the two checkouts are not the same git repository, or a destination already exists. Otherwise exit 0.
"""
import glob
import os
import re
import subprocess
from crew_shared import checkout, commands, crew_render, profile, tmux

OPERATIONAL = ["runs/*.json", "runs/*.md", "leads/*.md", "leads/*-events/*", "leads/reclaimed-workers/*",
               "inbox/*.jsonl", "status/*.status", "spawn-queue.jsonl", "wake/queue.jsonl", "wake/watch-state.json"]
IDENTITIES = ["leads/builder.json", "leads/reviewer.json", "wake/watcher.pid"]
SETTINGS = os.path.join(".claude", "settings.local.json")
CLAUDE_KEY = re.compile(r"[^A-Za-z0-9]")  # Claude Code's per-project directory name for an absolute cwd


def register(sub):
    p = sub.add_parser("migrate")
    p.add_argument("--project", required=True, help="the profile the crew runs from today")
    p.add_argument("--to", required=True, help="the relocated profile")
    p.add_argument("--org-profile")


def layout(values, project, state):
    home = os.path.dirname(os.path.abspath(project))
    return {"project": os.path.abspath(project), "home": home, "checkout": checkout(values, project), "state": state,
            "worktree_root": os.path.abspath(values["paths.worktree_root"]),
            "live_dir": os.path.abspath(values["paths.live_dir"]) if values.get("paths.live_dir") else None,
            "eng_crew": os.path.abspath(values["paths.eng_crew"]) if values.get("paths.eng_crew") else None}


# Most specific first: a whole-path reference to the old directory is the checkout (a run record's repo) before the
# home, while a path under it is the state, worktree root, live dir or bundle (docs, scripts) before the home.
EXACT = ["project", "state", "worktree_root", "live_dir", "checkout", "home", "eng_crew"]
UNDER = ["project", "state", "worktree_root", "live_dir", "eng_crew", "home", "checkout"]


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
    for pair in maps.values():
        pair[0], pair[1] = pair[0] or pair[1], pair[1] or pair[0]
    return dict(sorted(((p, pair) for p, pair in maps.items() if pair != [p, p]), key=lambda kv: -len(kv[0])))


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


def common_dir(repo):
    r = subprocess.run(["git", "-C", repo, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                       capture_output=True, text=True)
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 else None


def files(state, globs):
    return sorted({p for g in globs for p in glob.glob(os.path.join(state, g)) if os.path.isfile(p)})


def plan(old, new, session, maps):
    """(operations, owner steps, blockers); each operation is a tuple naming its kind first."""
    ops, owner, blocked = [], [], []
    if tmux.has_session(session):
        blocked.append("session %s is running; run crew down --preserve --project %s" % (session, old["project"]))
    if commands()["watch"].armed(os.path.join(old["state"], "wake", "watcher.pid")):
        blocked.append("the watcher is armed; run crew down --preserve --project %s" % old["project"])
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
    if os.path.isdir(old["worktree_root"]) and old["worktree_root"] != new["worktree_root"]:
        for name in sorted(os.listdir(old["worktree_root"])):
            path = os.path.join(old["worktree_root"], name)
            if not os.path.isdir(path):
                continue
            ops.append(("worktree-move", path, os.path.join(new["worktree_root"], name)) if os.path.realpath(path) in registered
                       else ("keep", path, "not a registered worktree of %s" % old["checkout"]))
    if old["live_dir"] and new["live_dir"] and old["live_dir"] != new["live_dir"] and os.path.isdir(old["live_dir"]):
        ops.append(("move", old["live_dir"], new["live_dir"]))
    rx = pattern(maps)
    for path in files(old["state"], OPERATIONAL) + [new["project"]]:
        with open(path, encoding="utf-8", errors="surrogateescape") as f:
            count = rewrite(f.read(), maps, rx)[1]
        if count:
            ops.append(("rewrite", path, count))
    settings = os.path.join(old["home"], SETTINGS)
    if old["home"] != new["home"] and os.path.isfile(settings):
        ops.append(("copy", settings, os.path.join(new["home"], SETTINGS)))
    for op in ops:
        if op[0] in ("move", "worktree-move", "copy") and os.path.lexists(op[2]):
            blocked.append("destination exists: %s" % op[2])
    for key in ("home", "checkout"):
        if old[key] != new[key]:
            owner.append("Claude Code memory for %s lives under ~/.claude/projects/%s/; carry it to %s/ with the "
                         "owner's go" % (old[key], CLAUDE_KEY.sub("-", old[key]), CLAUDE_KEY.sub("-", new[key])))
    if old["home"] != new["home"]:
        owner.append("trust %s in Claude Code and Codex on first start (crew writes no user-level config)" % new["home"])
    return ops, owner, blocked


def show(op):
    if op[0] == "rewrite":
        return "rewrite %s (%d refs)" % (op[1], op[2])
    if op[0] == "keep":
        return "keep %s (%s)" % (op[1], op[2])
    return " ".join(op[:2]) + (" -> " + op[2] if len(op) > 2 else "")


def run(args):
    values, session, state = profile(args, "worktree_root")
    new_values, problems = crew_render.resolve(args.to, args.org_profile)
    if problems:
        print("\n".join(problems))
        return 1
    if (new_values["repo.owner"], new_values["repo.name"]) != (values["repo.owner"], values["repo.name"]):
        print("crew: refusing migrate: %s and %s name different repos" % (args.project, args.to))
        return 1
    new_state = os.path.join(os.path.abspath(new_values["paths.state_dir"]),
                             "%s__%s" % (new_values["repo.owner"], new_values["repo.name"]))
    old, new = layout(values, args.project, state), layout(new_values, args.to, new_state)
    maps = mappings(old, new)
    ops, owner, blocked = plan(old, new, session, maps)
    for path, (whole, under) in maps.items():
        print("map %s -> %s" % (path, whole) + ("" if whole == under else " (under it: %s)" % under))
    for op in ops:
        print(show(op))
    for step in owner:
        print("owner: " + step)
    for reason in blocked:
        print("blocked: " + reason)
    print("crew migrate: preview; nothing written")
    return 1 if blocked else 0
