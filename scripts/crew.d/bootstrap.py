"""Bootstrap core: locate a pinned bundle, resolve, doctor, preview, apply and record (docs/bootstrap.md).

Usage: crew bootstrap --project FILE [--org-profile FILE] [--version vX.Y.Z] [--pre] [--dry-run] [--yes] [--dev] [--smoke] [--harness claude-code|codex]
       crew bootstrap --project FILE [--proposal FILE] [--runtime tmux|grok-bot] [--flavor thorough|standard|fast|solo]
       crew bootstrap --project FILE --uninstall [--dry-run] [--yes] [--remove-labels] [--routines-removed]

Runs doctor read-only before planning; any fail stops without writing an install. A fresh host may need
crew doctor --fix first. Apply requires confirmation. tmux keeps rendering and hooks in crew up; Grok Bot
deploys the preview to paths.live_dir; its plan notes that triage.enabled installs no Grok timer. Refuses tracked or
locally edited targets. With --harness, also installs the pack.harness registry's entries for the selected
harnesses as data (copy, pointer, Codex launch notes) under the same refusals. Records VERSION, crew.toml, install.json and the eng-crew link in per-repo state. Never starts
roles or changes credentials.
--version fetches the release from the profile's [install] source (gh for github, the default; url, mirror and git
never call gh), verifies SHA256SUMS (git: the tag against the pinned commit, then that commit's release-bundle.py
builds it), extracts beside this source and runs that bundle's bootstrap. Existing version
directories are never overwritten. Pre-releases require --pre and satisfy no pack pin; an org profile requires
its adjacent manifest.toml pin to match before installation.
After apply, validates the profile, re-renders every brief, checks path-normalized UTF-8 byte size budgets,
and checks deployed targets and doctor again.
Records failed checks in install.json. --smoke queues a real docs-only issue on a started crew, once per install;
it does not claim the asynchronous pipeline passed. Missing profiles are proposed from local git config,
confirmed (or supplied as edited TOML), and recorded once, including flavor.name.
"""
import contextlib
from argparse import Namespace
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import sys
import subprocess
import tarfile
import tempfile
import tomllib
from crew_shared import codex_trust, commands, crew_render, git, HERE, load, placeholder_paths, POINTER, tmux

crew_install = load("crew_install", "crew-install.py")

ROOT = Path(HERE).parent.resolve()


def release_tag(tag, pre):
    match = re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-rc\.(0|[1-9]\d*))?", tag)
    if not match:
        raise ValueError("bootstrap needs a release tag vX.Y.Z (or vX.Y.Z-rc.N with --pre)")
    if match[4] and not pre:
        raise ValueError("pre-release tags require --pre and satisfy no pack pin")
    return tag


def source(dev, pre=False):
    if (ROOT / ".git").exists():
        if dev:
            return git(str(ROOT), "rev-parse", "HEAD")
        tag = git(str(ROOT), "describe", "--exact-match", "--tags", "HEAD")
    else:
        tag = (ROOT / "VERSION").read_text().strip()
    return release_tag(tag, pre)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_target(path, old, doctor, project):
    parents = [p for p in path.parents if p.is_relative_to(project.parent)]
    if any(p.is_symlink() for p in (path, *parents)):
        raise ValueError("symlink target or parent: " + str(path))
    if path.exists() and old.get(str(path)) != digest(path):
        raise ValueError("target edited or unowned: " + str(path))
    root = project.parent if path.is_relative_to(project.parent) else path.parent
    if doctor.sh("git", "-C", str(root), "ls-files", "--error-unmatch", str(path.relative_to(root)))[0] == 0:
        raise ValueError("tracked target: " + str(path))


