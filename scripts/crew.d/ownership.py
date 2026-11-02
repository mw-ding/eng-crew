"""`crew ownership` re-reads the repo control item before dispatch, push, post or land.

Usage: crew ownership --project FILE [--org-profile FILE] [--action start|write|land]
Exit 0 when permitted, 1 otherwise; works with either runtime binding.
"""
from crew_shared import crew_render, require_ownership


def register(sub):
    p = sub.add_parser("ownership")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")
    p.add_argument("--action", choices=["start", "write", "land"], default="start")


def run(args):
    values, problems = crew_render.resolve(args.project, args.org_profile)
    if problems:
        print("\n".join(problems))
        return 1
    return 0 if require_ownership(values, args.action) else 1
