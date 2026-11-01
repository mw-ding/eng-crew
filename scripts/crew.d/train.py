"""crew train build PR... | land N | bisect N --project FILE [--org-profile FILE]"""
import glob
import json
import os
import re
import subprocess
import sys
import time
from crew_shared import commands, fetch, git, profile


# Merge train (tmux.md crew train, #321): build crew/train-<n> = fetched main + each PR head as --no-ff merges, run the
# local checks, push it with a draft PR so CI runs once on the combined result, then land each member at its tested
# head with no catch-up between them. Machine-readable lines: member, dropped, landed, stopped, train.
def train_path(state, n):
    return os.path.join(state, "trains", "train-%d.json" % n)


def train_save(state, rec):
    os.makedirs(os.path.join(state, "trains"), exist_ok=True)
    with open(train_path(state, rec["n"]), "w") as f:
        json.dump(rec, f, indent=2)


def train_number(repo, state):
    """1 + the highest train number on the remote or in the state dir, so no train branch is ever reused."""
    remote = git(repo, "ls-remote", "--heads", "origin", "refs/heads/crew/train-*")
    seen = [int(m) for m in re.findall(r"refs/heads/crew/train-(\d+)$", remote, re.M)]
    seen += [int(re.search(r"(\d+)\.json$", p).group(1)) for p in glob.glob(os.path.join(state, "trains", "*.json"))]
    return max(seen, default=0) + 1


def train_local_checks(wt):
    """check-repo, then every scripts/test-*.py the train's tree has; (failing script, last output lines) or None."""
    scripts = [s for s in ["scripts/check-repo.py"] if os.path.exists(os.path.join(wt, s))]
    scripts += sorted(os.path.relpath(p, wt) for p in glob.glob(os.path.join(wt, "scripts", "test-*.py")))
    for s in scripts:
        r = subprocess.run([sys.executable, s], cwd=wt, capture_output=True, text=True)
        if r.returncode:
            return s, (r.stdout + r.stderr).strip().splitlines()[-5:]
    return ("none" if not scripts else None), []


def train_wait_ci(slug, pr, args):
    """pass | fail | timeout for the train PR's checks, and their CI run links. Sleeps --grace first: checks register
    a few seconds after the PR opens and `gh pr checks` exits non-zero until they do, so no checks yet is pending."""
    time.sleep(args.grace)
    deadline = time.monotonic() + args.timeout
    while True:
        r = subprocess.run(["gh", "pr", "checks", str(pr), "-R", slug, "--json", "name,bucket,link"],
                           capture_output=True, text=True)
        try:
            checks = json.loads(r.stdout or "[]")
        except ValueError:
            checks = []
        buckets = {c.get("bucket") for c in checks}
        if checks and "pending" not in buckets:
            links = list(dict.fromkeys(re.sub(r"/job/\d+$", "", c["link"]) for c in checks if c.get("link")))
            return ("pass" if buckets <= {"pass", "skipping"} else "fail"), links
        if time.monotonic() >= deadline:
            return "timeout", []
        time.sleep(args.interval)


def train_close(repo, slug, rec):
    """Close the train PR without a comment and delete the train branch; (closed, deleted)."""
    closed = subprocess.run(["gh", "pr", "close", str(rec["pr"]), "-R", slug], capture_output=True).returncode == 0
    return closed, subprocess.run(["git", "-C", repo, "push", "-q", "origin", "--delete", rec["branch"]],
                                  capture_output=True).returncode == 0


