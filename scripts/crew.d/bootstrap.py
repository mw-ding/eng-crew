"""Bootstrap core: locate a pinned bundle, resolve, doctor, preview, apply and record (docs/bootstrap.md).

Usage: crew bootstrap --project FILE [--org-profile FILE] [--dry-run] [--yes] [--dev] [--smoke]

Runs doctor read-only before planning; any fail stops without writing an install. A fresh host may need
crew doctor --fix first. Apply requires confirmation. tmux keeps rendering and hooks in crew up; Grok Bot
deploys the preview to paths.live_dir. Refuses tracked or locally edited targets. Records VERSION,
crew.toml, install.json and the eng-crew link in per-repo state. Never starts roles or changes credentials.
After apply, validates the profile, re-renders every brief and checks deployed targets and doctor again.
Records failed checks in install.json. --smoke queues a real docs-only issue on a started crew, once per install;
it does not claim the asynchronous pipeline passed. Bundle fetching, proposals, pointers and size budgets are separate.
"""
import contextlib
from argparse import Namespace
import difflib
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import subprocess
import tempfile
from crew_shared import commands, crew_render, git, HERE, placeholder_paths, tmux

ROOT = Path(HERE).parent.resolve()


def source(dev):
    if (ROOT / ".git").exists():
        if dev:
            return git(str(ROOT), "rev-parse", "HEAD")
        tag = git(str(ROOT), "describe", "--exact-match", "--tags", "HEAD")
    else:
        tag = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("bootstrap needs a stable release tag; use --dev for a development clone")
    return tag


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register(sub):
    p = sub.add_parser("bootstrap", help="preview and install this bundle for a project")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--dev", action="store_true", help="record this clone's SHA; satisfies no version pin")
    p.add_argument("--smoke", action="store_true", help="queue a real docs-only test issue; requires a started crew")


def self_test(project, org, live, record, doctor):
    checks = {}

    def check(name, action):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(out):
            try:
                code = action()
            except (OSError, ValueError, RuntimeError) as e:
                print(e)
                code = 1
        checks[name] = "fail" if code else "ok"
        print("Self-test: %s %s" % (name, checks[name]))
        if code:
            print(out.getvalue(), end="")

    profile_argv = ["resolve", "--project", str(project)] + (["--org-profile", org] if org else [])
    check("profile", lambda: crew_render.crew_config.main(profile_argv))
    with tempfile.TemporaryDirectory(prefix="crew-self-test-") as tmp:
        argv = ["--project", str(project), "--out", tmp] + (["--org-profile", org] if org else [])
        check("render", lambda: crew_render.main(argv))
        if checks["render"] == "ok":
            roles = ["coordinator", "builder", "reviewer", "synthesizer"]
            names = roles if record["runtime"] == "tmux" else [
                "coordinator-after-merge", "builder-b1", "reviewer-validator", "synthesizer"]
            check("briefs", lambda: int(any(
                not (Path(tmp) / "briefs" / (role + ".md")).is_file() and
                not (Path(tmp) / "runtime" / (name + ".md")).is_file()
                for role, name in zip(roles, names))))
            if live.is_dir():
                expected = {p.relative_to(tmp): p.read_bytes() for p in Path(tmp).rglob("*") if p.is_file()}
                check("deploy", lambda: int(expected != {
                    p.relative_to(live): p.read_bytes() for p in live.rglob("*") if p.is_file()}))
            elif record["runtime"] == "tmux":
                checks["deploy"] = "pending crew up"
                print("Self-test: deploy pending crew up")
            else:
                checks["deploy"] = "fail"
                print("Self-test: deploy fail (live directory missing)")
    check("targets", lambda: int(any(digest(Path(p)) != sha for p, sha in record["targets"].items())))
    check("doctor", lambda: doctor.run(Namespace(project=str(project), org_profile=org, fix=False,
                                               dry_run=False, milestone=None)))
    return checks


