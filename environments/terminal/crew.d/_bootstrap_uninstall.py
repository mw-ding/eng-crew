"""Bootstrap offboarding: pause items, stop the runtime, remove unchanged targets and archive state.

Called by mdstack bootstrap --uninstall. Keeps edited or tracked targets and all leftover worktrees.
Grok Bot routine removal requires explicit confirmation; collaborator, Project and protection stay human steps.
"""
from argparse import Namespace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from crew_shared import checkout, commands, crew_render, fetch, git, placeholder_paths


def gh(repo, *args):
    result = subprocess.run(["gh", *args, "-R", repo], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("gh %s failed: %s" % (args[0], result.stderr.strip()))
    return result.stdout


def unchanged(path, checksum):
    if path.is_symlink() or not path.is_file():
        return False
    if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
        return False
    return subprocess.run(["git", "-C", str(path.parent), "ls-files", "--error-unmatch", path.name],
                          capture_output=True).returncode != 0


def uninstall(args):
    values, problems = crew_render.resolve(args.project, args.org_profile)
    if not problems:
        problems = placeholder_paths(args, values, ("state_dir",))
    if problems:
        raise ValueError("\n".join(problems))
    repo = values["repo.owner"] + "/" + values["repo.name"]
    state = Path(values["paths.state_dir"]).absolute() / repo.replace("/", "__")
    manifest = state / "install.json"
    record = json.loads(manifest.read_text())
    if record["runtime"] != values["runtime.name"]:
        raise ValueError("runtime differs from install.json; restore the installed profile")
    # The repo directory bootstrap wrote excludes and pointers in: for FILE#<repo>, that repo's clone (#1344).
    selected = crew_render.crew_config.split_ref(args.project)[1]
    project = Path(checkout(values, args.project)) if selected else Path(args.project).absolute().parent
    result = subprocess.run(["git", "-C", str(project), "rev-parse", "--path-format=absolute",
                             "--git-path", "info/exclude"], capture_output=True, text=True)
    exclude = Path(result.stdout.strip()) if result.returncode == 0 else None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    archive = state.with_name(state.name + ".offboarded-" + stamp)
    prs = json.loads(gh(repo, "pr", "list", "--state", "open", "--limit", "1000",
                        "--json", "number,labels,body"))
    prs = [p for p in prs if any(l["name"].startswith("crew:") for l in p["labels"])
           or "crew:v1 role=builder" in p["body"]]
    issues = json.loads(gh(repo, "issue", "list", "--state", "open", "--label", "crew:ready",
                           "--limit", "1000", "--json", "number"))
    human = ["Keep or unlink the Project; revoke the collaborator and restore protection only on owner decision"]
    if record["runtime"] == "grok-bot":
        human.insert(0, "Remove every routine ID in wiring.md, newest first; mark each removed; confirm no new wakes")
    removed, kept = [], []
    for name, checksum in record["targets"].items():
        path = Path(name)
        action = "Remove" if unchanged(path, checksum) else "Keep (missing, edited or tracked)"
        print("%s: %s" % (action, path))
    for kind, items in (("pr", prs), ("issue", issues)):
        for item in items:
            print("Pause: %s #%d" % (kind, item["number"]))
    print("Stop runtime: " + record["runtime"])
    print("Archive: " + str(archive))
    for step in human:
        print("Human step: " + step)
    if args.remove_labels:
        print("Remove labels: crew:* (strips them from all issues and PRs)")
    if args.dry_run:
        print("crew bootstrap: uninstall dry-run; no changes")
        return 0
    if not args.yes and (not sys.stdin.isatty() or input("Apply this offboarding plan? [y/N] ").lower() != "y"):
        raise ValueError("confirmation required; review --dry-run, then use --yes")
    for kind, items in (("pr", prs), ("issue", issues)):
        for item in items:
            gh(repo, kind, "edit", str(item["number"]), "--add-label", "crew:hold")
    if record["runtime"] == "tmux":
        stop = Namespace(project=args.project, org_profile=args.org_profile, keep_work=True)
        if commands()["down"].run(stop):
            raise ValueError("runtime did not stop; targets and state retained")
        for run in (state / "runs").glob("*.json"):
            worktree = json.loads(run.read_text()).get("worktree")
            if worktree and Path(worktree).exists():
                base = fetch(worktree, values["repo.default_branch"])
                if (git(worktree, "status", "--porcelain", "--untracked-files=all") or
                        git(worktree, "log", "--format=%H", "HEAD", "--not", base)):
                    raise ValueError("unlanded work retained: " + worktree)
    elif not args.routines_removed:
        raise ValueError("items paused; remove routines in wiring.md, then retry with --routines-removed")
    for name, checksum in record["targets"].items():
        path = Path(name)
        if unchanged(path, checksum):
            path.unlink()
            removed.append(name)
        else:
            kept.append(name)
    link = state / "mdstack"
    if link.is_symlink() and str(link.resolve()) == record.get("source"):
        link.unlink()
        removed.append(str(link))
    else:
        kept.append(str(link))
    if exclude and exclude.exists():
        # Bootstrap owns the .crew/ entry; keep it while any run output remains in the checkout.
        lines = exclude.read_text().splitlines(True)
        names = {str(Path(p).relative_to(project)) for p in removed
                 if Path(p).is_relative_to(project)}
        names |= {"/" + name for name in names}  # bootstrap writes anchored lines
        if not (project / ".crew").exists():
            names.add(".crew/")
        exclude.write_text("".join(line for line in lines if line.strip() not in names))
    labels = []
    if args.remove_labels:
        labels = json.loads(gh(repo, "label", "list", "--limit", "1000", "--json", "name"))
        labels = [l["name"] for l in labels if l["name"].startswith("crew:")]
        for label in labels:
            gh(repo, "label", "delete", label, "--yes")
    record["offboarding"] = dict(date=stamp, removed=removed, kept=kept, removed_labels=labels,
                                 paused_prs=[p["number"] for p in prs], paused_issues=[i["number"] for i in issues],
                                 pending_human_steps=human, worktrees="kept", archive=str(archive))
    record["status"] = "offboarded"
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    state.rename(archive)
    print("crew bootstrap: offboarded; state archived at " + str(archive))
    return 0