def train_build(args, values, state, repo, slug):
    n, main = train_number(repo, state), values["repo.default_branch"]
    base = fetch(repo, main)
    wt = os.path.join(os.path.abspath(values["paths.worktree_root"]), "train-%d-%s" % (n, base[:7]))
    if os.path.lexists(wt):
        print("crew: refusing train: %s exists" % wt)
        return 1
    rec = {"n": n, "branch": "crew/train-%d" % n, "base": base, "sha": base, "members": [], "dropped": [],
           "pr": None, "local": "none", "ci": "none", "ci_links": []}
    os.makedirs(os.path.dirname(wt), exist_ok=True)
    git(repo, "worktree", "add", "-q", "--detach", wt, base)
    try:
        for pr in args.items:
            try:
                head = fetch(wt, "pull/%d/head" % pr)
            except RuntimeError:
                rec["dropped"].append({"pr": pr, "reason": "no-head"})
                continue
            r = subprocess.run(["git", "-C", wt, "merge", "-q", "--no-ff", "--no-edit", "-m",
                                "crew train %d: merge #%d @ %s" % (n, pr, head[:7]), head], capture_output=True)
            if r.returncode:  # a conflict drops the PR; its builder resolves it (synthesizer brief)
                subprocess.run(["git", "-C", wt, "merge", "--abort"], capture_output=True)
                rec["dropped"].append({"pr": pr, "reason": "conflict"})
                continue
            rec["members"].append({"pr": pr, "head": head, "step": git(wt, "rev-parse", "HEAD")})
        rec["sha"] = git(wt, "rev-parse", "HEAD")
        failed, tail = train_local_checks(wt) if rec["members"] else ("none", [])
        rec["local"] = "pass" if failed is None else "none" if failed == "none" else "fail " + failed
        if rec["members"] and failed in (None, "none"):
            git(wt, "push", "-q", "origin", "HEAD:refs/heads/" + rec["branch"])
            body = ("Merge train %d: CI on the combined result only. Never merge this PR; `crew train land %d` lands "
                    "the members and closes it.\n\n- Base: `%s` %s\n- Train SHA: %s\n- Members, in landing order: %s\n"
                    "- Dropped (conflict): %s\n" % (
                        n, n, main, base, rec["sha"], ", ".join("#%d @ %s" % (m["pr"], m["head"][:7])
                                                                for m in rec["members"]),
                        ", ".join("#%d" % d["pr"] for d in rec["dropped"]) or "none"))
            r = subprocess.run(["gh", "pr", "create", "-R", slug, "--draft", "--base", main, "--head", rec["branch"],
                                "--title", "crew train %d (CI only, do not merge)" % n, "--body", body],
                               capture_output=True, text=True)
            found = re.search(r"/pull/(\d+)", r.stdout)
            if not found:
                print("crew: gh pr create failed: %s" % r.stderr.strip())
                subprocess.run(["git", "-C", repo, "push", "-q", "origin", "--delete", rec["branch"]],
                               capture_output=True)
            else:
                rec["pr"] = int(found.group(1))
                train_save(state, rec)
                rec["ci"], rec["ci_links"] = train_wait_ci(slug, rec["pr"], args)
                if rec["ci"] != "pass":  # a red train never lands; its check links stay readable after the close
                    train_close(repo, slug, rec)
        for line in tail:
            print("crew: %s: %s" % (failed, line))
    finally:
        subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt], capture_output=True)
        subprocess.run(["git", "-C", repo, "worktree", "prune"], capture_output=True)
    train_save(state, rec)
    for m in rec["members"]:
        print("member pr=%d head=%s step=%s" % (m["pr"], m["head"], m["step"]))
    for d in rec["dropped"]:
        print("dropped pr=%d reason=%s" % (d["pr"], d["reason"]))
    for link in rec["ci_links"]:
        print("ci-link %s" % link)
    print("train n=%d branch=%s base=%s sha=%s pr=%s local=%s ci=%s" % (
        n, rec["branch"], base, rec["sha"], rec["pr"] or "none", rec["local"].replace(" ", ":"), rec["ci"]))
    return 0 if rec["ci"] == "pass" else 1


def train_merge_record(values, rec, i, m, merge, permission):
    return ("[%s/merge] squashed @ %s → %s (crew train %d)\n\n"
            "- Train: `%s` @ %s (base `%s` %s), member %d of %d, train PR #%d (draft, CI only); CI green: %s. "
            "Tested with main: `%s` held exactly the train's state before this member, so no catch-up.\n"
            "- Approval at head: `pass=verdict verdict=pass` at %s.\n- Permission: %s.\n\n"
            "<!-- crew:v1 role=synthesizer pass=merge pr=%d sha=%s round=n/a verdict=n/a -->\n" % (
                values.get("identities.synthesizer.name", "Sam"), m["head"][:7], merge[:7], rec["n"], rec["branch"],
                rec["sha"], values["repo.default_branch"], rec["base"], i, len(rec["members"]), rec["pr"],
                ", ".join(rec["ci_links"]) or "all checks", values["repo.default_branch"], m["head"][:7], permission,
                m["pr"], m["head"]))