def harness_targets(harnesses, project, state, live, preview, old, doctor, notes=()):
    targets, launches = {}, []
    if "claude-code" in harnesses:
        for role in ("coordinator", "builder", "reviewer", "synthesizer"):
            relative = Path("briefs") / (role + ".md")
            if not (preview / relative).is_file():
                relative = Path("runtime") / (role + ".md")
            if not (preview / relative).is_file():
                raise ValueError("missing rendered brief: " + str(relative))
            pointer = POINTER.replace("$CREW_BRIEF", str(live / relative))
            if role == "coordinator":
                path = project.parent / ".claude/skills/crew-coordinator/SKILL.md"
            else:
                path = project.parent / (".claude/agents/crew-" + role + ".md")
            targets[path] = ('---\nname: crew-%s\ndescription: Eng-crew %s role\n---\n\n%s\n' %
                             (role, role, pointer))
        path = project.parent / ".claude/settings.local.json"
        check_target(path, old, doctor, project)
        settings = json.loads(path.read_text()) if path.exists() else {}
        targets[path] = json.dumps(commands()["up"].stop_hook_settings(settings, str(state)), indent=2) + "\n"
    if "codex" in harnesses:
        relative = Path("briefs/coordinator.md")
        if not (preview / relative).is_file():
            relative = Path("runtime/coordinator.md")
        if not (preview / relative).is_file():
            raise ValueError("missing rendered brief: " + str(relative))
        prompt = POINTER.replace("$CREW_BRIEF", str(live / relative))
        prompt += "".join(" Then read %s and follow it." % note for note in notes)
        launches.append(shlex.join(["codex", "-c", codex_trust(str(project.parent)), prompt]))
    return targets, launches


def pack_manifest(org_profile, project=None):
    """The org pack's manifest.toml path, or None without a pack."""
    if org_profile:
        return Path(org_profile).absolute().parent / "manifest.toml"
    if project:
        with open(project, "rb") as f:
            paths = tomllib.load(f).get("paths", {})
        pack = paths.get("pack") if isinstance(paths, dict) else None
        if isinstance(pack, str) and pack.strip():
            return Path(project).absolute().parent / Path(pack).expanduser() / "manifest.toml"
    return None


def pack_table(org_profile, project=None):
    """The org pack manifest's [pack] table, or None without a pack."""
    manifest = pack_manifest(org_profile, project)
    if manifest:
        with manifest.open("rb") as f:
            return tomllib.load(f).get("pack", {})
    return None


def pack_pointers(harnesses, org_profile, project):
    """The pack.harness registry entries of the selected harnesses (docs/bootstrap.md#pack-harness-pointers-design):
    {target: text}, Codex launch notes, and harness_pointers records. Sources are read as data, never run."""
    targets, notes, owned = {}, [], {}
    manifest = pack_manifest(org_profile, project)
    pack = pack_table(org_profile, project) or {}
    if not harnesses or "harness" not in pack:
        return targets, notes, owned
    problems = []
    crew_render.crew_config.validate_harness_registry(
        lambda path, reason: problems.append("%s: %s" % (path, reason)), pack["harness"], str(manifest.parent))
    if problems:
        raise ValueError("\n".join(problems))
    root = Path(os.path.realpath(manifest.parent))
    for entry in tomllib.loads((root / pack["harness"]).read_text())["pointer"]:
        if entry["harness"] not in harnesses:
            continue
        if "launch_note" in entry:
            notes.append(str(root / entry["launch_note"]))
            continue
        mode, source = entry.get("mode", "copy"), root / entry["source"]
        path = project.parent / entry["target"]
        targets[path] = source.read_bytes().decode() if mode == "copy" else "Read %s and follow it.\n" % source
        owned[str(path)] = dict(harness=entry["harness"], source=entry["source"], mode=mode)
    return targets, notes, owned


def pack_record(org_profile, project=None):
    """install.json's pack identity when the manifest declares pack.version (#878); else None, no field."""
    pack = pack_table(org_profile, project) or {}
    return {"name": pack.get("name"), "version": pack["version"]} if "version" in pack else None


