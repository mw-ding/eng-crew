# environments/terminal

The terminal environment: a local team in tmux (or herdr) sessions, the
lowest-latency environment and the reference implementation of the generic
actions. Binding: [runtimes/tmux.md](../../docs/runtimes/tmux.md).

## Contents

| Path | Holds |
|---|---|
| `crew.d/<command>.py` | One module per `mdstack` subcommand (watcher, router, leads, scheduler, spawn and kill, action, land, bootstrap, doctor, ...); `_shared.py` holds the shared helpers |
| `sessions/<backend>/adapter.py` | Session backend adapters (tmux, herdr), discovered by `crew-session.py` ([session backends](../../docs/runtimes/session-backends.md)) |
| `crew-session.py` | Session backend discovery and capability tables |
| `crew-proc.py` | Process and liveness helpers |
| `remote/crew-remote.py` | The hardened remote call and runner for multi-host placement ([multi-device](../../docs/runtimes/multi-device.md)) |

## How it plugs in

The [`cli/mdstack`](../../cli/README.md) entry point dispatches each command
to its `crew.d` module. Only this module names session backends, inboxes,
windows or the terminal's environment variables (dependency rule D5). The
session backend is chosen per host, with tmux as the fallback.
