"""Live inventory: declared capabilities, prepared projects, reachability and this crew's run load/cap.

Usage: crew hosts [--project FILE] [--org-profile FILE]

Uses host check's fixed-entrypoint SSH contract; the remote runner is supplied by #208. Unknown load is ?, never 0.
Primary readiness uses local doctor. Empty inventories print a header. No repairs or cache writes; exit 0 for a
valid inventory even when a host is unreachable or not ready. Projects are runner-reported prepared mirrors.
"""
from crew_shared import commands, profile


def register(sub):
    p = sub.add_parser("hosts", help="list host capabilities, projects, reachability and load")
    commands()["host"].options(p)


def run(args):
    values, session, state = profile(args)
    host = commands()["host"]
    print("HOST PRIMARY OS/ARCH DEVICES ENGINES ROLES PROJECTS REACHABILITY READY LOAD")
    for name in host.inventory(values):
        get = lambda key, default=None: host.setting(values, name, key, default)
        facts = host.inspect_host(args, values, session, state, name)
        print(name, "yes" if get("primary", False) else "no",
              get("capabilities.os") + "/" + get("capabilities.arch"),
              ",".join(get("capabilities.devices", [])) or "-", ",".join(get("capabilities.engines")),
              ",".join(get("roles", ["builder", "reviewer"])), ",".join(facts["projects"]) or "-",
              "reachable" if facts["reachable"] else "unreachable", "yes" if facts["ready"] else "no",
              "%s/%s" % (facts["load"], get("max_runs")))
    return 0
