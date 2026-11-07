"""`crew pack` lists the connectors, harnesses, environment defaults and skills a project resolves, built-in and from
its installed pack, or runs the actions/ conformance kit against a pack (docs/packs.md#pack-plug-ins).

Usage: crew pack list --project FILE
       crew pack test DIR
"""
from crew_shared import load


def register(sub):
    p = sub.add_parser("pack", help="list pack plug-ins or run the conformance kit")
    p.add_argument("action", choices=("list", "test"))
    p.add_argument("dir", nargs="?", help="pack directory (test)")
    p.add_argument("--project", help="profile whose paths.pack is listed (list)")


def run(args):
    crew_pack = load("crew_pack", "core/crew-pack.py")
    if args.action == "test":
        if not args.dir:
            print("crew pack: test needs the pack directory")
            return 2
        return crew_pack.main(["test", args.dir])
    if not args.project:
        print("crew pack: list needs --project")
        return 2
    return crew_pack.main(["discover", "--project", args.project])
