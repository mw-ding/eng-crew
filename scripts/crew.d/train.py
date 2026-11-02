"""`crew train build` merges approved PR heads onto the fetched default branch as `crew/train-<n>` in a temporary clone
that ignores local merge attributes (a conflicting PR is dropped), runs the local checks and waits for CI on a draft
train PR after a grace period; `crew train land <n> <pr>` lands the next member head-bound after re-checking the
tested default branch, head, blocking state tags, verdict, open rereview, open hold-until, merge permission and
GitHub mergeability, posts a merge record citing the train, and ends the train (PR closed, branch deleted) on a stop
or the last member; `crew train close` ends it early; `bisect` is not built yet.

Usage: crew train build PR... [--after N] [--no-wait] | check PR... | wait N | land N PR | close N | bisect N
       --project FILE [--org-profile FILE]
"""
import contextlib
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from crew_shared import commands, fetch, git, ownership, profile, require_ownership


# Merge train (tmux.md crew train, #321): build crew/train-<n> = fetched main + each PR head as --no-ff merges, run the
# local checks, push it with a draft PR so CI runs once on the combined result, then land the members one call each, in
# order, at their tested heads with no catch-up between them. Machine-readable lines: member, dropped, landed, stopped,
# train.
def train_path(state, n):
    return os.path.join(state, "trains", "train-%d.json" % n)


def train_load(state, n):
    try:
        with open(train_path(state, n)) as f:
            return json.load(f)
    except FileNotFoundError:
        print("crew: no train %d (run crew train build)" % n)
        return None


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


def train_close(repo, slug, rec, values):
    """Close the train PR without a comment and delete the train branch; the line saying whether both happened."""
    if not require_ownership(values, "write"):
        return "ownership-lost; train kept"
    rec["closed"] = True
    closed = subprocess.run(["gh", "pr", "close", str(rec["pr"]), "-R", slug], capture_output=True).returncode == 0
    deleted = subprocess.run(["git", "-C", repo, "push", "-q", "origin", "--delete", rec["branch"]],
                             capture_output=True).returncode == 0
    return "pr-closed=%s branch-deleted=%s" % ("yes" if closed else "no", "yes" if deleted else "no")


