"""`mdstack gc` sweeps run working copies under `paths.worktree_root` that lifecycle reaping missed (#316).

Candidates: a local run record whose worktree sits directly under the root and whose window is gone, and a directory
directly under the root that no run record names (an orphan). Dry-run by default: one line per candidate,
`path<TAB>run<TAB>keep|remove<TAB>reason`. A candidate is `remove` only when its PR is merged (the record's PR, else
a merged PR whose head is the copy's HEAD) and C6 proves the work landed: a clean tree and every commit on the
default branch, its branch or that PR's head. Everything else is kept with its reason: a symlink or path outside the
root (never followed), a live window, a working-copy claim or another run's reference, an orphan younger than an hour,
nested worktrees, an open or closed-unmerged PR, no merged PR, unlanded work or an unreadable copy. Runs on a role host are out of scope (the host reaps them).

`--apply` re-checks each candidate (the root boundary again right before deleting) and removes up to `--max`: a linked worktree with
`git worktree remove` (never `--force`), a run's own copy (#1252) by deleting its directory, then the run's records
through the kill path. A failed removal is printed as `failed` and the command exits 1; no forced or fallback removal
follows. A rerun with nothing left removes nothing.

Usage: mdstack gc [--apply] [--max N] --project FILE [--org-profile FILE]
"""
import os
import shutil
import subprocess
import time
from crew_shared import checkout, commands, copy_claim, git, kill_run, profile, remember_pr, remote_run, runs, tmux, unlanded

ORPHAN_MIN_AGE = 3600  # seconds: a spawn creates its directory before it records the worktree path


def register(sub):
    p = sub.add_parser("gc")
    p.add_argument("--apply", action="store_true", help="remove the `remove` candidates (default: dry run)")
    p.add_argument("--max", type=int, default=10, help="at most this many removals per run (default 10)")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def tracker(values, *args):
    """A JSON read from the tracker through route's client (no tool CLI named here, rule D6)."""
    return commands()["route"].gh(*args, "-R", "%s/%s" % (values["repo.owner"], values["repo.name"]))


def run_pr(state, name, rec):
    """The run's PR number from its record, item or builder done line, else None."""
    status = os.path.join(state, "status", name + ".status")
    if os.path.exists(status):
        with open(status) as f:
            for line in f.read().splitlines():
                remember_pr(rec, line)
    item = rec.get("item", "")
    return rec.get("pr") or rec.get("args", {}).get("pr") or (int(item.split("PR #")[1].split()[0].rstrip(",;"))
                                                              if "PR #" in item else None)


def candidates(values, state):
    root = os.path.realpath(values["paths.worktree_root"])
    recorded, out = {}, []
    for name, rec in runs(state):
        wt = rec.get("worktree")
        if wt:
            recorded[os.path.realpath(wt)] = name
        if wt and not remote_run.host_of(rec) and os.path.dirname(os.path.realpath(wt)) == root:
            out.append((os.path.realpath(wt), name, dict(rec)))
    for entry in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        path = os.path.join(root, entry)  # unresolved: a symlink here is reported, never followed (#316 r1)
        if os.path.isdir(path) and os.path.realpath(path) not in recorded:
            out.append((path, None, {}))
    return out, recorded


def outside_root(values, path):
    """Why path is not a real directory directly under the configured root, or None."""
    if os.path.islink(path):
        return "symlink to %s, not followed" % os.path.realpath(path)
    if os.path.dirname(os.path.realpath(path)) != os.path.realpath(values["paths.worktree_root"]):
        return "outside %s" % os.path.realpath(values["paths.worktree_root"])
    return None


