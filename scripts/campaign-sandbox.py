#!/usr/bin/env python3
"""M25 disposable sandbox (#785): set up and tear down a level-a local sandbox, and plan a level-b forge sandbox.

`setup` refuses before any write when ROOT exists non-empty or overlaps a production root, then creates under ROOT a
bare origin (`origin.git`), a clone (`repo`) seeded with a local CI fixture, the sandbox profile (`crew.toml`, its own
repo slug, tmux session and state/worktree/live roots), a control-item and fixtures record (`state/sandbox.json`:
labels, identities, CI), the guarded run manifest (`state/manifest.json`, via campaign-guard.py) and, when tmux is
installed, the `state/bin/tmux` shim that pins every scenario tmux call to the sandbox socket. `teardown` runs
the guard check, kills only the sandbox's own tmux session on the sandbox socket, records every repo or worktree with uncommitted or
unpushed work and the sentinel check in `state/cleanup.json`; `--remove` deletes ROOT only when nothing is retained
and the sentinel is unchanged. `plan-forge` prints the level-b forge operations and never runs them: level b is
blocked on owner account access. Python 3.11+ stdlib only. Contract and runbook: docs/campaign-harness.md.

Usage: campaign-sandbox.py setup --root DIR --run-id ID --production FILE --source DIR --release ID --sentinel FILE
                                 [--scenario AXX ...]
       campaign-sandbox.py teardown MANIFEST [--remove]
       campaign-sandbox.py plan-forge --repo OWNER/NAME --production FILE
"""
import argparse
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard, crew_repo = load("campaign_guard", "campaign-guard.py"), load("crew_repo", "crew-repo.py")
EXTRA_LABELS = ["integration:finding", "integration:run"]
IDENTITIES = {"builder": "sandbox-builder", "reviewer": "sandbox-reviewer"}
PROFILE = """[repo]\nowner = "campaign"\nname = "sandbox-{run}"\ndefault_branch = "main"\n
[runtime]\nname = "tmux"\n\n[runtime.options]\nsession = "crew-campaign-{run}"\n
[paths]\nstate_dir = "{root}/state"\nworktree_root = "{root}/wt"\nlive_dir = "{root}/live"\n"""
# An inherited $TMUX beats TMUX_TMPDIR, so a bare `tmux kill-server` from a crew pane kills the owner's server (#817).
SHIM = """#!/bin/sh
# Campaign sandbox tmux shim (#817): pin every call to the sandbox socket and never follow an inherited $TMUX.
sock={sock}
want=
for arg; do
  if [ -n "$want" ]; then
    [ "$want" = S ] && [ "$arg" != "$sock" ] && {{ echo "tmux shim: refused -S $arg (outside the sandbox)" >&2; exit 2; }}
    want=; continue
  fi
  case "$arg" in
    -L*) echo "tmux shim: refused $arg (outside the sandbox)" >&2; exit 2 ;;
    -S) want=S ;;
    -S*) [ "${{arg#-S}}" = "$sock" ] || {{ echo "tmux shim: refused $arg (outside the sandbox)" >&2; exit 2; }} ;;
    -c|-f|-T) want=v ;;
    -*) ;;
    *) break ;;
  esac
done
unset TMUX TMUX_PANE
exec {real} -S "$sock" "$@"
"""


def tmux_socket(state_dir):
    return os.path.join(state_dir, "tmux", "tmux-%d" % os.getuid(), "default")


def install_shim(state_dir):
    real = shutil.which("tmux")
    if not real:
        return None
    sock = tmux_socket(state_dir)
    os.makedirs(os.path.dirname(sock), mode=0o700)
    shim = Path(state_dir, "bin", "tmux")
    shim.parent.mkdir()
    shim.write_text(SHIM.format(sock=shlex.quote(sock), real=shlex.quote(real)))
    shim.chmod(0o755)
    return {"socket": sock, "shim": str(shim)}


def git(*args, cwd=None):
    return subprocess.run(["git", "-c", "user.name=campaign", "-c", "user.email=campaign@sandbox.invalid", *args],
                          cwd=cwd, capture_output=True, text=True, check=True).stdout


