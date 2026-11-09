"""`mdstack acked` checks an `mdstack send` message by the `ack: <msg-id>` line in the window's status file; for a run
on a role host it pulls that file's new lines into the primary's mirror first (#346).

Usage: mdstack acked WINDOW MSG-ID [--wait SECS] --project FILE
"""
from crew_shared import profile, remote_run, runs, wait_ack


def register(sub):
    p = sub.add_parser("acked")
    p.add_argument("window")
    p.add_argument("id")
    p.add_argument("--wait", type=float, default=0.0, help="seconds to wait for the ack (default: check once)")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args):
    values, _, state = profile(args)
    rec = dict(runs(state)).get(args.window, {})
    return wait_ack(state, args.window, args.id, args.wait,
                    remote_run.refresh(values, state, args.window, rec) if remote_run.host_of(rec) else None)
