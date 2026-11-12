"""`mdstack ownership` re-reads the repo control item before dispatch, push, post or land.

Usage: mdstack ownership --project FILE [--org-profile FILE] [--action start|write|land] [--runtime session]
Exit 0 when permitted, 1 otherwise; works with either runtime binding. A project pause (#1714) refuses start and land. `--runtime session`
checks as `session@<runtime.instance>`, for a coordinator session with no binding yet.
"""
import os
from crew_shared import crew_render, refuse_paused, require_ownership


def register(sub):
    p = sub.add_parser("ownership")
    p.add_argument("--project")
    p.add_argument("--org-profile")
    p.add_argument("--action", choices=["start", "write", "land"], default="start")
    p.add_argument("--runtime", choices=["session"])


def run(args):
    values, problems = crew_render.resolve(args.project, args.org_profile)
    if problems:
        print("\n".join(problems))
        return 1
    if args.runtime:
        values = dict(values, **{"runtime.name": args.runtime})
    if not require_ownership(values, args.action):
        return 1
    state = os.path.join(os.path.abspath(values["paths.state_dir"]), "%s__%s" % (values["repo.owner"], values["repo.name"]))
    return 1 if args.action != "write" and refuse_paused(state, args.action) else 0
