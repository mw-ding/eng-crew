"""`mdstack install` puts a stable `mdstack` on the user's PATH for the release bundle it runs from (#1317).

Usage: mdstack install [--dry-run]

Run it from a bundle extracted into ~/.mdstack/releases/. It points releases/current at that bundle and writes
the launcher ~/.mdstack/bin/mdstack, a shell script that runs releases/current/cli/mdstack, so a later
`mdstack upgrade --version` moves the launcher with no PATH change. When ~/.mdstack/bin is not on PATH, it links
mdstack into the first directory on PATH under your home that it can write and that holds no other mdstack (for
example ~/.local/bin), else prints the one line to add to your shell profile. It never edits a shell rc file.
--dry-run prints the plan and writes nothing. Doctor reports a missing or stale launcher and a PATH that resolves
mdstack to something else. Re-running is idempotent.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
from crew_shared import crew_render, ROOT


def home():
    """The user-level root, ~/.mdstack (#1316)."""
    return Path(os.path.expanduser(os.path.join("~", ".mdstack")))


def launcher_text(root):
    return ("#!/bin/sh\n# mdstack launcher, written by mdstack install (#1317): runs the current release.\n"
            'exec %s "$@"\n' % shlex.quote(str(root / "releases" / "current" / "cli" / "mdstack")))


def path_hint(root):
    shown = str(root / "bin")
    if shown.startswith(os.path.expanduser("~") + os.sep):
        shown = "$HOME" + shown[len(os.path.expanduser("~")):]
    return 'add to your shell profile: export PATH="%s:$PATH"' % shown


def flip(releases, bundle):
    """Point releases/current at bundle (a sibling, linked relatively) in one rename."""
    tmp = releases / ".current.tmp"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    tmp.symlink_to(bundle.name, target_is_directory=True)
    os.replace(tmp, releases / "current")


def path_dir(launcher):
    """(directory on PATH that resolves mdstack to the launcher, True), else (a directory under your home it can
    write, to link it there, False), else (None, False). Any other mdstack on PATH leaves (None, False)."""
    dirs = [Path(e) for e in os.environ.get("PATH", "").split(os.pathsep) if e and Path(e).is_absolute()]
    dirs = [d for d in dirs if d.is_dir()]
    for d in dirs:
        target = d / "mdstack"
        if d.resolve() == launcher.parent.resolve() or target.is_symlink() and target.resolve() == launcher.resolve():
            return d, True
        if target.exists() or target.is_symlink():
            return None, False  # it shadows any later link; doctor reports it
    user = Path.home().resolve()
    return next(((d, False) for d in dirs if d.resolve().is_relative_to(user) and os.access(d, os.W_OK)), (None, False))


def served(project, releases):
    """The other project files whose install, under the same state root as project, runs from a bundle in
    releases: what `mdstack upgrade --version` re-renders after project (#1317). install.json records `project`."""
    values, problems = crew_render.resolve(project, None)
    if problems:
        return []
    found = []
    for manifest in sorted(Path(values["paths.state_dir"]).absolute().glob("*/install.json")):
        record = json.loads(manifest.read_text())
        other = record.get("project")
        if (other and Path(other).is_file() and Path(other).resolve() != Path(project).resolve()
                and Path(record.get("source") or "/").resolve().parent == releases.resolve()):
            found.append(other)
    return found


def follow(args, bundle, argv, env):
    """After `mdstack upgrade --version` upgraded --project from bundle: run the same upgrade for every other
    project this install serves, then flip releases/current to bundle. No user-level install (no current link),
    a dry run or a failed project flips nothing."""
    releases = bundle.parent
    if not (releases / "current").is_symlink():
        return 0
    failed = []
    for project in served(args.project, releases):
        print("crew upgrade: also upgrading " + project, flush=True)
        argv[argv.index("--project") + 1] = project
        if subprocess.run(argv, env=env).returncode:
            failed.append(project)
    if failed:
        print("crew upgrade: releases/current not moved; failed: " + ", ".join(failed))
        return 1
    if not args.dry_run:
        flip(releases, bundle)
        print("crew upgrade: releases/current -> " + bundle.name)
    return 0


def register(sub):
    p = sub.add_parser("install", help="put a stable mdstack launcher on PATH for this release bundle")
    p.add_argument("--dry-run", action="store_true", help="print the plan; write nothing")


def run(args):
    try:
        return install(args)
    except OSError as e:
        print("crew install: " + str(e))
        return 1


def install(args):
    root, bundle = home(), Path(ROOT).resolve()
    releases = root / "releases"
    if bundle.parent != releases.resolve() or not (bundle / "VERSION").is_file():
        print("crew install: run mdstack install from a release bundle extracted into %s/" % releases)
        return 1
    launcher = root / "bin" / "mdstack"
    current = releases / "current"
    plan = []
    if not current.is_symlink() or current.resolve() != bundle:
        plan.append(("link", "%s -> %s" % (current, bundle.name)))
    if not launcher.is_file() or launcher.read_text() != launcher_text(root):
        plan.append(("launcher", str(launcher)))
    directory, linked = path_dir(launcher)
    if directory and not linked:
        plan.append(("PATH link", "%s -> %s" % (directory / "mdstack", launcher)))
    for step, detail in plan:
        if args.dry_run:
            pass
        elif step == "link":
            flip(releases, bundle)
        elif step == "launcher":
            launcher.parent.mkdir(parents=True, exist_ok=True)
            tmp = launcher.with_name(".mdstack.tmp")
            tmp.write_text(launcher_text(root))
            tmp.chmod(0o755)
            os.replace(tmp, launcher)
        else:
            (directory / "mdstack").symlink_to(launcher)
        print("crew install: %s %s %s" % ("would write" if args.dry_run else "wrote", step, detail))
    if not plan:
        print("crew install: no changes")
    if not directory:
        print("crew install: mdstack is not on PATH; " + path_hint(root))
    return 0
