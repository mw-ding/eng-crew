"""Builder confinement (#1252; docs/specs/portable.md, M47 B5's enforcing boundary).

A builder run gets its own working copy: a local clone whose Git administrative directory belongs to the run and
borrows the shared checkout's objects read-only (alternates), not a linked worktree of the shared checkout. A
confined run also launches under its harness's OS write sandbox, writable only under that copy and the crew state
directory, so a raw shell cannot remove a sibling run's copy or write the shared checkout's metadata.
`runtime.options.confinement = "enforce"` refuses a builder configuration that cannot enforce this; `off` (default)
launches it and marks the run unconfined.
"""
import os
import subprocess


def run_copy(git, repo, wt, sha, base):
    """Create wt as the run's own clone of repo, detached at sha, its origin the shared checkout's origin and
    origin/<default> at base (the just-fetched default branch). Objects come from repo's object store, read-only."""
    objects = os.path.join(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"), "objects")
    git(os.path.dirname(wt), "init", "-q", wt)
    with open(os.path.join(wt, ".git", "objects", "info", "alternates"), "w") as f:
        f.write(objects + "\n")
    git(wt, "remote", "add", "origin", git(repo, "remote", "get-url", "origin"))
    push = git(repo, "remote", "get-url", "--push", "origin")
    if push != git(wt, "remote", "get-url", "origin"):
        git(wt, "remote", "set-url", "--push", "origin", push)
    git(wt, "update-ref", "refs/remotes/origin/%s" % base[0], base[1])
    git(wt, "checkout", "-q", "--detach", sha)


def inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root + os.sep)


def unsupported(values, role, adapter, mode, remote, state, repo, wt=None):
    """Why this builder launch does not enforce confinement, or None when it does (spec B5 item 3). An existing wt
    (a restart) must keep its git metadata inside itself, as a run copy does."""
    if role != "builder":
        return "not a builder run"
    if remote:
        return "a role-host builder is not confined yet"
    if mode not in getattr(adapter, "CONFINES", ()):
        return "%s with permission_mode=%s applies no OS write sandbox mdstack sets" % (adapter.TITLE, mode)
    for label, path in (("paths.worktree_root", values["paths.worktree_root"]), ("the shared checkout", repo)):
        if inside(path, state):
            return "%s %s is inside the crew state directory, a writable root" % (label, path)
    if wt:
        common = subprocess.run(["git", "-C", wt, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True).stdout.strip()
        if not common or not inside(common, wt):
            return "its worktree %s shares the checkout's git metadata (spawned before #1252)" % wt
    return None


def decide(values, role, adapter, mode, remote, state, repo, wt=None):
    """(confined, reason): RuntimeError under confinement=enforce when the launch cannot enforce it."""
    reason = unsupported(values, role, adapter, mode, remote, state, repo, wt)
    if reason and role == "builder" and values.get("runtime.options.confinement", "off") == "enforce":
        raise RuntimeError("crew: refusing launch: confinement=enforce: %s (docs/runtimes/tmux.md#confinement)" % reason)
    return reason is None, reason


def tmpdir(wt):
    """A confined run's TMPDIR, inside its own copy (.crew/ is excluded): the sandbox drops /tmp and $TMPDIR."""
    path = os.path.join(wt, ".crew", "tmp")
    os.makedirs(path, exist_ok=True)
    return path