def train_build(args, values, state, repo, slug):
    n, main = train_number(repo, state), values["repo.default_branch"]
    base = fetch(repo, main)
    parent = train_load(state, args.after) if args.after else None
    if args.after:
        if parent is None or parent.get("stopped") or (parent.get("closed") and
                len(parent.get("landed", [])) != len(parent["members"])):
            print("crew: predecessor unavailable; build on the default branch instead")
            return 1
        base = fetch(repo, parent["branch"]) if not parent.get("closed") else parent["sha"]
        if base != parent["sha"]:
            print("crew: predecessor train branch moved")
            return 1
    wt = os.path.join(os.path.abspath(values["paths.worktree_root"]), "train-%d-%s" % (n, base[:7]))
    if os.path.lexists(wt):
        print("crew: refusing train: %s exists" % wt)
        return 1
    rec = {"n": n, "branch": "crew/train-%d" % n, "base": base, "sha": base, "members": [], "dropped": [],
           "pr": None, "local": "none", "ci": "none", "ci_links": [], "after": args.after, "deferred": []}
    os.makedirs(os.path.dirname(wt), exist_ok=True)
    # A temporary clone, not a worktree: the shared repo's info/attributes (or a global attributes file) can resolve a
    # conflict locally, e.g. merge=union, that GitHub's merge then hits (train 4, #321).
    git(repo, "clone", "-q", "--shared", "--no-checkout", repo, wt)
    try:
        with contextlib.suppress(FileNotFoundError):  # an init template could still supply one
            os.remove(os.path.join(wt, ".git", "info", "attributes"))
        git(wt, "remote", "set-url", "origin", git(repo, "remote", "get-url", "origin"))
        git(wt, "checkout", "-q", "--detach", base)
        for pr in dict.fromkeys(args.items):
            if parent and pr in {m["pr"] for m in parent["members"]}:
                rec["deferred"].append({"pr": pr, "reason": "predecessor-member"})
                continue
            try:
                head = fetch(wt, "pull/%d/head" % pr)
            except RuntimeError:
                rec["dropped"].append({"pr": pr, "reason": "no-head"})
                continue
            paths = set(git(wt, "diff", "--name-only", base + "..." + head).splitlines())
            overlap = None
            for member in rec["members"]:
                if paths & set(member["paths"]):
                    pair = subprocess.run(["git", "-C", wt, "-c", "core.attributesFile=" + os.devnull,
                                           "merge-tree", "--write-tree", member["head"], head], capture_output=True)
                    if pair.returncode:
                        overlap = member["pr"]
                        break
            if overlap:
                rec["deferred"].append({"pr": pr, "reason": "overlap-with-%d" % overlap})
                continue
            r = subprocess.run(["git", "-C", wt, "-c", "core.attributesFile=" + os.devnull, "merge", "-q", "--no-ff",
                                "--no-edit", "-m",
                                "crew train %d: merge #%d @ %s" % (n, pr, head[:7]), head], capture_output=True)
            if r.returncode:  # a conflict drops the PR; its builder resolves it (synthesizer brief)
                subprocess.run(["git", "-C", wt, "merge", "--abort"], capture_output=True)
                rec["dropped"].append({"pr": pr, "reason": "conflict"})
                continue
            rec["members"].append({"pr": pr, "head": head, "step": git(wt, "rev-parse", "HEAD"), "paths": sorted(paths)})
        rec["sha"] = git(wt, "rev-parse", "HEAD")
        failed, tail = train_local_checks(wt) if rec["members"] else ("none", [])
        rec["local"] = "pass" if failed is None else "none" if failed == "none" else "fail " + failed
        if rec["members"] and failed in (None, "none"):
            if not require_ownership(values, "write"):
                return 1
            git(wt, "push", "-q", "origin", "HEAD:refs/heads/" + rec["branch"])
            body = ("Merge train %d: CI on the combined result only. Never merge this PR; `crew train land %d` lands "
                    "the members and closes it.\n\n- Base: `%s` %s\n- Train SHA: %s\n- Members, in landing order: %s\n"
                    "- Dropped (conflict): %s\n" % (
                        n, n, main, base, rec["sha"], ", ".join("#%d @ %s" % (m["pr"], m["head"][:7])
                                                                for m in rec["members"]),
                        ", ".join("#%d" % d["pr"] for d in rec["dropped"]) or "none"))
            if not require_ownership(values, "write"):
                return 1
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
                rec["ci"] = "pending"
                train_save(state, rec)
                if not args.no_wait:
                    rec["ci"], rec["ci_links"] = train_wait_ci(slug, rec["pr"], args)
                if rec["ci"] not in ("pass", "pending"):  # a red train never lands; its check links stay readable after the close
                    train_close(repo, slug, rec, values)
        for line in tail:
            print("crew: %s: %s" % (failed, line))
    finally:
        shutil.rmtree(wt, ignore_errors=True)
    train_save(state, rec)
    for m in rec["members"]:
        print("member pr=%d head=%s step=%s" % (m["pr"], m["head"], m["step"]))
    for d in rec["dropped"]:
        print("dropped pr=%d reason=%s" % (d["pr"], d["reason"]))
    for d in rec["deferred"]:
        print("deferred pr=%d reason=%s" % (d["pr"], d["reason"]))
    for link in rec["ci_links"]:
        print("ci-link %s" % link)
    print("train n=%d branch=%s base=%s sha=%s pr=%s local=%s ci=%s" % (
        n, rec["branch"], base, rec["sha"], rec["pr"] or "none", rec["local"].replace(" ", ":"), rec["ci"]))
    return 0 if rec["ci"] in ("pass", "pending") else 1