def classify(values, session, state, project, path, name, rec, recorded):
    """("keep" | "remove", reason, pr) for one candidate, read fresh."""
    escape = outside_root(values, path)
    if escape:
        return "keep", escape, None
    if name and name in {n for _, n in tmux.list_windows(session)}:
        return "keep", "window live", None
    protected = [checkout(values, project), state, os.getcwd()]
    if any(os.path.realpath(p) == path or os.path.realpath(p).startswith(path + os.sep) for p in protected):
        return "keep", "protected path inside", None
    other = [n for p, n in recorded.items() if n != name and (p == path or p.startswith(path + os.sep))]
    if other:
        return "keep", "referenced by run " + other[0], None
    held = copy_claim.holder(path)
    if held and (held.get("crew"), held.get("run")) != (state, name):
        return "keep", "working-copy claim held by run %s" % held.get("run"), None
    head = None
    if os.path.isdir(path):
        if not name and time.time() - os.path.getmtime(path) < ORPHAN_MIN_AGE:
            return "keep", "orphan younger than 1h", None
        if not os.path.exists(os.path.join(path, ".git")):
            return "keep", "not a git working copy", None
        try:
            head = git(path, "rev-parse", "HEAD")
            listed = git(path, "worktree", "list", "--porcelain").splitlines()
        except RuntimeError as e:
            return "keep", "unreadable: %s" % str(e).splitlines()[0], None
        if any(os.path.realpath(line[9:]).startswith(path + os.sep) for line in listed if line.startswith("worktree ")):
            return "keep", "has nested worktrees", None
    try:
        pr = run_pr(state, name, rec) if name else None
        if pr:
            st = tracker(values, "pr", "view", str(pr), "--json", "state")["state"]
            if st != "MERGED":
                return "keep", "PR #%s %s" % (pr, "open" if st == "OPEN" else "closed, not merged"), pr
        elif head:
            found = [p for p in tracker(values, "pr", "list", "--state", "merged", "--search", head,
                                   "--json", "number,headRefOid") or [] if p.get("headRefOid") == head]
            pr = found[0]["number"] if found else None
        if not pr:
            return "keep", "no merged PR", None
        items = unlanded(values, dict(rec, pr=pr), path) if head else []
    except (RuntimeError, ValueError, KeyError, TypeError) as e:
        return "keep", "unchecked: %s" % str(e).splitlines()[0], pr
    if items:
        return "keep", "unlanded: %s%s" % (items[0], " (+%d more)" % (len(items) - 1) if len(items) > 1 else ""), pr
    return "remove", "PR #%s merged, landed" % pr, pr


def remove(values, session, state, path, name):
    """None on success, else why the removal failed."""
    escape = outside_root(values, path)  # the boundary again, right before deleting anything
    if escape:
        return "refused: " + escape
    if os.path.isdir(path):
        if os.path.isfile(os.path.join(path, ".git")):  # a linked worktree: git removes it and its admin entry
            common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
            r = subprocess.run(["git", "--git-dir", common, "worktree", "remove", path], capture_output=True, text=True)
            if r.returncode:
                return r.stderr.strip() or "git worktree remove exit %d" % r.returncode
        else:  # a run's own copy (#1252): its directory is the whole copy
            try:
                shutil.rmtree(path)
            except OSError as e:
                return "%s: %s" % (e.strerror or e, getattr(e, "filename", path))
    if name and kill_run(values, session, state, name):
        return "run records kept by the kill path"
    return None


def run(args):
    values, session, state = profile(args, "worktree_root")
    found, _ = candidates(values, state)
    counts, budget = {"remove": 0, "keep": 0, "removed": 0, "failed": 0}, args.max
    for path, name, rec in found:
        _, recorded = candidates(values, state)  # re-read the references before each decision
        cls, reason, _ = classify(values, session, state, args.project, path, name, rec, recorded)
        if cls == "remove" and args.apply:
            if budget <= 0:
                cls, reason = "keep", "over --max %d" % args.max
            else:
                budget -= 1
                err = remove(values, session, state, path, name)
                cls, reason = ("removed", reason) if err is None else ("failed", err)
        counts[cls] += 1
        print("\t".join([path, name or "-", cls, reason]))
    if args.apply:
        print("gc: removed %(removed)d, failed %(failed)d, kept %(keep)d" % counts)
    else:
        print("gc: dry run: %(remove)d to remove, %(keep)d kept (pass --apply to remove)" % counts)
    return 1 if counts["failed"] else 0