def train_land(args, values, state, repo, slug):
    n, main, poll = args.items[0], values["repo.default_branch"], commands()["poll"]
    try:
        with open(train_path(state, n)) as f:
            rec = json.load(f)
    except FileNotFoundError:
        print("crew: no train %d (run crew train build)" % n)
        return 1
    if rec["ci"] != "pass":
        print("crew: train %d CI is %s, not pass; nothing landed" % (n, rec["ci"]))
        return 1
    grant, expected, landed, stop = values.get("runtime.options.merge_grant", "none"), rec["base"], [], None
    try:
        if fetch(repo, rec["branch"]) != rec["sha"]:
            stop = (rec["members"][0]["pr"], "train branch moved")
    except RuntimeError as e:
        stop = (rec["members"][0]["pr"], str(e))
    for i, m in enumerate(rec["members"] if not stop else [], 1):
        try:
            cur = fetch(repo, main)
            view = poll.gh_json("pr", "view", str(m["pr"]), "-R", slug, "--json", poll.PR_FIELDS)
            marks = [dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
                     for r in view["reviews"] for line in poll.CREW_LINE.findall(r["body"])]
            merge_ok = any(k.get("pass") == "steer" and k.get("cmd") == "merge-ok" and k.get("sha") == m["head"]
                           for k in marks)
            why = ("main moved: %s, train base %s" % (cur, expected) if cur != expected else
                   "head changed: %s, tested %s" % (view["headRefOid"], m["head"]) if view["headRefOid"] != m["head"]
                   else "no approval verdict at head" if poll.pr_snapshot(view)["verdict"] != "pass" else
                   "no merge permission: no merge-ok at head and merge_grant is none"
                   if not merge_ok and grant == "none" else None)
            if not why:
                r = subprocess.run(["gh", "pr", "merge", str(m["pr"]), "-R", slug, "--squash",
                                    "--match-head-commit", m["head"]], capture_output=True, text=True)
                why = "merge refused: " + r.stderr.strip() if r.returncode else None
            if not why:  # landed: the squash must sit on the tested state and reproduce the train step's tree
                new = fetch(repo, main)
                landed.append({"pr": m["pr"], "head": m["head"], "merge": new})
                tree = [git(repo, "rev-parse", c + "^{tree}") for c in (new, m["step"])]
                if git(repo, "rev-parse", new + "^") != expected or tree[0] != tree[1]:
                    why = "landed as %s, not the train's tested state; merge record not posted" % new
                elif subprocess.run(["gh", "pr", "review", str(m["pr"]), "--comment", "-R", slug, "--body",
                                     train_merge_record(values, rec, i, m, new, "owner merge-ok at head" if merge_ok
                                                        else 'merge_grant = "%s"' % grant)],
                                    capture_output=True).returncode:
                    why = "landed as %s, but the merge record was not posted" % new
                expected = new
        except RuntimeError as e:
            why = str(e)
        if why:
            stop = (m["pr"], why)
            break
    closed, deleted = train_close(repo, slug, rec)
    rec.update(landed=landed, stopped=stop and {"pr": stop[0], "reason": stop[1]})
    train_save(state, rec)
    for x in landed:
        print("landed pr=%d head=%s merge=%s" % (x["pr"], x["head"], x["merge"]))
    if stop:
        print("stopped pr=%d reason=%s" % stop)
    print("train n=%d landed=%d/%d pr-closed=%s branch-deleted=%s" % (
        n, len(landed), len(rec["members"]), "yes" if closed else "no", "yes" if deleted else "no"))
    return 0 if len(landed) == len(rec["members"]) else 1


def register(sub):
    p = sub.add_parser("train", help="merge train: CI once on main + approved PRs, then land them in order")
    p.add_argument("action", choices=["build", "land", "bisect"])
    p.add_argument("items", nargs="+", type=int, help="build: PR numbers in landing order; land: the train number")
    p.add_argument("--grace", type=float, default=20.0, help="seconds after the train PR opens before reading CI")
    p.add_argument("--interval", type=float, default=20.0, help="seconds between CI reads")
    p.add_argument("--timeout", type=float, default=1800.0, help="seconds to wait for CI after the grace period")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    if args.action == "bisect":
        print("crew: train bisect is not implemented yet (#321 follow-up): rebuild the train without the suspect PR, "
              "or land its members one at a time")
        return 2
    if args.action != "build" and len(args.items) != 1:
        print("crew: train %s takes one train number" % args.action)
        return 2
    values, _, state = profile(args, *(("worktree_root",) if args.action == "build" else ()))
    slug = "%s/%s" % (values["repo.owner"], values["repo.name"])
    try:
        repo = git(os.path.dirname(os.path.abspath(args.project)), "rev-parse", "--show-toplevel")
        return (train_build if args.action == "build" else train_land)(args, values, state, repo, slug)
    except RuntimeError as e:
        print(e)
        return 1
