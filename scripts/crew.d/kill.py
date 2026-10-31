"""crew kill WINDOW [--discard --reason TEXT] --project FILE [--org-profile FILE]"""
import os
from crew_shared import kill_run, profile, tmux


def register(sub):
    p = sub.add_parser("kill")
    p.add_argument("window")
    p.add_argument("--discard", action="store_true", help="remove unlanded work; needs --reason")
    p.add_argument("--reason", help="why the unlanded work is discarded; posted on the run's PR or issue")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    if args.discard and not args.reason:
        print("crew: --discard needs --reason \"<why>\" (the owner's decision, posted on the item)")
        return 2
    values, session, state = profile(args)
    if tmux.has_session(session):
        tmux.pin_layout(session)
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    if windows.get(args.window) == 0:
        print("crew: refusing to kill the coordinator window; use crew down")
        return 1
    if args.window not in windows and not os.path.exists(os.path.join(state, "runs", args.window + ".json")):
        print("crew: no run %s" % args.window)
        return 1
    if kill_run(values, session, state, args.window, args.reason if args.discard else None):
        return 1
    print("crew: killed %s" % args.window)
    return 0