def setup(a):
    root = os.path.realpath(a.root)
    prod = guard.target(a.production)["roots"].values()
    if os.path.exists(root) and os.listdir(root):
        return ["root: %s exists and is not empty" % root]
    if any(guard.nested(root, p) for p in prod):
        return ["root: %s overlaps a production root" % root]
    for sub in ("state", "wt", "live"):
        os.makedirs(os.path.join(root, sub))
    git("init", "-q", "--bare", "-b", "main", os.path.join(root, "origin.git"))
    repo = os.path.join(root, "repo")
    git("clone", "-q", os.path.join(root, "origin.git"), repo)
    Path(repo, "ci.sh").write_text("#!/bin/sh\n# Level-a CI fixture: the scenario sets CI_RESULT to replay red.\n"
                                   "exit \"${CI_RESULT:-0}\"\n")
    git("add", "ci.sh", cwd=repo)
    git("commit", "-q", "-m", "campaign sandbox seed", cwd=repo)
    git("push", "-q", "origin", "HEAD:main", cwd=repo)
    Path(root, "crew.toml").write_text(PROFILE.format(run=a.run_id, root=root))
    labels = [n for n, _, _ in crew_repo.LABELS] + EXTRA_LABELS
    Path(root, "state", "sandbox.json").write_text(json.dumps({
        "level": "a", "run_id": a.run_id, "labels": labels, "identities": IDENTITIES, "ci": "ci.sh",
        "tmux": install_shim(os.path.join(root, "state")),
        "control_item": {"number": 1, "title": "M25 campaign control (%s)" % a.run_id, "labels": ["integration:run"]},
    }, indent=2) + "\n")
    argv = ["manifest", "--sandbox", os.path.join(root, "crew.toml"), "--production", a.production, "--source",
            a.source, "--release", a.release, "--run-id", a.run_id, "--sentinel", a.sentinel,
            "--out", os.path.join(root, "state", "manifest.json")]
    return guard.main(argv + [x for s in a.scenario for x in ("--scenario", s)])


def retained(m):
    """Every sandbox repo or worktree with uncommitted changes or commits not on a remote, on any local branch."""
    root = os.path.dirname(m["profile"]["path"])
    wt = m["roots"]["worktree_root"]
    out = []
    for path in [os.path.join(root, "repo")] + sorted(os.path.join(wt, d) for d in os.listdir(wt)):
        if not os.path.exists(os.path.join(path, ".git")):
            continue
        dirty = git("status", "--porcelain", cwd=path).splitlines()
        unpushed = git("log", "--format=%H %s", "HEAD", "--branches", "--not", "--remotes",
                       cwd=path).splitlines()
        if dirty or unpushed:
            out.append({"path": path, "dirty": dirty, "unpushed": unpushed})
    return out


def teardown(a):
    m = json.loads(Path(a.manifest).read_text())
    problems = guard.refusals(m)
    if problems:
        return problems
    session = m["session"]
    env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
    killed = bool(shutil.which("tmux")) and subprocess.run(
        ["tmux", "-S", tmux_socket(m["roots"]["state_dir"]), "kill-session", "-t", "=" + session],
        capture_output=True, env=env).returncode == 0
    keep = retained(m)
    sentinel = guard.main(["sentinel", a.manifest]) == 0
    record = {"run_id": m["run_id"], "session": session, "session_killed": killed, "retained": keep,
              "sentinel_unchanged": sentinel}
    Path(m["roots"]["state_dir"], "cleanup.json").write_text(json.dumps(record, indent=2) + "\n")
    print("retained: %d worktree(s)%s" % (len(keep), "".join("\n  " + r["path"] for r in keep)))
    root = os.path.dirname(m["profile"]["path"])
    if a.remove and not keep and sentinel and os.path.isfile(os.path.join(root, "state", "sandbox.json")):
        shutil.rmtree(root)
        print("removed: %s" % root)
    elif a.remove:
        print("kept: %s (retained work, changed sentinel or no sandbox record)" % root)
    return 0 if sentinel else 1


def plan_forge(a):
    owner, name = a.repo.split("/", 1)
    if a.repo == guard.target(a.production)["repo"]:
        return ["repo: %s is the production repo" % a.repo]
    ops = [["gh", "repo", "create", a.repo, "--private"]]
    ops += [["gh", "label", "create", n, "-R", a.repo, "--color", c, "--description", d]
            for n, c, d in crew_repo.LABELS]
    ops += [["gh", "label", "create", n, "-R", a.repo] for n in EXTRA_LABELS]
    ops += [["gh", "api", "-X", "PUT", "repos/%s/collaborators/<%s-identity>" % (a.repo, r)] for r in IDENTITIES]
    ops += [["git", "push", "<sandbox-clone>", "HEAD:main"],  # with .github/workflows/ci.yml copied from the source
            ["gh", "issue", "create", "-R", a.repo, "--title", "M25 campaign control", "--label", "integration:run"]]
    for op in ops:
        print("plan: " + shlex.join(op))
    print("level b: blocked, owner account access (nothing was run; profile repo = %s/%s)" % (owner, name))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    for flag in ("root", "run-id", "production", "source", "release", "sentinel"):
        s.add_argument("--" + flag, required=True)
    s.add_argument("--scenario", action="append", default=[])
    t = sub.add_parser("teardown")
    t.add_argument("manifest")
    t.add_argument("--remove", action="store_true")
    p = sub.add_parser("plan-forge")
    p.add_argument("--repo", required=True)
    p.add_argument("--production", required=True)
    args = ap.parse_args(argv)
    result = {"setup": setup, "teardown": teardown, "plan-forge": plan_forge}[args.cmd](args)
    if isinstance(result, list):
        for problem in result:
            print("refused: " + problem)
        return 2
    return result


if __name__ == "__main__":
    sys.exit(main())
