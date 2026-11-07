"""`mdstack kill` removes a role window with its own worktree (SIGTERM then SIGKILL the pane process group first),
then dequeues the oldest spawn in the freed band.

Usage: mdstack kill WINDOW [--discard --reason TEXT] --project FILE [--org-profile FILE]
"""
import os
from crew_shared import BANDS, commands, kill_run, profile, runs, tmux


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
    values, session, state = profile(args, "worktree_root")
    if tmux.has_session(session):
        tmux.pin_layout(session)
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    if windows.get(args.window) == 0:
        print("crew: refusing to kill the coordinator window; use mdstack down")
        return 1
    if args.window not in windows and not os.path.exists(os.path.join(state, "runs", args.window + ".json")):
        print("crew: no run %s" % args.window)
        return 1
    role = dict(runs(state)).get(args.window, {}).get("role")
    if commands()["lead"].enabled(state, role) and os.environ.get("CREW_POOL") != role and not args.discard:
        rec = dict(runs(state))[args.window]
        return commands()["lead"].event(args, role, {"reason": "lifecycle", "action": "reclaim", "window": args.window,
                         "start": rec.get("start"), "head": rec.get("head"), "args": rec.get("args")})
    if role is None:
        role = next((r for r, (lo, hi) in BANDS.items() if lo <= windows.get(args.window, -1) <= hi), None)
    if kill_run(values, session, state, args.window, args.reason if args.discard else None):
        return 1
    print("crew: killed %s" % args.window)
    return commands()["dequeue"].run(args, role=role) if role and not commands()["lead"].enabled(state, role) else 0
