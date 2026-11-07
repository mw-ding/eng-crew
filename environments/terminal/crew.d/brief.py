"""`mdstack brief` prints the "This run" block that ends a role brief, the same for every runtime and session backend
(#647): `mdstack spawn` appends it for tmux; a coordinator dispatching a hosted session appends this output.
Refuses (exit 2, nothing printed) when a required field (Item, Pass, Base) is missing or empty.

Usage: mdstack brief --item ITEM --pass PASS --base SHA [--round K] [--window NAME] [--slot S] [--host H]
                  [--worktree PATH] [--engine "ENGINE MODEL EFFORT"] [--claim PATH] [--flavor F] [--comments IDS]
"""

FIELDS = [("window", "Window"), ("item", "Item"), ("pass", "Pass"), ("round", "Round"), ("slot", "Slot"),
          ("host", "Host"), ("worktree", "Worktree"), ("base", "Base"), ("engine", "Engine"), ("claim", "Claim"),
          ("flavor", "Flavor"), ("comments", "Comments")]
REQUIRED = ("Item", "Pass", "Base")


def run_block(pairs):
    """The "## This run" block from (label, value) pairs in the caller's order; empty values are left out.
    Raises ValueError naming any missing REQUIRED label."""
    pairs = [(k, v) for k, v in pairs if v not in (None, "")]
    missing = [k for k in REQUIRED if k not in dict(pairs)]
    if missing:
        raise ValueError("crew: refusing run block: missing %s (required: %s)" % (", ".join(missing),
                                                                                  ", ".join(REQUIRED)))
    return "\n## This run\n\n" + "".join("- %s: %s\n" % kv for kv in pairs)


def register(sub):
    p = sub.add_parser("brief")
    for flag, label in FIELDS:
        p.add_argument("--" + flag, dest=flag, help="%s%s" % (label, " (required)" if label in REQUIRED else ""))


def run(args):
    try:
        print(run_block([(label, getattr(args, flag)) for flag, label in FIELDS]), end="")
    except ValueError as e:
        print(e)
        return 2
    return 0
