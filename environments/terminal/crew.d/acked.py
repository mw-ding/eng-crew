"""`mdstack acked` checks an `mdstack send` message by the `ack: <msg-id>` line in the window's status file.

Usage: mdstack acked WINDOW MSG-ID [--wait SECS] --project FILE
"""
from crew_shared import profile, wait_ack


def register(sub):
    p = sub.add_parser("acked")
    p.add_argument("window")
    p.add_argument("id")
    p.add_argument("--wait", type=float, default=0.0, help="seconds to wait for the ack (default: check once)")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    return wait_ack(profile(args)[2], args.window, args.id, args.wait)
