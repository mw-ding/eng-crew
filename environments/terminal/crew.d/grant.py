"""`mdstack grant prune` previews finished grants and archives them before an attended owner edit (#1774).

Usage: mdstack grant prune [--project FILE] [--org-profile FILE] [--dry-run]

Application requires an owner terminal, explicit `prune` confirmation and stopped writers. Role shells and pipes
cannot apply. Only a project-owned, single-line string in [runtime.options] is writable; inherited/team/inline
layouts are kept. Source records identify one local decision-log issue; unsupported backends are kept.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import tomllib
from crew_shared import commands, crew_render, load, profile, require_ownership, runs, tmux

scope = load("crew_grant_scope", "environments/terminal/crew.d/_grant_scope.py")
KEY = "runtime.options.merge_grant"
STRING = re.compile(r'''(?m)^(merge_grant[ \t]*=[ \t]*)("(?:[^"\\\r\n]|\\.)*"|'[^'\r\n]*')([ \t]*(?:#[^\r\n]*)?\r?$)''')


def register(sub):
    p = sub.add_parser("grant")
    p.add_argument("action", choices=["prune"])
    p.add_argument("--project")
    p.add_argument("--org-profile")
    p.add_argument("--dry-run", action="store_true")


def selected(args):
    _, provenance, problems, _ = crew_render.crew_config.resolve_profile(args.project, args.org_profile)
    if problems:
        raise ValueError("; ".join(problems))
    if "#" in args.project or provenance.get(KEY) != "project":
        raise ValueError("inherited/team grant: no writable project-owned value")
    path = Path(args.project)
    if path.is_symlink():
        raise ValueError("unsupported symlink profile")
    original = path.read_bytes()
    text = original.decode("utf-8")
    parsed = tomllib.loads(text)
    matches = list(STRING.finditer(text))
    if len(matches) != 1 or re.findall(r"(?m)^\[([^\r\n]+)\][ \t]*(?:#[^\r\n]*)?\r?$", text[:matches[0].start()])[-1:] != [
            "runtime.options"]:
        raise ValueError("unsupported merge_grant layout: use one single-line string in [runtime.options]")
    value = parsed["runtime"]["options"]["merge_grant"]
    if tomllib.loads("merge_grant = " + matches[0][2])["merge_grant"] != value:
        raise ValueError("unsupported merge_grant layout")
    return original, text, matches[0], value


def preview(args):
    values, _, state = profile(args)
    try:
        original, _, _, value = selected(args)
        rows = scope.classify(value, values)
    except (OSError, ValueError, KeyError, UnicodeError) as e:
        print("crew: grant: keeping everything: " + str(e))
        return None
    print("crew: grant preview (whole clauses):")
    for row in rows:
        print("%s: %s\n  %s" % ("remove" if row["remove"] else "keep", row["clause"], row["reason"]))
        for link in row["links"]:
            print("  " + link)
    return (original, rows, values, state)


def attended(state):
    role = any(os.environ.get(k) for k in ("CREW_ROLE", "CREW_ID", "CREW_BRIEF"))
    cwd = Path.cwd().resolve()
    role |= any(rec.get("worktree") and Path(rec["worktree"]).resolve() in (cwd, *cwd.parents)
                for _, rec in runs(state))
    return not role and sys.stdin.isatty() and sys.stdout.isatty()


def confirm(plan):
    if not attended(plan[3]):
        raise ValueError("application requires an attended owner shell; role/noninteractive use refused")
    if not any(row["remove"] for row in plan[1]):
        return False
    try:
        return input("Type prune to archive and remove these clauses (anything else keeps them): ") == "prune"
    except EOFError:
        return False


def stopped(values, state):
    down = commands()["down"]
    if down.land_locked(state) or tmux.has_session(values.get("runtime.options.session") or
                                                  "crew-%s-%s" % (values["repo.owner"], values["repo.name"])) or \
            down.watcher(state) or any(True for _ in runs(state)):
        raise ValueError("writers/land lock still present; use owner-run down first")


def archive(values, rows, before, after):
    removed = [r for r in rows if r["remove"]]
    logs = {r["log"] for r in removed}
    if len(logs) != 1:
        raise ValueError("ambiguous decision log; nothing changed")
    user = scope.api("user")["login"]
    if user not in values["identities.owners"]:
        raise ValueError("archive requires a configured owner identity")
    body = "[Owner/grant-prune] archive attempt (history only; supplies no authority)\n\n"
    body += "Profile bytes SHA-256: %s → %s\n\n" % (hashlib.sha256(before).hexdigest(), hashlib.sha256(after).hexdigest())
    for row in removed:
        fence = "`" * max(3, max((len(m) + 1 for m in re.findall(r"`+", row["clause"])), default=3))
        body += "%stext\n%s\n%s\n\nFinished facts: %s\n%s\n\n" % (
            fence, row["clause"], fence, row["reason"], "\n".join(row["links"]))
    body += "— %s (Owner) · mdstack grant prune" % user
    endpoint = "repos/%s/%s/issues/%s/comments" % (values["repo.owner"], values["repo.name"], next(iter(logs)))

    def reconciled():
        pages = scope.api(endpoint, "--paginate", "--slurp")
        found = [c for page in pages for c in page if c["body"] == body and c["user"]["login"] == user]
        if len(found) > 1:
            raise ValueError("archive reconciliation ambiguous; inspect decision log")
        return found[0]["html_url"] if found else None

    link = reconciled()  # retries reconcile this identical attempt before posting
    if link:
        return link
    try:
        posted = scope.api(endpoint, "--input", "-", body=json.dumps({"body": body}))
        if posted["body"] == body and posted["user"]["login"] == user:
            return posted["html_url"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    link = reconciled()  # uncertain post: read back, never blindly post again
    if not link:
        raise ValueError("archive post failed/unconfirmed; profile unchanged")
    return link


def apply(args, plan):
    values, _, state = profile(args)
    if not require_ownership(values, "write"):
        return 1
    stopped(values, state)
    original, text, match, value = selected(args)
    rows = scope.classify(value, values)
    if original != plan[0] or rows != plan[1] or values != plan[2]:
        raise ValueError("profile or scope/source facts changed; preview again")
    kept = [r["clause"] for r in rows if not r["remove"]]
    new_value = ";".join(kept) if kept else "none"
    after = (text[:match.start(2)] + json.dumps(new_value, ensure_ascii=False) + text[match.end(2):]).encode("utf-8")
    prior = tomllib.loads(text)
    prior["runtime"]["options"]["merge_grant"] = new_value
    if tomllib.loads(after.decode("utf-8")) != prior:
        raise ValueError("refusing any change beyond merge_grant")
    staging = None
    try:
        with tempfile.NamedTemporaryFile(dir=Path(args.project).parent, prefix=".grant-prune-", suffix=".toml",
                                         delete=False) as f:
            staging = f.name
            f.write(after)
            f.flush()
            os.fsync(f.fileno())
        proposed, problems = crew_render.resolve(staging, args.org_profile)
        if problems or proposed != dict(values, **{KEY: new_value}):
            raise ValueError("pruned profile invalid or other effective values changed: " + "; ".join(problems))
        os.chmod(staging, os.stat(args.project).st_mode & 0o777)
        backup_dir = Path(state) / "runs"
        backup_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=backup_dir, prefix="grant-backup-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-",
                                         suffix=".toml.bak", delete=False) as f:
            f.write(original)
            f.flush()
            os.fsync(f.fileno())
            print("crew: grant backup: " + f.name)
        if not require_ownership(values, "write"):
            return 1
        link = archive(values, rows, original, after)
        if not require_ownership(values, "write"):
            return 1
        if Path(args.project).read_bytes() != original:
            raise ValueError("profile changed after archive; archive remains history, profile not replaced")
        current, _, _ = profile(args)
        stopped(current, state)
        if current != values or scope.classify(value, current) != rows:
            raise ValueError("scope/source/profile facts changed after archive; profile not replaced")
        if not require_ownership(current, "write"):
            return 1
        if Path(args.project).read_bytes() != original:
            raise ValueError("profile changed before replacement; profile not replaced")
        os.replace(staging, args.project)
        print("crew: grant pruned; archive: " + link)
        return 0
    finally:
        if staging and os.path.exists(staging):
            os.unlink(staging)


def run(args):
    plan = preview(args)
    if args.dry_run:
        return 0
    try:
        if plan is None:
            raise ValueError("unsupported or unreadable grant; nothing changed")
        if not confirm(plan):
            print("crew: grant kept")
            return 0
        return apply(args, plan)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print("crew: grant refused: " + str(e))
        return 1