def train_predecessor(args, values, state, repo, slug, rec):
    """A stopped predecessor invalidates the speculative tree; rebuild its successor on current main."""
    if not rec.get("after"):
        return None, rec["base"]
    parent = train_load(state, rec["after"])
    if parent is None or parent.get("stopped") or (parent.get("closed") and
            len(parent.get("landed", [])) != len(parent["members"])):
        train_close(repo, slug, rec, values)
        rec["stopped"] = {"reason": "predecessor stopped; rebuilt on main"}
        train_save(state, rec)
        args.items = [m["pr"] for m in rec["members"]]
        args.after = None
        print("rebuild train=%d reason=predecessor-stopped" % rec["n"])
        return train_build(args, values, state, repo, slug), None
    if len(parent.get("landed", [])) != len(parent["members"]):
        return None, None
    expected = parent["landed"][-1]["merge"]
    if parent["sha"] != rec["base"] or git(repo, "rev-parse", expected + "^{tree}") != git(
            repo, "rev-parse", rec["base"] + "^{tree}"):
        raise RuntimeError("crew: predecessor did not land the successor's tested base")
    return None, expected


def train_check(args, values, state, repo, slug):
    """Read-only, conservative pre-check. Manual gates remain explicit; land always re-checks §7."""
    poll, blocked = commands()["poll"], False
    for pr in args.items:
        view = poll.gh_json("pr", "view", str(pr), "-R", slug, "--json",
                            poll.PR_FIELDS + ",comments,mergeable,body,files,isDraft,baseRefName,closingIssuesReferences")
        head = view["headRefOid"]
        mode = ownership(values)
        results = {"ownership": ("pass", "runtime owns project") if mode == "active" else ("blocked", mode)}
        why, merge_ok = train_gate(poll, values, slug, view, head)
        results["state-permission"] = ("blocked", why) if why else ("pass", "current gate snapshot")
        verdict = None
        for review in view["reviews"]:
            markers = [dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
                       for line in poll.CREW_LINE.findall(review["body"])]
            if any(m.get("pass") == "verdict" and m.get("sha") == head for m in markers):
                verdict = review, markers
        approved = False
        if verdict:
            review, markers = verdict
            expected = values.get("identities.reviewer.gh_user")
            identity = not expected or review.get("author", {}).get("login") == expected
            formal = review.get("state") == "APPROVED" or values.get(
                "backends.review.capabilities.post-verdict", "").startswith("emulated")
            approved = identity and formal and all(any(m.get("role") == "reviewer-validator" and
                m.get("pass") == kind and m.get("sha") == head and m.get("verdict") == "pass"
                for m in markers) for kind in ("review", "validate", "verdict"))
        results["verdict"] = ("pass", "formal review + validate + verdict at head") if approved else (
            "blocked", "missing formal passing review/validate/verdict at head")
        results["ci"] = ("pass", "checks green at head") if poll.pr_snapshot(view)["ci"] == "passed" else (
            "blocked", "checks " + poll.pr_snapshot(view)["ci"])
        tags = {lb["name"] for lb in view["labels"]}
        results["sensitive"] = ("blocked", "owner merge-ok needed at head") if (
            "crew:sensitive" in tags and not merge_ok) else ("pass", "merge-ok present or not sensitive")
        posts = "\n".join([view["body"], *[p["body"] for p in view["reviews"] + view["comments"]]])
        evidence = re.search(r"## Acceptance Evidence\s+(.+?)(?=\n## |\Z)", view["body"], re.S)
        paths = set(re.findall(r"evidence/[\w./-]+", posts))
        if paths:
            tree = poll.gh_json("api", "repos/%s/git/trees/%s?recursive=1" % (slug, head))
            missing = paths - {entry["path"] for entry in tree["tree"]}
            results["evidence"] = ("blocked", "missing artifacts: " + ", ".join(sorted(missing))) if missing else (
                "manual", "artifacts present; verify validation agrees with each claim")
        elif evidence and re.search(r"\bN/A\b[^\n]*[a-zA-Z]{3}", evidence.group(1)):
            results["evidence"] = ("manual", "verify the stated N/A reason against behaviour")
        elif evidence and "```sh" in evidence.group(1) and "```text" in evidence.group(1):
            results["evidence"] = ("manual", "inline reproduction; verify applicable evidence policy and validation")
        else:
            results["evidence"] = ("blocked", "no evidence artifacts or reasoned N/A")
        mirrored = any(f["path"] == "docs/protocol.md" or f["path"].startswith("templates/")
                       for f in view["files"])
        mirror_posts = [p for p in view["comments"] if p.get("author", {}).get("login") ==
                        values.get("identities.coordinator.gh_user") and "check-skill-drift.py" in p["body"]]
        results["mirror"] = ("blocked", "crew:needs-mirror") if "crew:needs-mirror" in tags else (
            ("manual", "verify coordinator deployed and clean drift check after last touching commit") if mirrored
            and (mirror_posts or values.get("runtime.options.mirror_deferral", "none") not in ("none", ""))
            else ("blocked", "no coordinator mirror/drift record") if mirrored
            else ("pass", "no mirrored paths"))
        results["change"] = ("blocked", "closed, draft or wrong base") if (view["state"] != "OPEN" or
            view["isDraft"] or view["baseRefName"] != values["repo.default_branch"]) else ("pass", "open on default base")
        results["grant-scope"] = ("manual", "verify owner authorization and grant scope")
        results["engine"] = ("manual", "verify actual builder engine and diversity re-check")
        results["linkage"] = ("manual", "verify Closes linkage or protocol exemption")
        results["runtime"] = ("manual", "verify runtime gates and synthesizer inbox holds")
        results["tested-base"] = ("manual", "train supplies tested-base evidence at serial land")
        for gate, (status, reason) in results.items():
            print("gate pr=%d sha=%s name=%s status=%s reason=%s" % (pr, head, gate, status, json.dumps(reason)))
            blocked |= status == "blocked"
    return 1 if blocked else 0


