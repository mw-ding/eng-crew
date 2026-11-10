"""`mdstack copy-claim acquire|release|show` holds a host-wide claim on a working copy before a run uses it
(docs/runtimes/multi-device.md#working-copy-claims, #391).

A coordinator dispatching a run into an existing working copy (a hand-dispatched pack run, a declared checkout)
acquires the claim first and does not dispatch on a refusal; it releases the claim after the run's cleanup. The crew is
this profile's state root, so a second crew on the host, with its own state root, is refused while the claim lives.
`mdstack spawn` claims each fresh worktree the same way and `mdstack kill` releases it.

Usage: mdstack copy-claim acquire|release|show --path DIR [--run ID] [--item TEXT] --project FILE [--org-profile FILE]
"""
import json
from crew_shared import copy_claim, profile


def register(sub):
    p = sub.add_parser("copy-claim")
    p.add_argument("action", choices=["acquire", "release", "show"])
    p.add_argument("--path", required=True, help="the working copy; aliases resolve to one claim")
    p.add_argument("--run", help="acquire/release: the run holding the copy (a window or run ID)")
    p.add_argument("--item", default="", help="acquire: the item the run works, e.g. 'issue #7'")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args):
    _, _, state = profile(args, runtimes=("tmux", "session"))
    if args.action == "show":
        print(json.dumps(copy_claim.holder(args.path)))
        return 0
    if not args.run:
        print("crew: copy-claim %s needs --run" % args.action)
        return 2
    try:
        if args.action == "acquire":
            print("crew: claimed " + copy_claim.describe(copy_claim.acquire(args.path, state, args.run, args.item)))
        else:
            copy_claim.release(args.path, state, args.run)
            print("crew: released %s" % copy_claim.identity(args.path))
    except RuntimeError as e:
        print(e)
        return 1
    return 0
