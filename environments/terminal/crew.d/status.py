"""`mdstack status` prints the coordinator's and each run's liveness (alive, dead, missing, ambiguous; a trust or Codex
hooks-review dialog on screen is ambiguous) from its pane identity, and the host placement chose for each run (- for
a record from before placement or a crew with no [hosts] inventory, #207). A run on a role host shows its host's probe
(#345), `unreachable` when the host does not answer.

Usage: mdstack status --project FILE [--org-profile FILE]
"""
import subprocess
import time
from crew_shared import ENGINE_CMD, harness_up, heartbeat, probe, profile, remote_run, runs, tmux


def register(sub):
    p = sub.add_parser("status")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args):
    """Table of role runs: window, role, host, item, head, last status line, heartbeat age, liveness."""
    values, session, state = profile(args)
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    rows = [("WINDOW", "ROLE", "HOST", "ITEM", "HEAD", "BEAT", "LIVENESS", "LAST")]
    p = tmux.pane(session, 0) if 0 in windows.values() else None
    if p:
        rows.append(([n for n, i in windows.items() if i == 0][0], "coordinator", "-", "-", "-", "-",
                     "dead" if p["dead"] == "1" else harness_up(session, 0, p, ENGINE_CMD.values()), "-"))
    for name, rec in runs(state):
        last, beat = heartbeat(state, name)
        head = subprocess.run(["git", "-C", rec.get("worktree") or "/nonexistent", "rev-parse", "--short=7", "HEAD"],
                              capture_output=True, text=True).stdout.strip() or "-"
        rows.append((name, rec["role"], rec.get("host") or "-", rec["item"], head, "%dm" % ((time.time() - beat) // 60),
                     remote_run.probe(values, name, rec) if remote_run.host_of(rec) else probe(session, name, rec, windows),
                     last or "-"))
    widths = [max(len(r[i]) for r in rows) for i in range(7)]
    print("\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths)) + "  " + r[7] for r in rows))
    return 0
