#!/usr/bin/env python3
"""One-off purge of stale git worktrees on the crew host (#1161, a slice of #316).

Lists every `git worktree list` entry of the repo with its branch, head, PR
state read back from GitHub, classification (`keep` or `remove`) and reason.
A row is `remove` only when it is not the main worktree, a protected checkout
or the current directory; no run record (`$CREW_STATE/runs/*.json`, the
source `crew status` reads), claim or tmux pane references it; `git status
--porcelain` is empty apart from `.crew/` scratch; and its head is an
ancestor of `origin/<base>` or a merged or closed PR has exactly that head and
its remote branch matches or is gone. Every run also lists `orphan` rows: a
directory under a scanned root (each worktree's parent and every `--root`)
whose `.git` names a missing gitdir. Dry-run is the default. `--apply` first
checks that every `remove` row and its parent are writable and removes nothing
if any is not. It then runs `git worktree remove` (never `--force`) on `remove`
rows, stops at the first failure, reports it as `failed` and any orphan it left,
and exits non-zero; only a run with no failure runs `git worktree prune`. Local
branches are left alone. Not run by CI.

Usage: worktree-purge.py [--repo DIR] [--state DIR] [--protect PATH]... [--root DIR]... [--base BRANCH] [--apply]
"""
import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys
import tempfile


def git(cwd, *args, **kw):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, **kw)


def real(path):
    return os.path.realpath(path)


def under(path, root):
    return path == root or path.startswith(root.rstrip("/") + "/")


def worktrees(repo):
    rows, cur = [], None
    for line in git(repo, "worktree", "list", "--porcelain").stdout.splitlines():
        key, _, val = line.partition(" ")
        if key == "worktree":
            cur = {"path": real(val), "head": "", "branch": None, "bare": False}
            rows.append(cur)
        elif key == "HEAD":
            cur["head"] = val
        elif key == "branch":
            cur["branch"] = val.removeprefix("refs/heads/")
        elif key == "bare":
            cur["bare"] = True
    return rows


def gh_prs(repo, branch, sha):
    """PRs whose head branch is `branch` or that contain `sha`, from GitHub."""
    out = []
    queries = [["--head", branch]] if branch else []
    queries.append(["--search", sha])
    for q in queries:
        p = subprocess.run(["gh", "pr", "list", "--state", "all", *q, "--json",
                            "number,state,headRefOid,headRefName"],
                           cwd=repo, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError("gh pr list failed: " + p.stderr.strip())
        out += json.loads(p.stdout or "[]")
    return out


def pane_paths():
    p = subprocess.run(["tmux", "list-panes", "-a", "-F", "#{pane_current_path}"],
                       capture_output=True, text=True)
    return [real(x) for x in p.stdout.splitlines() if x] if p.returncode == 0 else []


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def references(state, panes):
    """(label, path or None, item number or None) for every live reference."""
    refs = []
    for f in sorted(glob.glob(os.path.join(state, "runs", "*.json"))):
        try:
            with open(f) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            refs.append(("unreadable run record " + os.path.basename(f), "/", None))
            continue
        for s in strings(data):
            if s.startswith("/"):
                refs.append(("run record " + os.path.basename(f), real(s), None))
    for f in sorted(glob.glob(os.path.join(state, "claims", "*"))):
        name = os.path.basename(f)
        m = re.search(r"(?:issue|pr)(\d+)", name)
        refs.append(("claim " + name, None, m.group(1) if m else None))
        with open(f, errors="replace") as fh:
            for tok in fh.read().split():
                if tok.startswith("/"):
                    refs.append(("claim " + name, real(tok), None))
    refs += [("tmux pane", p, None) for p in panes]
    return refs


def referenced_by(path, refs):
    base = os.path.basename(path)
    for label, p, num in refs:
        if p == "/" or (p and (under(p, path) or p == path)) or (num and base.startswith(num + "-")):
            return label
    return None


def dirty(path):
    p = git(path, "status", "--porcelain")
    if p.returncode != 0:
        return ["git status failed"]
    return [ln for ln in p.stdout.splitlines() if not ln[3:].startswith(".crew/")]


def remote_head(repo, branch):
    p = git(repo, "ls-remote", "origin", "refs/heads/" + branch)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip().splitlines()[0] if p.stderr.strip() else "exit %d" % p.returncode)
    out = p.stdout.split()
    return out[0] if out else None


def pr_label(prs):
    return ",".join(sorted({"%s#%s" % (p["state"], p["number"]) for p in prs})) or "none"


def classify(wt, ctx):
    """Return (pr_state, cls, reason) for one worktree row."""
    path = wt["path"]
    if wt is ctx["main"]:
        return "-", "keep", "main worktree"
    if wt["bare"]:
        return "-", "keep", "bare entry"
    if under(ctx["cwd"], path):
        return "-", "keep", "current directory"
    if any(under(path, p) for p in ctx["protect"]):
        return "-", "keep", "protected checkout"
    try:
        prs = ctx["lookup"](ctx["repo"], wt["branch"], wt["head"])
    except Exception as exc:
        return "error", "keep", "PR lookup failed: %s" % exc
    label = pr_label(prs)
    ref = referenced_by(path, ctx["refs"])
    if ref:
        return label, "keep", "referenced by " + ref
    if not os.path.isdir(path):
        return label, "keep", "path missing (prune handles it)"
    changes = dirty(path)
    if changes:
        return label, "keep", "uncommitted changes (%d paths)" % len(changes)
    if git(ctx["repo"], "merge-base", "--is-ancestor", wt["head"], ctx["upstream"]).returncode == 0:
        return label, "remove", "head in " + ctx["upstream"]
    done = [p for p in prs if p["state"] in ("MERGED", "CLOSED") and p["headRefOid"] == wt["head"]]
    if not done:
        if any(p["state"] == "OPEN" for p in prs):
            return label, "keep", "PR open"
        if prs:
            return label, "keep", "head differs from every merged or closed PR head"
        return label, "keep", "no PR and head not in " + ctx["upstream"]
    pr = done[0]
    try:
        remote = remote_head(ctx["repo"], pr["headRefName"])
    except RuntimeError as exc:
        return label, "keep", "remote branch lookup failed: %s" % exc
    if remote is None:
        return label, "remove", "PR #%s %s, remote branch gone" % (pr["number"], pr["state"].lower())
    if remote == wt["head"]:
        return label, "remove", "PR #%s %s, remote branch matches" % (pr["number"], pr["state"].lower())
    return label, "keep", "PR #%s %s, remote branch moved" % (pr["number"], pr["state"].lower())


