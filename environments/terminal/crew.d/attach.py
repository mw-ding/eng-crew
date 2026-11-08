"""`mdstack attach` watches a window read-only (or a temporary tiled builders view).

Usage: mdstack attach WINDOW|ROLE|builders [--rw] --project FILE [--org-profile FILE]
"""
import os
from crew_shared import BANDS, profile, tmux


# Observe (#138): attach to a window, or tail a run's step summary (docs/observe.md).
ROLE_BANDS = dict(BANDS, coordinator=(0, 0))
# One pane of the builders view: the last lines of a window's screen (trailing blanks dropped), refreshed every second.
# Values are single-quoted: shlex.quote leaves "=" bare, which zsh (a common default-shell) expands.
SNAPSHOT = "while :; do out=$(tmux capture-pane -p -t '%s' | awk 'NF { n = NR } { l[NR] = $0 } " \
    "END { for (i = 1; i <= n; i++) print l[i] }' | tail -n \"$(($(tput lines) - 1))\"); " \
    "printf '\\033[H\\033[2J== %%s ==\\n%%s' '%s' \"$out\"; sleep 1; done"


def register(sub):
    p = sub.add_parser("attach")
    p.add_argument("target", help="window name, role (builder, reviewer, synthesizer, coordinator) or builders")
    p.add_argument("--rw", action="store_true", help="interactive attach; read-only by default")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args):
    """Attach read-only (--rw to type) to a window, or to a role's only window; `builders` opens a temporary tiled
    view of the builder band in a separate session, killed on detach, so the mdstack layout never changes."""
    values, session, state = profile(args)
    if not tmux.has_session(session):
        print("crew: %s not running" % session)
        return 1
    windows = sorted(tmux.list_windows(session))
    if args.target == "builders":
        band = [(i, n) for i, n in windows if BANDS["builder"][0] <= i <= BANDS["builder"][1]]
        if not band:
            print("crew: no builder windows")
            return 1
        name = "%s-builders-%d" % (session, os.getpid())
        tmux.view(name, [SNAPSHOT % ("=%s:%d" % (session, i), n) for i, n in band])
        try:
            return tmux.attach("=" + name, not args.rw)
        finally:
            tmux.kill_session(name)
    found = [(i, n) for i, n in windows if n == args.target]
    if not found and args.target in ROLE_BANDS:
        lo, hi = ROLE_BANDS[args.target]
        found = [(i, n) for i, n in windows if lo <= i <= hi]
        if len(found) > 1:
            print("crew: %s has several windows (%s); name one" % (args.target, ", ".join(n for _, n in found)))
            return 1
    if not found:
        print("crew: no window %s in %s" % (args.target, session))
        return 1
    return tmux.attach("=%s:%d" % (session, found[0][0]), not args.rw)
