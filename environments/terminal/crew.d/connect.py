"""`mdstack connect` opens the owner's own shell on an inventory host, or reattaches-or-creates a tmux session there.

Usage: mdstack connect [--project FILE] [--org-profile FILE] ALIAS [SESSION] [-- TRANSPORT_ARGS...]

ALIAS is an inventory host name or its `connect.alias`. With SESSION it runs `tmux new-session -A -s SESSION` on the
host, so one command creates the session or reattaches it; without, a plain login shell. The transport (`ssh`, the
default, `mosh` or `et`), its proxy command and fixed options are profile data under `hosts.<name>.connect`
(docs/runtimes/multi-device.md#connect-to-a-host); words after ALIAS [SESSION] that start with `-` pass through to
the transport, so options for mdstack itself go before ALIAS. The destination is the host's `address`, else its label
(#1034). It replaces itself with the transport, under the owner's SSH config and keys, never the crew key's fixed
entrypoint. An unknown alias lists the known ones, exit 1.
"""
import argparse
import os
import re
import shlex
from crew_shared import commands, profile

SESSION = re.compile(r"[A-Za-z0-9_-]{1,64}")  # tmux turns "." and ":" in a session name into "_"


def register(sub):
    p = sub.add_parser("connect", help="open a shell or a tmux session on an inventory host")
    commands()["host"].options(p)
    p.add_argument("alias", help="inventory host name or its connect.alias")
    p.add_argument("words", nargs=argparse.REMAINDER, help="[SESSION] [-- TRANSPORT_ARGS...]")


def aliases(values):
    """Alias -> host for every inventory host: its name, plus its connect.alias when set."""
    host = commands()["host"]
    names = {name: name for name in host.inventory(values)}
    names.update({host.setting(values, n, "connect.alias"): n for n in host.inventory(values)
                  if host.setting(values, n, "connect.alias")})
    return names


def split(words):
    """(session or None, transport args) from the words after ALIAS."""
    session = None
    if words and not words[0].startswith("-"):
        session, words = words[0], words[1:]
    return session, words[1:] if words[:1] == ["--"] else words


def argv(values, host, session, extra):
    """The transport command line for host: transport, proxy, profile options, passed-through args, the host's
    address (else its label), then the reattach-or-create command when session is set."""
    get = lambda key, default=None: commands()["host"].setting(values, host, "connect." + key, default)
    dest = commands()["host"].address(values, host)
    transport, proxy, options = get("transport", "ssh"), get("proxy"), get("options", [])
    tmux = ["tmux", "new-session", "-A", "-s", session] if session else []
    if transport == "mosh":
        # mosh's default remote-IP discovery runs its own ProxyCommand, which a configured proxy replaces
        via = ["--ssh=ssh -o ProxyCommand=" + shlex.quote(proxy), "--experimental-remote-ip=remote"] if proxy else []
        return ["mosh", *via, *options, *extra, dest] + (["--", *tmux] if tmux else [])
    if transport == "et":  # et takes a ProxyCommand from the owner's SSH config; validate refuses connect.proxy
        return ["et", *options, *extra, dest] + (["-c", shlex.join(tmux)] if tmux else [])
    via = ["-o", "ProxyCommand=" + proxy] if proxy else []
    return ["ssh", *via, *options, *extra] + (["-t", dest, *tmux] if tmux else [dest])


def run(args):
    values, _, _ = profile(args, runtimes=("tmux", "session"))
    known = aliases(values)
    if args.alias not in known:
        print("crew connect: unknown host alias %s; known: %s" % (args.alias, ", ".join(sorted(known)) or "none"))
        return 1
    session, extra = split(args.words)
    if session is not None and not SESSION.fullmatch(session):
        print("crew connect: session name %r: expected [A-Za-z0-9_-], 1-64 characters" % session)
        return 1
    command = argv(values, known[args.alias], session, extra)
    os.execvp(command[0], command)