def train_wait(args, values, state, repo, slug):
    rec = train_load(state, args.items[0])
    if rec is None or rec.get("closed") or not rec.get("pr"):
        return 1
    rebuilt, _ = train_predecessor(args, values, state, repo, slug, rec)
    if rebuilt is not None:
        return rebuilt
    rec["ci"], rec["ci_links"] = train_wait_ci(slug, rec["pr"], args)
    if rec["ci"] != "pass":
        train_close(repo, slug, rec, values)
    train_save(state, rec)
    rebuilt, _ = train_predecessor(args, values, state, repo, slug, rec)
    if rebuilt is not None:
        return rebuilt
    print("train n=%d ci=%s" % (rec["n"], rec["ci"]))
    for link in rec["ci_links"]:
        print("ci-link %s" % link)
    return 0 if rec["ci"] == "pass" else 1


def train_merge_record(values, rec, i, m, merge, permission):
    return ("[%s/merge] squashed @ %s → %s (crew train %d)\n\n"
            "Land rule: train of %d (ready together).\n\n"
            "- Train: `%s` @ %s (base `%s` %s), member %d of %d, train PR #%d (draft, CI only); CI green: %s. "
            "Tested with main: `%s` held exactly the train's state before this member, so no catch-up.\n"
            "- Approval at head: `pass=verdict verdict=pass` at %s.\n- Permission: %s.\n\n"
            "<!-- crew:v1 role=synthesizer pass=merge pr=%d sha=%s round=n/a verdict=n/a -->\n" % (
                values.get("identities.synthesizer.name", "Sam"), m["head"][:7], merge[:7], rec["n"], len(rec["members"]), rec["branch"],
                rec["sha"], values["repo.default_branch"], rec["base"], i, len(rec["members"]), rec["pr"],
                ", ".join(rec["ci_links"]) or "all checks", values["repo.default_branch"], m["head"][:7], permission,
                m["pr"], m["head"]))