def pack_pin(org_profile, tag, project=None):
    pack = pack_table(org_profile, project)
    if pack is not None:
        pin = pack.get("eng_crew_version")
        if pin != tag or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
            raise ValueError("pack.eng_crew_version must equal the stable installed tag %s; "
                             "follow docs/packs.md Version pin steps" % tag)


def install_table(values):
    """The profile's [install] keys (docs/bootstrap.md Release sources); {} is the github default."""
    return {k[len("install."):]: v for k, v in values.items() if k.startswith("install.")}


def same_source(record, install):
    """Whether install.json's transport names the profile's source kind and location; no field reads as github."""
    transport = record.get("transport") or {}
    return (transport.get("kind", "github"), transport.get("location")) == (
        install.get("source", "github"), install.get("location"))


def fetch(args):
    tag = release_tag(args.version, args.pre)
    pack_pin(args.org_profile, tag, args.project)
    install = {}
    if Path(args.project).is_file():
        values, problems = crew_render.resolve(args.project, args.org_profile)
        if problems:
            raise ValueError("\n".join(problems))
        install = install_table(values)
    name = "eng-crew-" + tag[1:]
    destination = ROOT.parent / name
    if destination.exists() or destination.is_symlink():
        raise ValueError("version directory already exists; run its bootstrap directly: " + str(destination))
    sha, sums_sha, commit = crew_install.fetch(install, tag, destination)
    print("crew bootstrap: verified %s %ssha256=%s; extracted %s" % (
        tag, "commit=%s " % commit if commit else "", sha, destination), flush=True)
    argv = [sys.executable, str(destination / "scripts/crew"), getattr(args, "cmd", "bootstrap"), "--project", args.project]
    if args.org_profile:
        argv += ["--org-profile", args.org_profile]
    for harness in args.harness or []:
        argv += ["--harness", harness]
    for option in ("proposal", "runtime", "flavor"):
        if getattr(args, option) is not None:
            argv += ["--" + option, getattr(args, option)]
    for flag in ("pre", "dry_run", "yes", "smoke"):
        if getattr(args, flag):
            argv.append("--" + flag.replace("_", "-"))
    if getattr(args, "cmd", "bootstrap") == "upgrade":
        argv += ["--wait-timeout", str(args.wait_timeout), "--timeout", str(args.timeout)]
    env = dict(os.environ, CREW_BOOTSTRAP_BUNDLE_SHA256=sha)
    transport = crew_install.transport(install, sums_sha, commit)
    if transport:
        env["CREW_BOOTSTRAP_TRANSPORT"] = json.dumps(transport)
    return subprocess.run(argv, env=env).returncode


def register(sub, name="bootstrap"):
    p = sub.add_parser(name, help="preview and install this bundle for a project")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")
    p.add_argument("--proposal", help="owner-edited TOML for a missing project file")
    p.add_argument("--runtime", choices=("tmux", "grok-bot"), help="proposed runtime; default is the bundle profile")
    p.add_argument("--flavor", choices=("thorough", "standard", "fast"),
                   help="record flavor.name in the proposal; default standard")
    p.add_argument("--version", help="fetch and run this release beside the current bundle")
    p.add_argument("--pre", action="store_true", help="allow rc tags; satisfies no pack pin")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--uninstall", action="store_true", help="pause, stop, remove owned targets and archive state")
    p.add_argument("--remove-labels", action="store_true", help="delete crew labels after stopping the runtime")
    p.add_argument("--routines-removed", action="store_true", help="confirm Grok Bot routines were removed manually")
    p.add_argument("--dev", action="store_true", help="record this clone's SHA; satisfies no version pin")
    p.add_argument("--harness", action="append", choices=("claude-code", "codex"),
                   help="install harness pointers (repeat for both; tmux render only)")
    p.add_argument("--smoke", action="store_true", help="queue a real docs-only test issue; requires a started crew")
    return p


