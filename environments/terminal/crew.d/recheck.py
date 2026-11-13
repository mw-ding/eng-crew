"""Request the explicit fresh merge-up recheck, retaining the prior approval's round.

Usage: mdstack recheck PR --head SHA --round K --project FILE [--rereview-id ID] [--wait-ack SECONDS]
Unconfirmed merges or an open full rereview route normal review. Behind alone never triggers this command.
The fresh recheck worker bounds remerge hunks and reruns acceptance checks, escalating broader content.
"""
import os
import sys
from crew_shared import commands, profile, refuse_paused, require_ownership


def register(sub):
    commands()["review"].arguments(sub.add_parser("recheck"))


def run(args):
    try:
        values, _, state = profile(args)
        print("mdstack: config " + os.path.abspath(args.project), file=sys.stderr)
        if not require_ownership(values, "start") or refuse_paused(state, "recheck"):
            raise ValueError("recheck refused")
        review, route = commands()["review"], commands()["route"]
        pr = review.live(args, values)
        approved = route.approved_merge_up(pr, "%s/%s" % (values["repo.owner"], values["repo.name"]), values["repo.default_branch"])
        pass_ = "recheck" if approved and not route.open_rereview(pr, args.head) else "review"
        if pass_ == "review":
            print("crew: recheck escalates to normal review")
        return review.handoff(args, values, state, pr, pass_)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as e:
        print("crew: refusing recheck: " + str(e))
        return 2
