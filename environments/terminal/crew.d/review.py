"""Hand a pinned review to the existing reviewer lead; its pool starts fresh validation after passing review.

Usage: mdstack review PR --head SHA --round K --project FILE [--rereview-id ID] [--wait-ack SECONDS]
The coordinator runs neither pass. Admission, claims, engine exclusion and completion routing stay in the pool.
"""
import os
import sys
from crew_shared import commands, load, profile, refuse_paused, require_ownership, runs

posts = load("crew_review_posts", "environments/terminal/crew.d/_helper-posts.py")


def register(sub):
    p = sub.add_parser("review")
    arguments(p)


def arguments(p):
    p.add_argument("pr", type=int)
    for flag in ("head", "round", "project"):
        p.add_argument("--" + flag, required=True, type=int if flag == "round" else str)
    p.add_argument("--org-profile")
    p.add_argument("--rereview-id")
    p.add_argument("--wait-ack", type=float)
    p.add_argument("--timeout", type=float, default=15)


def live(args, values):
    posts.sha(args.head)
    pr = posts.view(values, args.pr)
    if args.pr < 1 or args.round < 1 or pr["number"] != args.pr or pr["headRefOid"] != args.head or pr["state"] != "OPEN" or pr["isDraft"]:
        raise ValueError("invalid, draft, closed or stale PR/head/round")
    if {l["name"] for l in pr["labels"]} & {"crew:hold", "crew:escalated"}:
        raise ValueError("held or escalated PR")
    for item in pr["closingIssuesReferences"]:
        issue = commands()["poll"].gh_json("issue", "view", str(item["number"]), "-R",
                                         "%s/%s" % (values["repo.owner"], values["repo.name"]), "--json", "labels")
        if {l["name"] for l in issue["labels"]} & {"crew:hold", "crew:escalated"}:
            raise ValueError("linked item held or escalated")
    return commands()["route"].own_view(values, pr)


def handoff(args, values, state, pr, pass_):
    route, poll = commands()["route"], commands()["poll"]
    steer = route.rereview_id(pr, args.head)
    if args.rereview_id != steer:
        raise ValueError("obsolete or missing rereview binding")
    expected = poll.pr_snapshot(pr, values=values)["round"]
    if pass_ == "recheck":
        approved = route.approved_merge_up(pr, "%s/%s" % (values["repo.owner"], values["repo.name"]), values["repo.default_branch"])
        expected = approved["round"]
    if args.round != expected:
        raise ValueError("wrong live round")
    if not steer and any(m.get("pass") == "verdict" and m.get("sha") == args.head and m.get("round") == str(args.round)
                         for r in current_reviews(values, pr) for m in route.markers(r["body"])):
        print("crew: pass already completed")
        return 0
    for _, rec in runs(state):
        if rec["role"] == "reviewer" and rec.get("head") == args.head and rec.get("pass") == pass_ and rec.get("args", {}).get("pr") == args.pr and rec["args"].get("round") == args.round and rec.get("rereview_id") == steer:
            print("crew: pass already running")
            return 0
    if live(args, values) != pr or not require_ownership(values, "start") or refuse_paused(state, pass_):
        raise ValueError("live binding changed before handoff")
    refs = ["#%s" % args.pr, args.head, str(args.round)] + ([steer] if steer else [])
    return commands()["lead"].handoff(args, "reviewer", pass_, refs)


def current_reviews(values, pr):
    route, poll = commands()["route"], commands()["poll"]
    start = 0
    for i, review in enumerate(pr["reviews"]):
        if any(poll.round_reset(values, review, m) for m in route.markers(review["body"])):
            start = i + 1
    return route.own_reviews(values, dict(pr, reviews=pr["reviews"][start:]))


def run(args):
    try:
        values, _, state = profile(args)
        print("mdstack: config " + os.path.abspath(args.project), file=sys.stderr)
        if not require_ownership(values, "start") or refuse_paused(state, "review"):
            raise ValueError("review refused")
        return handoff(args, values, state, live(args, values), "review")
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as e:
        print("crew: refusing review: " + str(e))
        return 2
