"""Harness adapter discovery (docs/runtimes/harness-adapters.md#adapter-modules). Python 3.11+ stdlib only.

Each harnesses/<engine>/adapter.py is one harness's adapter module, named by its profile engine id; _-prefixed
directories are not adapters. This module loads them once in sorted directory order and derives every engine table
the profile schema, crew commands and remote readiness consume, so adding a harness adds its adapter module and tests
only:

- ENGINES: every engine a tier order or pack capability may name, in ENGINE_RANK order;
- LAUNCHABLE: engines with an interactive launch (role_argv), in LAUNCH_RANK order: the coordinator choices and
  the engines crew spawn picks from;
- ENGINE_CMD and CLI: engine id -> executable, for the launchable engines and for every engine;
- RESUMABLE, INSTALLS, LAUNCH_NOTES and INSTALL_BUILTINS: coordinator resume support, bootstrap --harness choices,
  pack launch-note harnesses and the built-in install targets no pack pointer may claim.

An adapter with no rank sorts after the ranked ones, by engine id. Contributor-tier and engine-independence policy
stay in the crew core; an adapter receives only the result (the chosen engine, model and effort, and a launch only
after the core's checks pass)."""
import glob
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))  # harnesses/


def discover(directory):
    """The adapter modules in directory by engine id, <engine>/adapter.py, loaded in sorted directory order."""
    found = {}
    for path in sorted(glob.glob(os.path.join(directory, "[!_]*", "adapter.py"))):
        name = os.path.basename(os.path.dirname(path))
        spec = importlib.util.spec_from_file_location("crew_harness_" + name.replace("-", "_"), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        found[name] = mod
    return found


ADAPTERS = discover(HERE)


def ranked(names, key):
    return sorted(names, key=lambda n: (getattr(ADAPTERS[n], key, None) is None, getattr(ADAPTERS[n], key, 0), n))


ENGINES = ranked(ADAPTERS, "ENGINE_RANK")
LAUNCHABLE = ranked([n for n in ADAPTERS if hasattr(ADAPTERS[n], "role_argv")], "LAUNCH_RANK")
ENGINE_CMD = {n: ADAPTERS[n].EXECUTABLE for n in LAUNCHABLE}
CLI = {n: ADAPTERS[n].EXECUTABLE for n in ENGINES}
BY_EXECUTABLE = {ADAPTERS[n].EXECUTABLE: ADAPTERS[n] for n in LAUNCHABLE}
RESUMABLE = [n for n in LAUNCHABLE if getattr(ADAPTERS[n], "RESUME", None)]
INSTALLS = [n for n in LAUNCHABLE if hasattr(ADAPTERS[n], "install_targets") or hasattr(ADAPTERS[n], "install_launch")]
LAUNCH_NOTES = [n for n in INSTALLS if hasattr(ADAPTERS[n], "install_launch")]
INSTALL_BUILTINS = [t for n in INSTALLS for t in getattr(ADAPTERS[n], "INSTALL_TARGETS", [])]


def login_status(engine):
    """The read-only login check argv for an engine's CLI; an unknown engine is probed as `<engine> auth status`."""
    adapter = ADAPTERS.get(engine)
    return [CLI.get(engine, engine), *getattr(adapter, "LOGIN_STATUS", ["auth", "status"])]
