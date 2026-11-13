"""Private transport for the ack, verdict and merge-up narrative posters (#237).

Uses the existing runtime reads and backend mapping; posts COMMENT at the native full head,
never approval. A failed post response is reconciled by readback, never retried blindly.
"""
import json
import os
import re
import shlex
import subprocess
from crew_shared import commands, coordinator_window, crew_render, HERE, require_ownership, ROLES, ROOT


def sha(value):
    if not re.fullmatch(r"[0-9a-f]{40}", value or ""):
        raise ValueError("full SHA required")
    return value


def view(values, pr):
    if any(values["backends.%s.name" % concern] != "github" for concern in ("change", "review", "markers")):
        raise ValueError("helper live PR read unavailable for this backend")
    return commands()["route"].gh("pr", "view", str(pr), "-R", "%s/%s" % (values["repo.owner"], values["repo.name"]),
                                  "--json", "number,state,isDraft,headRefOid,baseRefName,body,labels,reviews,commits,closingIssuesReferences,statusCheckRollup")


def actor(args, values, state, role):
    name = args.actor
    coordinator = role == "coordinator" and name == coordinator_window(values) and not os.environ.get("CREW_ID")
    if not re.fullmatch(r"[A-Za-z0-9][\w.-]*", name or "") or (not coordinator and os.environ.get("CREW_ID") != name) or os.environ.get("CREW_ROLE") != role:
        raise ValueError("actual run actor/role required")
    path = os.path.join(state, "runs", name + ".json")
    if coordinator and not os.path.exists(path):
        parts = (args.engine or "").split()
        if len(parts) != 3 or not args.harness or not args.start:
            raise ValueError("coordinator without a run record needs actual --engine, --harness and --start")
        rec = dict(role=role, engine=parts[0], model=parts[1], effort=parts[2], harness=args.harness, start=args.start,
                   worktree=os.getcwd())
    else:
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
    if rec["role"] != role or role != "coordinator" and (rec["args"].get("pr") != args.pr or rec["head"] != args.head):
        raise ValueError("foreign run PR/head/role")
    login = commands()["poll"].gh_json("api", "user")["login"]
    if login != values["identities.%s.gh_user" % role]:
        raise ValueError("wrong posting identity")
    if not all(isinstance(rec.get(k), str) and rec[k].strip() and not re.search(r"[\s<>]", rec[k])
               for k in ("engine", "model", "effort", "harness")):
        raise ValueError("actual engine/model/effort/harness required")
    defaults = ROLES[role]["identity_defaults"]
    name_ = values["identities.%s.name" % role]
    title = values.get("identities.%s.title" % role, defaults["title"])
    emoji = values.get("identities.%s.emoji" % role, defaults["emoji"]) if values.get("report.emoji", True) else ""
    rec["signature"] = "— %s%s (%s) · %s · %s" % (emoji + " " if emoji else "", name_, title, rec["harness"], rec["model"])
    return rec


def usage(state, name, rec):
    path = os.path.join(state, "runs", name + ".json")
    flags = ["--run", path] if os.path.exists(path) else ["--engine", rec["engine"], "--dir", rec["worktree"], "--start", rec["start"]]
    r = subprocess.run(["python3", os.path.join(HERE, "run-usage.py"), *flags], capture_output=True, text=True)
    if r.returncode:
        raise ValueError("run usage unavailable")
    return r.stdout.strip()


def post(args, values, state, head, body, validate):
    """Re-read the binding under a per-PR lock; validate returns False for an existing identity key."""
    import fcntl
    os.makedirs(os.path.join(state, "helper-locks"), exist_ok=True)
    with open(os.path.join(state, "helper-locks", "pr%s.lock" % args.pr), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        live = view(values, args.pr)
        if not validate(live):
            print("crew: ack already posted")
            return 0
        if not require_ownership(values, "write"):
            raise ValueError("ownership changed before post")
        overlay = crew_render.pack_overlay(args.project, args.org_profile, values)
        renderer = crew_render.Renderer(values, os.path.join(ROOT, "templates"), overlay=overlay)
        template, _ = renderer.op("review", "post-verdict")
        if "<head-sha>" not in template or "<APPROVE|REQUEST_CHANGES>" not in template:
            raise ValueError("native head-bound COMMENT mapping unavailable")
        path = os.path.join(state, "runs", args.actor + ".body.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        fill = {"<owner>": values["repo.owner"], "<repo>": values["repo.name"], "<n>": str(args.pr),
                "<head-sha>": head, "<file>": path, "<APPROVE|REQUEST_CHANGES>": "COMMENT"}
        argv = [re.sub("|".join(map(re.escape, fill)), lambda m: fill[m.group(0)], a) for a in shlex.split(template)]
        r = subprocess.run(argv, capture_output=True, text=True)
        if r.returncode:
            if any(review["body"] == body for review in view(values, args.pr)["reviews"]):
                print("crew: post confirmed by readback")
                return 0
            raise ValueError("post response uncertain; reconcile live reviews before retry")
        print("crew: posted COMMENT @ " + head)
        return 0
