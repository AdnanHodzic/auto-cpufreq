# Contributing to auto-cpufreq

Thanks for helping improve auto-cpufreq. Please open a GitHub issue or discussion for substantial behavioral changes, and keep pull requests focused on one purpose.

## Development

See [Development installation](README.md#installation-development-mode-only) for the supported installation methods. With Poetry:

```bash
poetry install
poetry run auto-cpufreq --help
```

For GTK development, install the optional GUI dependencies and start the application in a graphical session:

```bash
poetry install --extras gui
poetry run auto-cpufreq-gtk
```

Prefer a development environment over replacing a running system installation. Do not test privileged power-policy changes on a production machine without first reviewing their effects.

## Where to make changes

| Responsibility | Start here |
| --- | --- |
| Read-only hardware telemetry and `SystemReport` | `auto_cpufreq/modules/system_info.py` |
| Read-only governor/Turbo suggestion rules and Monitor recommendation states | `auto_cpufreq/modules/report_recommendations.py` |
| Shared report semantics (missing battery/sensors, platform profile, config, offline CPUs) | `auto_cpufreq/modules/report_presentation.py` |
| Cross-interface refresh concurrency | `auto_cpufreq/modules/report_refresh.py` |
| GTK report layout for dashboard and Monitor | `auto_cpufreq/gui/report_view.py` |
| GTK Monitor screen | `auto_cpufreq/gui/monitor_view.py` |
| Main GTK window, power-apply UI state and navigation | `auto_cpufreq/gui/app.py` |
| GTK controls, menus, dialogs and daemon actions | `auto_cpufreq/gui/objects.py` |
| Desktop integration (opening directories) | `auto_cpufreq/gui/desktop.py` |
| GTK scheduling and delivery | `auto_cpufreq/gui/refresh_timer.py`, `auto_cpufreq/gui/refresh_bridge.py` |
| Optional GTK debug preference and watchdog | `auto_cpufreq/gui/diagnostics.py` |
| Shared log session lifecycle and rotation | `auto_cpufreq/modules/diagnostics.py` |
| Process/CPU/thread health measurements | `auto_cpufreq/modules/process_health.py` |
| Terminal Stats, Monitor, Live display | `auto_cpufreq/modules/system_monitor.py` |
| CLI modes, installation and policy lifecycle | `auto_cpufreq/bin/auto_cpufreq.py`, `auto_cpufreq/power_helper.py` |
| Configuration parsing, atomic snapshot publication and lazy inotify watches | `auto_cpufreq/config/config.py`, `auto_cpufreq/config/file_watcher.py` |

The shared recommendation functions are the **only place to change the
governor/Turbo suggestion formulas**. `SystemInfo.governor_suggestion()`
and `SystemInfo.turbo_on_suggestion()` remain compatibility methods and
delegate to those rules. Do not make their behavior diverge from the read-only
GTK and terminal Monitor recommendations. Changes to the daemon's actual
power policy require a separate review.

New code should import `MonitorModeView` from `gui/monitor_view.py` and
`open_containing_folder` from `gui/desktop.py`. The old imports via
`gui/objects.py` remain usable for existing callers. The old unused GTK
statistics widgets were removed from `gui/objects.py`: they were not used
by any tracked application entrypoint and performed separate synchronous
collection. Avoid reintroducing a second sampling path.

## Configuration file watcher

`config.py` uses the external `inotify-simple` 2.0.1 dependency
(BSD-2-Clause) through a dedicated `ConfigFileWatcher`. The auto-cpufreq
project remains GPL-3.0-or-later. The observer is **lazy**: read-only GTK and Stats
initialize configuration data without starting an inotify thread or
allocating watcher file descriptors. Daemon, Monitor, and Live modes call
`config.notifier.start()` when needed and `config.stop_watching()`
during their existing exit paths.

Keep reloads atomic: malformed, unreadable or concurrently replaced
files must not publish partially parsed settings. Genuine deletion
restores defaults. The watcher handles close-write/rename, symlinks,
lost directories and event-queue overflow; stopped observers must release
resources, and unexpected watch errors must not spin at high CPU.
Changes to these contracts should be exercised without modifying
production configuration or power policy.

## Consistent report fields across GTK and Stats

Both frontends receive the same `SystemReport` data model. Do not duplicate
presentation rules in separate toolkit modules. `report_presentation.py`
defines semantic text and availability, including absent batteries, unavailable
temperature and frequency-limit measurements, absent governor data, offline
CPUs, config-file labels and platform-profile providers. `gui/report_view.py`
and `modules/system_monitor.py` only decide **where** and **how** to show
each field. `format_system_report()` in `system_info.py` preserves the historical
text labels (including `Platform profile status`, `Platform profile provider`
and the `Not available` fallback) but obtains profile status, available choices
and provider summaries from `present_platform_profile()` rather than
reinterpreting raw provider devices. Keep those existing text labels stable
unless a deliberate compatibility change is reviewed.

A **missing battery** is different from an unknown AC source. Hardware
collection in `SystemInfo.battery_info()` returns a `BatteryInfo` even when
no battery path is found: `is_present=False` marks physical absence,
while `is_ac_plugged=True` retains the existing daemon power-source fallback.
The shared `battery_present()` function determines which battery rows GTK
and Stats display. Older `BatteryInfo` objects omit `is_present` and
remain compatible (treated as present). Do not replace a missing battery
with `None` inside hardware collection or use presence to change daemon policy.
When changing this contract, verify behavior both with a detected
battery and without one; check the display in GTK and Stats.

When changing report fields, compare the same observed values across GTK,
Stats and the legacy text report. In particular, preserve consistent
meaning for missing values and for detected, partial, read-only and absent
platform-profile interfaces. Do not substitute fabricated defaults for
unknown hardware readings.

## Refresh behavior

Both GTK and terminal screens use the same `ReportRefreshCoordinator`. It collects a snapshot in a background worker and keeps at most one collector active per process. Each UI has its own event loop and must render widgets on its own UI thread.

- **Periodic ticks:** call `request_if_idle()`. If collection or delivery is in progress, skip the tick without queuing another sample.
- **Explicit requests:** call `request()`. These may coalesce a single follow-up sample when busy. The GTK dashboard also uses explicit requests to confirm power-control changes.
- **Completion:** the UI acknowledges the delivered report's generation, even when presentation or diagnostics fail. Closing a view invalidates pending delivery; blocked hardware reads cannot be forcibly terminated.
- **GTK:** `GtkRefreshTimer` owns its GLib source and `GtkRefreshBridge` schedules UI-thread delivery. **Urwid:** keep using `watch_pipe` and its own alarm loop.

Telemetry and recommendations must remain **read-only**. Only dedicated power-policy/control code should issue privileged writes or modify services. Do not collapse GTK's `Applying…` transaction state into ordinary periodic refresh state: it protects the UI from stale reports.

## Before submitting a pull request

Keep the change coherent, preserve CLI and GTK entrypoints, and avoid
unrelated dependency updates or formatting-only changes. Verify syntax in
an isolated checkout without touching the system-installed executable:

```bash
python -m compileall -q auto_cpufreq
```

For frontend changes, compare GTK and terminal Stats with the same machine
and check that the GUI remains responsive during repeated opening, closing
and refresh-interval changes. Verify optional diagnostics with logging
disabled and enabled, including unwritable log paths. Avoid exercising
privileged power controls on a production installation without reviewing
their effects first.

### Opt-in diagnostic logging

`gui/diagnostics.py` holds the GTK preference, but importing a GUI module
must **not** open logs or start diagnostic threads: GTK's entrypoint activates
saved logging when it attaches the GLib main loop. For the terminal, the
`--diagnostic-log` option is supported only with `--stats`, `--monitor`
and `--live`. It uses `modules/diagnostics.py`, and does not replace
the existing CLI `--debug` command. Keep logging read-only, bound its
resource usage, and handle missing or unwritable directories. Do not make
diagnostic I/O prevent the UI from updating or closing.

For changes to scheduling, include evidence that refresh requests do not overlap, old GTK/Urwid callbacks are cleaned up, and the view recovers after a failed collection. For power-policy changes, explain how temporary actions and competing services are restored on error or exit.

In the PR description, include what changed, why, how you tested it, and any relevant distro/kernel/CPU details. Include logs only after checking them for private paths and other sensitive information.
