"""Upgrade a tmux install from this bundle (or --version), previewing before restarting roles.

Usage: crew upgrade --project FILE [--version vX.Y.Z] [--dry-run] [--yes]
                     [--wait-timeout SECONDS] [--timeout SECONDS]

Run from a separate operator terminal with dispatch paused. Waits for every current pass to finish
before applying; a timeout leaves the install and sessions untouched. Restarts preserve worktrees,
claims, inboxes and run metadata. Coordinator is last. Grok Bot routine reload remains manual.
"""
from argparse import Namespace
import json
from pathlib import Path
import shlex
import re
import tempfile
import time
from crew_shared import (
    brief_src, codex_trust, commands, crew_render, ENGINE_CMD, harness, identity, LAUNCH, POINTER,
    profile, require_ownership, role_notes, runs, stop_pane, tmux, wait_harness, window_env)


def register(sub):
    p = commands()["bootstrap"].register(sub, "upgrade")
    p.add_argument("--wait-timeout", type=float, default=300)
    p.add_argument("--timeout", type=float, default=15)


def busy(state, session, windows):
    records = dict(runs(state))
    leads = dict(commands()["lead"].records(state))
    for index, name in windows:
        if index != 0 and name not in records and name not in leads:
            return name
        path = Path(state) / "status" / (name + ".status")
        lines = [s for s in path.read_text().splitlines() if not s.startswith("heartbeat:")] if path.exists() else []
        if name in records and (not lines or not lines[-1].startswith(("done:", "blocked:", "failed:"))):
            return name
        if name in leads and commands()["lead"].pending(state, name):
            return name
        pane = tmux.pane(session, index)
        screen = tmux.capture(session, index).lower()
        if not pane or tmux.live_child(pane["pid"], pane["command"]) or "esc to interrupt" in screen or re.search(
                r"(?m)^[✽✻✶✢·*] .+… \([^\n]+\)", screen):
            return name
    return None


def reload(values, session, state, args, windows):
    records = dict(runs(state))
    leads = dict(commands()["lead"].records(state))
    for index, name in sorted(windows, key=lambda w: w[0] == 0):
        rec = records.get(name) or leads.get(name)
        role = rec["role"].removesuffix("-lead") if rec else "coordinator"
        src = Path(brief_src(state, role))
        if name in leads:
            src = Path(state) / "render/runtime" / (role + "-lead.md")
        brief = Path(state) / "runs" / (name + ".brief.md") if name in records else (
            Path(state) / "leads" / (role + ".brief.md") if name in leads else Path(state) / "coordinator.brief.md")
        tail = ""
        if name in records:
            before = brief.read_text()
            _, separator, tail = before.partition("\n## This run\n")
            if not separator:
                raise ValueError("missing run metadata: " + str(brief))
            tail = separator + tail.split("\n## Runtime note:", 1)[0]
        text = src.read_text() + tail + role_notes(values, state, role)
        if stop_pane(session, index):
            raise RuntimeError("process group survived stop: " + name)
        brief.write_text(text)
        cwd = (rec.get("worktree") if rec else None) or str(Path(args.project).absolute().parent)
        engine, model, effort = (rec["engine"], rec["model"], rec["effort"]) if name in records else (
            commands()["spawn"].pick_engine(values, "default") if name in leads else
            (values["engines.coordinator"], "", ""))
        argv = harness(engine, model, effort, cwd, state, values["runtime.options.permission_mode"]) if rec or engine == "pi" else (
            ["claude"] if engine == "claude-code" else ["codex", "-c", codex_trust(cwd)])
        env = window_env(values, state, role, name, str(brief), args.project)
        if name in leads:
            env.update(CREW_ROLE=role + "-lead", CREW_POOL=role)
        flags = [x for k, v in env.items() for x in ("-e", "%s=%s" % (k, v))]
        result = tmux.tmux("respawn-window", "-k", "-t", "=%s:%d" % (session, index), "-c", cwd,
                           *flags, LAUNCH % (shlex.join(argv), POINTER))
        if result.returncode:
            raise RuntimeError("reload failed: " + result.stderr.strip())
        wait_harness(session, index, name, ENGINE_CMD[engine], args.timeout)
        if rec:
            rec.update(identity(session, index))
            path = Path(state) / "runs" / (name + ".json") if name in records else Path(
                commands()["lead"].record_path(state, role))
            path.write_text(json.dumps(rec, indent=2) + "\n")
        print("crew upgrade: reloaded " + name)


def run(args):
    bootstrap = commands()["bootstrap"]
    try:
        if args.uninstall or args.remove_labels or args.routines_removed or args.smoke:
            raise ValueError("use crew bootstrap for uninstall or smoke")
        values, session, state = profile(args)
        if values.get("runtime.options.session_backend") == "herdr":
            raise ValueError("herdr: in-place upgrade unsupported; stop the crew and restart the updated install")
        if not require_ownership(values):
            return 1
        if args.version:
            if args.dev:
                raise ValueError("--version and --dev cannot be combined")
            return bootstrap.fetch(args)
        manifest = Path(state) / "install.json"
        if not manifest.exists():
            raise ValueError("no install; run crew bootstrap first")
        tag = bootstrap.source(args.dev, args.pre)
        bootstrap.pack_pin(args.org_profile, tag)
        previous = json.loads(manifest.read_text())
        with tempfile.TemporaryDirectory(prefix="crew-upgrade-") as tmp:
            argv = ["--project", args.project, "--out", tmp] + (["--org-profile", args.org_profile] if args.org_profile else [])
            if crew_render.main(argv):
                return 1
            if bootstrap.size_budget(tmp, values):
                return 1
            desired = {p.relative_to(tmp): p.read_bytes() for p in Path(tmp).rglob("*") if p.is_file()}
            live = Path(state) / "render"
            actual = {p.relative_to(live): p.read_bytes() for p in live.rglob("*") if p.is_file()}
            if (desired == actual and previous["tag"] == tag
                    and previous["source"] == str(bootstrap.ROOT)
                    and (Path(state) / "crew.toml").read_bytes() == Path(args.project).read_bytes()):
                print("crew upgrade: no changes")
                return 0
            if bootstrap.run(Namespace(**{**vars(args), "dry_run": True})):
                return 1
            if args.dry_run:
                return 0
            if not args.yes:
                raise ValueError("confirmation required; review --dry-run then use --yes")
            deadline = time.monotonic() + args.wait_timeout
            while active := busy(state, session, tmux.list_windows(session)):
                if time.monotonic() >= deadline:
                    raise ValueError("in-flight pass " + active + "; wait timed out; no install written")
                time.sleep(0.2)
            windows = tmux.list_windows(session)
            if not require_ownership(values) or bootstrap.run(args):
                return 1
            reload(values, session, state, args, windows)
        return 0
    except (OSError, ValueError, RuntimeError) as e:
        print("crew upgrade: " + str(e))
        return 1