def train_view(poll, slug, pr, args):
    """The PR with comments and mergeability; GitHub reports UNKNOWN until it has computed it: read up to 10 times."""
    for _ in range(10):
        view = poll.gh_json("pr", "view", str(pr), "-R", slug, "--json", poll.PR_FIELDS + ",comments,mergeable")
        if view.get("mergeable") != "UNKNOWN":
            break
        time.sleep(min(args.interval, 3.0))
    return view


def train_gate(poll, values, slug, view, head):
    """The §7 gates land re-checks at head right before the squash: (first miss or None, merge-ok at head). The other
    gates are the synthesizer's check right before this call (synthesizer brief)."""
    rereview = merge_ok = False
    for r in view["reviews"]:  # in order: a rereview at head stays open until a verdict at head follows it
        for line in poll.CREW_LINE.findall(r["body"]):
            k = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if k.get("sha") == head and k.get("pass") == "steer":
                rereview, merge_ok = rereview or k.get("cmd") == "rereview", merge_ok or k.get("cmd") == "merge-ok"
            elif k.get("sha") == head and k.get("pass") == "verdict" and k.get("role") == "reviewer-validator":
                rereview = False
    tags = {lb["name"] for lb in view["labels"]} & ({"crew:escalated", "crew:changes"} | (
        {"crew:hold"} if values.get("runtime.options.hold_label_blocks", True) else set()))
    posts = "\n".join(p["body"] for p in view["reviews"] + view["comments"])
    holds = sorted(set(re.findall(r"hold-until-#(\d+)", posts)))  # held until that item lands or closes
    held = [x for x in holds if poll.gh_json("issue", "view", x, "-R", slug, "--json", "state")["state"] == "OPEN"]
    grant = values.get("runtime.options.merge_grant", "none")
    sensitive = any(lb["name"] == "crew:sensitive" for lb in view["labels"])
    why = ("head changed: %s, tested %s" % (view["headRefOid"], head) if view["headRefOid"] != head else
           "state tag %s" % ", ".join(sorted(tags)) if tags else
           "no approval verdict at head" if poll.pr_snapshot(view)["verdict"] != "pass" else
           "open rereview at head" if rereview else
           "open coordinator hold-until-#%s" % held[0] if held else
           "crew:sensitive needs owner merge-ok at head" if sensitive and not merge_ok else
           "no merge permission: no merge-ok at head and merge_grant is none" if not merge_ok and grant == "none" else
           "not mergeable: GitHub reports %s" % view.get("mergeable") if view.get("mergeable") != "MERGEABLE" else None)
    return why, merge_ok