def missing_gitdir(path):
    """The gitdir that `path/.git` names when that gitdir is gone, else None."""
    try:
        with open(os.path.join(path, ".git")) as fh:
            line = fh.readline().strip()
    except OSError:
        return None
    if not line.startswith("gitdir: "):
        return None
    gitdir = os.path.join(path, line[len("gitdir: "):])
    return None if os.path.isdir(gitdir) else gitdir


def orphans(roots, listed):
    """Directories directly under `roots` whose `.git` names a missing gitdir."""
    found = []
    for root in sorted(set(roots)):
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in names:
            path = real(os.path.join(root, name))
            gitdir = path not in listed and os.path.isdir(path) and missing_gitdir(path)
            if gitdir:
                found.append((path, gitdir))
    return found


def unwritable(path):
    """Why this process cannot create and delete an entry in `path`, or None."""
    try:
        fd, probe = tempfile.mkstemp(prefix=".purge-probe-", dir=path)
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        return exc.strerror or str(exc)
    return None


def summary_key(reason):
    reason = re.sub(r"^(referenced by (?:unreadable run record|run record|claim|tmux pane)).*", r"\1", reason)
    return re.sub(r"\s*(#\d+|\(\d+ paths\))", "", reason)


def run(repo, state, protect, base, apply, cwd, lookup=gh_prs, panes=pane_paths, out=sys.stdout, roots=()):
    repo = git(repo, "rev-parse", "--show-toplevel").stdout.strip() or repo
    rows = worktrees(repo)
    ctx = {"repo": repo, "main": rows[0], "cwd": real(cwd), "lookup": lookup,
           "protect": [real(p) for p in protect], "upstream": "origin/" + base,
           "refs": references(state, panes()) if state else [("tmux pane", p, None) for p in panes()]}
    results = []
    for wt in rows:
        pr, cls, reason = classify(wt, ctx)
        results.append((wt, cls, reason))
        print("\t".join([wt["path"], wt["branch"] or "(detached)", wt["head"][:7], pr, cls, reason]), file=out)
    scan = [real(r) for r in roots] + [os.path.dirname(wt["path"]) for wt in rows[1:]]
    for path, gitdir in orphans(scan, {wt["path"] for wt in rows}):
        reason = "gitdir %s missing" % gitdir
        results.append(({"path": path}, "orphan", reason))
        print("\t".join([path, "-", "-", "-", "orphan", reason]), file=out)
    by = collections.Counter((cls, summary_key(r) if cls != "orphan" else "gitdir missing")
                             for _, cls, r in results)
    print("\nsummary:", file=out)
    for (cls, reason), n in sorted(by.items()):
        print("  %3d %s: %s" % (n, cls, reason), file=out)
    if not apply:
        print("dry run: %d remove, %d keep, %d orphan (pass --apply to remove)" % tuple(
            sum(c == k for _, c, _ in results) for k in ("remove", "keep", "orphan")), file=out)
        return 0
    targets = [wt["path"] for wt, cls, _ in results if cls == "remove"]
    blocked = [(p, why) for t in targets for p in (t, os.path.dirname(t)) for why in [unwritable(p)] if why]
    if blocked:
        for path, why in blocked:
            print("unwritable %s: %s" % (path, why), file=out)
        print("preflight failed: %d unwritable paths, nothing removed" % len(blocked), file=out)
        return 1
    removed = failed = kept = 0
    with tempfile.NamedTemporaryFile("w", suffix=".exclude") as ex:
        ex.write(".crew/\n")
        ex.flush()
        for wt, cls, reason in results:
            if cls == "orphan":
                continue
            if cls != "remove" or failed:
                kept += 1
                if cls == "remove":
                    print("skipped %s: stopped after a failure" % wt["path"], file=out)
                continue
            p = git(repo, "-c", "core.excludesFile=" + ex.name, "worktree", "remove", wt["path"])
            if p.returncode == 0:
                removed += 1
                print("removed %s" % wt["path"], file=out)
                continue
            failed += 1
            print("failed %s: %s" % (wt["path"], p.stderr.strip()), file=out)
            gitdir = os.path.isdir(wt["path"]) and missing_gitdir(wt["path"])
            if gitdir:
                print("orphan %s: git removed its admin entry %s" % (wt["path"], gitdir), file=out)
    if failed:
        print("not pruned: a removal failed", file=out)
    else:
        git(repo, "worktree", "prune")
        print("pruned", file=out)
    print("removed %d, failed %d, kept %d" % (removed, failed, kept), file=out)
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--state", default=os.environ.get("CREW_STATE"))
    ap.add_argument("--protect", action="append", default=[])
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--base", default="main")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    protect = a.protect + ([os.path.dirname(os.environ["CREW_PROJECT"])] if os.environ.get("CREW_PROJECT") else [])
    return run(a.repo, a.state, protect, a.base, a.apply, os.getcwd(), roots=a.root)


if __name__ == "__main__":
    sys.exit(main())
