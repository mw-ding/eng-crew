"""Harness adapter discovery (docs/runtimes/harness-adapters.md#adapter-modules). Python 3.11+ stdlib only.

Each harnesses/<engine>/adapter.py is one harness's adapter module, named by its profile engine id; _-prefixed
directories are not adapters. This module loads them once in sorted directory order and derives every engine table
the profile schema, crew commands and remote readiness consume, so adding a harness adds its adapter module and tests
only:

- ENGINES: every engine a tier order or pack capability may name, in ENGINE_RANK order;
- LAUNCHABLE: engines with an interactive launch (role_argv), in LAUNCH_RANK order: the coordinator choices and
  the engines mdstack spawn picks from;
- ENGINE_CMD and CLI: engine id -> executable, for the launchable engines and for every engine;
- RESUMABLE, INSTALLS, LAUNCH_NOTES and INSTALL_BUILTINS: coordinator resume support, bootstrap --harness choices,
  pack launch-note harnesses and the built-in install targets no pack pointer may claim.

add() registers an installed pack's adapters (docs/packs.md#pack-plug-ins), loaded by the same discover(); they join
every table but INSTALLS, which stays the built-in bootstrap --harness choices.

An adapter with no rank sorts after the ranked ones, by engine id. Contributor-tier and engine-independence policy
stay in the crew core; an adapter receives only the result (the chosen engine, model and effort, and a launch only
after the core's checks pass)."""
import glob
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))  # harnesses/


def discover(directory, legacy=None):
    """The adapter modules in directory by engine id, <engine>/adapter.py, loaded in sorted name order. For one release
    (#1222) a <name>.py in the legacy directory (the old scripts/ layout) is an adapter too, unless the new layout has
    that name or the file is a compatibility shim."""
    paths = {os.path.basename(os.path.dirname(p)): p for p in glob.glob(os.path.join(directory, "[!_]*", "adapter.py"))}
    for path in glob.glob(os.path.join(legacy, "[!_]*.py")) if legacy else []:
        with open(path, encoding="utf-8") as f:
            shim = "Compatibility shim: this file moved to" in f.read(200)
        paths.setdefault(os.path.basename(path)[:-3], None if shim else path)
    found = {}
    for name, path in sorted((n, p) for n, p in paths.items() if p):
        spec = importlib.util.spec_from_file_location("crew_harness_" + name.replace("-", "_"), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        found[name] = mod
    return found


LEGACY = os.path.join(os.path.dirname(HERE), "scripts", "harness.d")  # the old layout, one release
ADAPTERS = discover(HERE, LEGACY)


def ranked(names, key):
    return sorted(names, key=lambda n: (getattr(ADAPTERS[n], key, None) is None, getattr(ADAPTERS[n], key, 0), n))


ENGINES, LAUNCHABLE, RESUMABLE, INSTALLS, LAUNCH_NOTES, INSTALL_BUILTINS = [], [], [], [], [], []
ENGINE_CMD, CLI, BY_EXECUTABLE = {}, {}, {}
PACKED = {}  # engine id -> adapter file, for adapters a pack added (add)


def tables():
    """Derive every engine table from ADAPTERS, in place, so a module that bound a table by name sees an added pack."""
    ENGINES[:] = ranked(ADAPTERS, "ENGINE_RANK")
    LAUNCHABLE[:] = ranked([n for n in ADAPTERS if hasattr(ADAPTERS[n], "role_argv")], "LAUNCH_RANK")
    for table, items in ((ENGINE_CMD, {n: ADAPTERS[n].EXECUTABLE for n in LAUNCHABLE}),
                         (CLI, {n: ADAPTERS[n].EXECUTABLE for n in ENGINES}),
                         (BY_EXECUTABLE, {ADAPTERS[n].EXECUTABLE: ADAPTERS[n] for n in LAUNCHABLE})):
        table.clear()
        table.update(items)
    RESUMABLE[:] = [n for n in LAUNCHABLE if getattr(ADAPTERS[n], "RESUME", None)]
    INSTALLS[:] = [n for n in LAUNCHABLE if n not in PACKED and (
        hasattr(ADAPTERS[n], "install_targets") or hasattr(ADAPTERS[n], "install_launch"))]
    LAUNCH_NOTES[:] = [n for n in INSTALLS if hasattr(ADAPTERS[n], "install_launch")]
    INSTALL_BUILTINS[:] = [t for n in INSTALLS for t in getattr(ADAPTERS[n], "INSTALL_TARGETS", [])]


def add(found):
    """Register a pack's harness adapters (core/crew-pack.py) beside the built-ins, through the same discover() and
    tables. A built-in's name is a ValueError; a name a pack added before is replaced (one pack resolves at a time)."""
    for name, mod in found.items():
        if name in ADAPTERS and name not in PACKED:
            raise ValueError("pack harness %r shadows a built-in adapter" % name)
    for name, mod in found.items():
        ADAPTERS[name], PACKED[name] = mod, mod.__file__
    tables()


tables()


def login_status(engine):
    """The read-only login check argv for an engine's CLI; an unknown engine is probed as `<engine> auth status`."""
    adapter = ADAPTERS.get(engine)
    return [CLI.get(engine, engine), *getattr(adapter, "LOGIN_STATUS", ["auth", "status"])]