def train_land(args, values, state, repo, slug):
    """Land one member, the next in order; the synthesizer re-runs the whole §7 check at its head right before."""
    (n, pr), main, poll = args.items, values["repo.default_branch"], commands()["poll"]
    rec = train_load(state, n)
    if rec is None:
        return 1
    if rec["ci"] != "pass" or rec.get("closed"):
        print("crew: train %d is %s; nothing landed" % (n, "CI " + rec["ci"] if rec["ci"] != "pass" else "closed"))
        return 1
    rebuilt, predecessor_base = train_predecessor(args, values, state, repo, slug, rec)
    if rebuilt is not None:
        return rebuilt
    if predecessor_base is None:
        print("crew: predecessor has not finished; nothing landed")
        return 1
    landed = rec.setdefault("landed", [])
    i, m = len(landed) + 1, rec["members"][len(landed)]
    if pr != m["pr"]:
        print("crew: train %d lands #%d next, not #%d; nothing landed" % (n, m["pr"], pr))
        return 2
    expected, why, merge_ok = landed[-1]["merge"] if landed else predecessor_base, None, False
    try:
        cur = fetch(repo, main)
        if fetch(repo, rec["branch"]) != rec["sha"]:
            why = "train branch moved"
        elif cur != expected:
            why = "main moved: %s, train state %s" % (cur, expected)
        else:
            why, merge_ok = train_gate(poll, values, slug, train_view(poll, slug, pr, args), m["head"])
        if not why:
            if not require_ownership(values, "land"):
                return 1
            r = subprocess.run(["gh", "pr", "merge", str(pr), "-R", slug, "--squash", "--match-head-commit", m["head"]],
                               capture_output=True, text=True)
            why = "merge refused: " + r.stderr.strip() if r.returncode else None
        if not why:  # landed: the squash must sit on the tested state and reproduce the train step's tree
            new = fetch(repo, main)
            landed.append({"pr": pr, "head": m["head"], "merge": new})
            tree = [git(repo, "rev-parse", c + "^{tree}") for c in (new, m["step"])]
            grant = 'merge_grant = "%s"' % values.get("runtime.options.merge_grant", "none")
            if git(repo, "rev-parse", new + "^") != expected or tree[0] != tree[1]:
                why = "landed as %s, not the train's tested state; merge record not posted" % new
            elif subprocess.run(["gh", "pr", "review", str(pr), "--comment", "-R", slug, "--body", train_merge_record(
                    values, rec, i, m, new, "owner merge-ok at head" if merge_ok else grant)],
                    capture_output=True).returncode:
                why = "landed as %s, but the merge record was not posted" % new
    except RuntimeError as e:
        why = str(e)
    if landed and landed[-1]["pr"] == pr:
        print("landed pr=%d head=%s merge=%s" % (pr, m["head"], landed[-1]["merge"]))
    if why:
        rec["stopped"] = {"pr": pr, "reason": why}
        print("stopped pr=%d reason=%s" % (pr, why))
    done = why or len(landed) == len(rec["members"])  # a stop or the last member ends the train
    tail = train_close(repo, slug, rec, values) if done else "next=%d" % rec["members"][len(landed)]["pr"]
    train_save(state, rec)
    print("train n=%d landed=%d/%d %s" % (n, len(landed), len(rec["members"]), tail))
    return 1 if why else 0


def train_close_cmd(args, values, state, repo, slug):
    """End a train early (the synthesizer's own §7 check failed for the next member): close its PR, delete its branch."""
    rec = train_load(state, args.items[0])
    if rec is None:
        return 1
    tail = train_close(repo, slug, rec, values)
    train_save(state, rec)
    print("train n=%d landed=%d/%d %s" % (rec["n"], len(rec.get("landed", [])), len(rec["members"]), tail))
    return 0


def register(sub):
    p = sub.add_parser("train", help="merge train: CI once on main + approved PRs, then land them in order")
    p.add_argument("action", choices=["build", "wait", "check", "land", "close", "bisect"])
    p.add_argument("items", nargs="+", type=int,
                   help="build: PR numbers in landing order; land: the train number and its next PR; close: the number")
    p.add_argument("--after", type=int, help="build on this predecessor train's tested tip")
    p.add_argument("--no-wait", action="store_true", help="push the train and return while CI is pending")
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
    if len(args.items) != {"build": len(args.items), "check": len(args.items), "wait": 1, "land": 2, "close": 1}[args.action]:
        print("crew: train %s takes %s" % (args.action, "<n> <pr>" if args.action == "land" else "<n>"))
        return 2
    values, _, state = profile(args, *(("worktree_root",) if args.action == "build" else ()))
    slug = "%s/%s" % (values["repo.owner"], values["repo.name"])
    try:
        repo = git(os.path.dirname(os.path.abspath(args.project)), "rev-parse", "--show-toplevel")
        return {"build": train_build, "wait": train_wait, "check": train_check, "land": train_land, "close": train_close_cmd}[args.action](
            args, values, state, repo, slug)
    except RuntimeError as e:
        print(e)
        return 1