def size_budget(rendered, values):
    """Check path-normalized role Markdown against its byte budget; wiring is not loaded."""
    failed = False
    for path in sorted(Path(rendered).rglob("*.md")):
        role = path.stem.split("-")[0]
        if role not in crew_render.ROLES:
            continue
        size = len(path.read_bytes())
        budget = values["size_budget." + role]
        if size > budget:
            print("%s: %d path-normalized UTF-8 bytes exceeds %s budget %d bytes" %
                  (path.relative_to(rendered), size, role, budget))
            failed = True
    return int(failed)


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
            values, _ = crew_render.resolve(str(project), org)
            with tempfile.TemporaryDirectory(prefix="crew-size-budget-") as normalized:
                normalized_argv = ["--project", str(project), "--out", normalized] + (
                    ["--org-profile", org] if org else [])
                check("size_budget", lambda: crew_render.main(normalized_argv, normalize_paths=True) or
                      size_budget(normalized, values))
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
        if args.uninstall:
            from crew_shared import load
            return load("bootstrap_uninstall", "crew.d/_bootstrap_uninstall.py").uninstall(args)
        if args.remove_labels or args.routines_removed:
            raise ValueError("--remove-labels and --routines-removed require --uninstall")
        return bootstrap(args)
    except (OSError, ValueError, RuntimeError, tarfile.TarError) as e:
        print("crew bootstrap: %s" % e, file=sys.stderr)
        return 1


def propose_project(args, project):
    if args.proposal:
        text = Path(args.proposal).read_text()
    else:
        remote = git(str(project.parent), "config", "--local", "--get", "remote.origin.url")
        match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([\w.-]+)/([\w.-]+?)(?:\.git)?/?", remote)
        if not match:
            raise ValueError("local origin is not a recognized GitHub URL; supply --proposal with your binding")
        owner, repo = match.groups()
        runtime = args.runtime or tomllib.loads((ROOT / "profiles/default.toml").read_text())["runtime"]["name"]
        runtime_text = "name = %s\n" % json.dumps(runtime)
        if runtime == "tmux":
            runtime_text = (ROOT / "profiles/tmux.toml").read_text().split("[runtime]\n", 1)[1].split("[backends.", 1)[0]
        text = '[repo]\nowner = %s\nname = %s\n\n[runtime]\n%s' % (
            json.dumps(owner), json.dumps(repo), runtime_text)
        for concern in crew_render.crew_config.OPERATIONS:
            text += '\n[backends.%s]\nname = "github"\n' % concern
            if runtime == "tmux" and concern == "review":
                text += 'capabilities = { post-verdict = "emulated (COMMENT-review verdict + recorded owner merge-ok)" }\n'
    if "flavor" not in tomllib.loads(text):
        text += '\n[flavor]\nname = %s\n' % json.dumps(args.flavor or "standard")
    print("Project proposal: %s\n%s" % (project, text), end="" if text.endswith("\n") else "\n")
    print("Review identities and paths inherited from the profile layers; edit with --proposal FILE.")
    if args.dry_run:
        print("crew bootstrap: dry-run; no profile or install written")
        return False
    if not args.yes:
        if not sys.stdin.isatty():
            raise ValueError("profile confirmation required; use --proposal FILE to edit, then --yes")
        answer = input("Record proposal? [y/N or edited TOML path] ").strip()
        if answer.lower() != "y":
            if answer.lower() in ("", "n"):
                raise ValueError("profile confirmation required")
            args.proposal = answer
            return propose_project(args, project)
    with project.open("x") as f:
        f.write(text)
    print("crew bootstrap: recorded profile " + str(project))
    return True


