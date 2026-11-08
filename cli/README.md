# cli

The command-line entry point. Part of the
[module layout](../docs/specs/team.md#4-target-module-layout).

## Contents

| File | Holds |
|---|---|
| `mdstack` | The CLI: bootstrap and doctor for every environment, and the terminal environment's operations |
| `crew` | Deprecated shim for the old name, kept for one release with a note on stderr (#1233) |

## How it plugs in

`mdstack` is thin: each subcommand is a module of the active environment,
found in sorted order, so adding a command adds files only. It holds no role
policy (dependency rule D8). Usage: the [terminal environment](../environments/terminal/README.md)
and `mdstack --help`; generic action subcommands follow the
[CLI contract](../actions/cli.md).