def smoke(values, record, manifest):
    if record.get("smoke", {}).get("issue"):
        print("Smoke: already queued " + record["smoke"]["issue"])
        return
    if values["runtime.name"] == "tmux":
        session = values.get("runtime.options.session") or "crew-%s-%s" % (values["repo.owner"], values["repo.name"])
        if not tmux.has_session(session):
            raise ValueError("smoke requires a started crew; run crew up first, then repeat --smoke")
    body = """## Goal

Prove the crew pipeline with a docs-only no-op change; no product behaviour changes.

## Acceptance criteria

1. docs/crew-smoke-test.md has a heading and one sentence explaining this test.
2. Required checks are green at the PR head.
3. The PR body has Acceptance Evidence with one row per criterion.
4. Only docs/crew-smoke-test.md and the required changelog fragment change.

## Out of scope

Product code, workflows, labels and settings. Use eng-backend, trivial tier.
"""
    r = subprocess.run(["gh", "issue", "create", "-R", values["repo.owner"] + "/" + values["repo.name"],
                        "--title", "crew smoke test: add docs/crew-smoke-test.md", "--body-file", "-",
                        "--label", "crew:ready", "--assignee", values["identities.builder.gh_user"]],
                       input=body, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("smoke issue creation failed: " + r.stderr.strip())
    record["smoke"] = dict(issue=r.stdout.strip(), status="queued")
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    print("Smoke: queued " + record["smoke"]["issue"] + "; pipeline result pending")


def run(args):
    try:
        return bootstrap(args)
    except (OSError, ValueError, RuntimeError) as e:
        print("crew bootstrap: %s" % e, file=sys.stderr)
        return 1


def bootstrap(args):
    tag = source(args.dev)
    project = Path(args.project).absolute()
    if not project.is_file():
        raise ValueError("project file missing; provide crew.toml (proposal support is separate)")
    values, problems = crew_render.resolve(str(project), args.org_profile)
    if problems:
        raise ValueError("\n".join(problems))
    tmux = values["runtime.name"] == "tmux"
    keys = ("state_dir", "worktree_root", "toolchain_bin", "eng_crew" if tmux else "live_dir")
    problems = placeholder_paths(args, values, keys)
    if problems:
        raise ValueError("\n".join(problems))
    state = Path(values["paths.state_dir"]).absolute() / (values["repo.owner"] + "__" + values["repo.name"])
    doctor = commands()["doctor"]
    with contextlib.redirect_stdout(io.StringIO()) as report:
        code = doctor.run(Namespace(project=str(project), org_profile=args.org_profile, fix=False,
                                    dry_run=False, milestone=None))
    print(report.getvalue(), end="")
    if code:
        return code
    human = report.getvalue().partition("Steps only a person can take:\n")[2].splitlines()
    pending = [line.removeprefix("- ") for line in human]
    pending += (["Run crew up --project " + str(project)] if tmux else
                ["Create the routines from the rendered files (docs/bootstrap.md Q4)"])
    manifest = state / "install.json"
    previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    old = previous.get("targets", {})
    link = state / "eng-crew"
    if tmux and Path(values["paths.eng_crew"]).absolute() != link:
        raise ValueError("paths.eng_crew must name the install link: " + str(link))
    if link.exists() or link.is_symlink():
        if not link.is_symlink() or str(link.resolve()) != previous.get("source"):
            raise ValueError("target edited or unowned: " + str(link))
    with tempfile.TemporaryDirectory(prefix="crew-bootstrap-") as tmp:
        preview = Path(tmp)
        argv = ["--project", str(project), "--out", tmp]
        if args.org_profile:
            argv += ["--org-profile", args.org_profile]
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(out):
            code = crew_render.main(argv)
        if code:
            raise ValueError(out.getvalue())
        live = Path(values["paths.live_dir"]).absolute() if not tmux else state / "render"
        targets = {state / "VERSION": tag + "\n", state / "crew.toml": project.read_text()}
        rendered = {live / p.relative_to(preview): p.read_text() for p in preview.rglob("*") if p.is_file()}
        if not tmux:
            targets.update(rendered)
            existing = {p for p in live.rglob("*") if p.is_file() or p.is_symlink()}
            if existing - targets.keys():
                raise ValueError("live copy has extra files; reconcile before bootstrap")
        for path, text in targets.items():
            if path.is_symlink() or (path.exists() and old.get(str(path)) != digest(path)):
                raise ValueError("target edited or unowned: " + str(path))
            tracked = doctor.sh("git", "-C", str(path.parent), "ls-files", "--error-unmatch", path.name)[0] == 0
            if tracked:
                raise ValueError("tracked target: " + str(path))
        for path, text in {**targets, **rendered}.items():
            before = path.read_text() if path.exists() else ""
            print("".join(difflib.unified_diff(before.splitlines(True), text.splitlines(True),
                                             fromfile=str(path), tofile=str(path) + " (planned)")), end="")
        print("Plan: %s (%s); link %s -> %s" % (tag, values["runtime.name"], link, ROOT))
        if tmux:
            print("Render preview: %d files; crew up deploys render and hooks" %
                  sum(p.is_file() for p in preview.rglob("*")))
            print("Repo operation: add .crew/ to .git/info/exclude")
        for step in pending:
            print("Human step: " + step)
        if args.smoke:
            print("Plan: queue docs-only smoke issue (crew must be started; pipeline result remains pending)")
        if args.dry_run:
            print("crew bootstrap: dry-run; no install written")
            return 0
        if not args.yes and (not sys.stdin.isatty() or input("Apply this plan? [y/N] ").lower() != "y"):
            raise ValueError("confirmation required; review --dry-run, then use --yes")
        if doctor.run(Namespace(project=str(project), org_profile=args.org_profile, fix=True,
                                dry_run=False, milestone=None)):
            return 1
        if tmux:
            exclude = Path(git(str(project.parent), "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"))
            exclude.parent.mkdir(parents=True, exist_ok=True)
            text = exclude.read_text() if exclude.exists() else ""
            if ".crew/" not in text.splitlines():
                exclude.write_text(text + ("\n" if text and not text.endswith("\n") else "") + ".crew/\n")
        for path, text in targets.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        if link.is_symlink():
            link.unlink()
        link.symlink_to(ROOT, target_is_directory=True)
        record = dict(tag=tag, source=str(ROOT), bundle_sha256=None, runtime=values["runtime.name"],
                      targets={str(p): digest(p) for p in targets}, pending_human_steps=pending, status="installed")
        if "smoke" in previous:
            record["smoke"] = previous["smoke"]
        manifest.write_text(json.dumps(record, indent=2) + "\n")
    record["self_test"] = self_test(project, args.org_profile, live, record, doctor)
    failed = [name for name, status in record["self_test"].items() if status == "fail"]
    record["status"] = "failed" if failed else "installed"
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    if failed:
        raise ValueError("self-test failed: " + ", ".join(failed))
    print("crew bootstrap: installed " + str(manifest))
    if args.smoke:
        try:
            smoke(values, record, manifest)
        except (OSError, ValueError, RuntimeError):
            record["status"] = "failed"
            record["self_test"]["smoke"] = "fail"
            manifest.write_text(json.dumps(record, indent=2) + "\n")
            raise
    return 0