def bootstrap(args):
    if args.version:
        if args.dev:
            raise ValueError("--version and --dev cannot be combined")
        return fetch(args)
    tag = source(args.dev, args.pre)
    project = Path(args.project).absolute()
    if not project.is_file():
        if not propose_project(args, project):
            return 0
    pack_pin(args.org_profile, tag, args.project)
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
    harnesses = args.harness if args.harness is not None else previous.get("harnesses", [])
    if harnesses and not tmux:
        raise ValueError("harness pointers need tmux role briefs; a session binding is not implemented")
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
        registry, notes, owned = pack_pointers(harnesses, args.org_profile, project)
        pointers, launches = harness_targets(harnesses, project, state, live, preview, old, doctor, notes)
        refused = []
        for path in registry:
            try:
                check_target(path, old, doctor, project)
            except ValueError as e:
                refused.append(str(e))
        if refused:
            raise ValueError("\n".join(refused))
        pointers.update(registry)
        targets.update(pointers)
        if harnesses:
            targets.update(rendered)
        if not tmux:
            targets.update(rendered)
            existing = {p for p in live.rglob("*") if p.is_file() or p.is_symlink()}
            if existing - targets.keys():
                raise ValueError("live copy has extra files; reconcile before bootstrap")
        for path, text in targets.items():
            check_target(path, old, doctor, project)
        excludes = [".crew/"] if tmux else []
        excludes += ["/" + str(path.relative_to(project.parent)) for path in pointers]
        exclude = None
        if harnesses:
            exclude = Path(git(str(project.parent), "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"))
            if exclude.is_symlink() or exclude.parent.is_symlink():
                raise ValueError("symlink exclude or parent: " + str(exclude))
        for path, text in {**targets, **rendered}.items():
            before = path.read_text() if path.exists() else ""
            print("".join(difflib.unified_diff(before.splitlines(True), text.splitlines(True),
                                             fromfile=str(path), tofile=str(path) + " (planned)")), end="")
        print("Plan: %s (%s); link %s -> %s" % (tag, values["runtime.name"], link, ROOT))
        if tmux and not harnesses:
            print("Render preview: %d files; crew up deploys render and hooks" %
                  sum(p.is_file() for p in preview.rglob("*")))
        for line in excludes:
            print("Repo operation: add %s to .git/info/exclude" % line)
        for launch in launches:
            print("Codex launch (from %s): %s" % (project.parent, launch))
        if not tmux and values.get("triage.enabled"):
            print("Triage: triage.enabled installs no Grok timer; triage stays coordinator dispositions")
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
        if excludes:
            if exclude is None:
                exclude = Path(git(str(project.parent), "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"))
            exclude.parent.mkdir(parents=True, exist_ok=True)
            text = exclude.read_text() if exclude.exists() else ""
            missing = [line for line in excludes if line not in text.splitlines()]
            if missing:
                exclude.write_text(text + ("\n" if text and not text.endswith("\n") else "") +
                                   "\n".join(missing) + "\n")
        for path, text in targets.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        if link.is_symlink():
            link.unlink()
        link.symlink_to(ROOT, target_is_directory=True)
        bundle_sha = os.environ.get("CREW_BOOTSTRAP_BUNDLE_SHA256")
        if not bundle_sha and previous.get("source") == str(ROOT):
            bundle_sha = previous.get("bundle_sha256")
        record = dict(tag=tag, source=str(ROOT), bundle_sha256=bundle_sha, runtime=values["runtime.name"],
                      targets={**old, **{str(p): digest(p) for p in targets}}, harnesses=harnesses,
                      launches=launches, pending_human_steps=pending, status="installed")
        owned = {**{path: entry for path, entry in previous.get("harness_pointers", {}).items()
                    if entry["harness"] not in harnesses}, **owned}
        if owned:
            record["harness_pointers"] = owned
        transport = os.environ.get("CREW_BOOTSTRAP_TRANSPORT")
        transport = json.loads(transport) if transport else (
            previous.get("transport") if previous.get("source") == str(ROOT) else None)
        if transport:
            record["transport"] = transport
        pack = pack_record(args.org_profile, args.project)
        if pack:
            record["pack"] = pack
        if "smoke" in previous:
            record["smoke"] = previous["smoke"]
        manifest.write_text(json.dumps(record, indent=2) + "\n")
    if tmux and not harnesses and getattr(args, "cmd", "bootstrap") == "upgrade":
        for path, text in rendered.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
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
