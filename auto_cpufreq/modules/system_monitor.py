from __future__ import annotations

import os
import sys
from queue import Empty, SimpleQueue
from typing import Callable
import urwid
import time
from .system_info import (
    SystemReport,
    battery_power_label,
    format_platform_profile_summary,
    system_info,
)
from auto_cpufreq.config.config import config
from auto_cpufreq.modules.report_presentation import (
    present_report, configuration_file_text, offline_cpus_text,
    frequency_limit_text, battery_present,
)
from auto_cpufreq.modules.report_refresh import ReportRefreshCoordinator
from auto_cpufreq.modules.diagnostics import (
    SessionDiagnostics, cli_state_directory,
)
from enum import Enum


class ViewType(str, Enum):
    STATS = "Stats"
    MONITOR = "Monitor"
    LIVE = "Live"

    def __str__(self) -> str:
        return self.value


class SystemMonitor:
    def __init__(
        self, type: ViewType, suggestion: bool = False,
        diagnostic_log: bool = False,
        policy_status: Callable[[], str] | None = None,
    ):
        self.type: ViewType = type
        self._diagnostics = (
            SessionDiagnostics(
                component=type.name.lower(),
                state_dir=cli_state_directory(),
            )
            if diagnostic_log else None
        )
        self.title_header = urwid.Text(f"{type} Mode", align="center")
        self.header = urwid.Columns(
            [
                self.title_header,
            ]
        )

        # Create separate content walkers for left and right columns
        self.left_content = urwid.SimpleListWalker([])
        self.right_content = urwid.SimpleListWalker([])

        # Create listboxes for both columns
        self.left_listbox = urwid.ListBox(self.left_content)
        self.right_listbox = urwid.ListBox(self.right_content)

        # Create a columns widget with a vertical line (using box drawing character)
        self.columns = urwid.Columns(
            [
                ("weight", 1, self.left_listbox),
                (
                    "fixed",
                    1,
                    urwid.AttrMap(urwid.SolidFill("│"), "divider"),
                ),  # Vertical line # type: ignore
                ("weight", 1, self.right_listbox),
            ],
            dividechars=0,
        )

        self.footer_text = urwid.Text(
            "Press Q or Ctrl+C to quit | Use ↑↓ or PageUp/PageDown to scroll",
            align="center",
        )
        self.footer = urwid.AttrMap(self.footer_text, "footer")
        self._diagnostic_error_shown = 0

        self.frame = urwid.Frame(
            body=self.columns,
            header=urwid.AttrMap(self.header, "header"),
            footer=self.footer,
        )

        palette = [
            ("header", "white", "dark blue"),
            ("footer", "white", "dark green"),
            ("body", "white", "default"),
            ("divider", "light gray", "default"),  # Style for the vertical line
        ]

        if suggestion:
            palette.append(("suggestion", "yellow", "default"))

        self.loop = urwid.MainLoop(
            self.frame, palette=palette, unhandled_input=self.handle_input
        )

        self.last_focus_left = 0
        self.last_focus_right = 0
        self.on_quit: Callable[[], None] | None = None
        self._policy_status = policy_status
        self.suggestion = suggestion
        self.running = False
        self._refresh_pipe_fd: int | None = None
        self._alarm_handle = None
        self._refresh_results = SimpleQueue()
        self._pipe_delivery_error = None
        self._stalled_refresh_reported = False
        self._refresh_coordinator = ReportRefreshCoordinator(
            self._collect_report_data,
            self._dispatch_report_result,
            thread_name="urwid-report-refresh",
            on_dispatch_error=self._report_dispatch_error,
        )

    def update(self, loop: urwid.MainLoop, user_data: dict) -> None:
        self._alarm_handle = None
        if not self.running:
            return
        try:
            # A periodic tick also provides fallback delivery when the
            # worker's watch_pipe notification could not be written.
            self._refresh_ready(b"")
            age = self._refresh_coordinator.request_age_seconds()
            if age is None:
                self._stalled_refresh_reported = False
            elif age >= 20 and not self._stalled_refresh_reported:
                self._stalled_refresh_reported = True
                if self._diagnostics:
                    self._diagnostics.warning(
                        "Urwid collection/delivery pending for %.1fs; "
                        "keeping single-flight worker", age,
                    )
            # The coordinator atomically skips busy periodic cycles.
            self._refresh_coordinator.request_if_idle()
        except Exception as error:
            # An optional diagnostic backend or transient worker-start
            # failure must not permanently stop the terminal refresh loop.
            if self._diagnostics:
                try:
                    self._diagnostics.warning(
                        "Urwid periodic refresh failed: %s", error
                    )
                except Exception:
                    pass
        finally:
            if self.running and self._alarm_handle is None:
                self._alarm_handle = self.loop.set_alarm_in(2, self.update)

    def _collect_report_data(self):
        report = system_info.generate_system_report()
        if self.suggestion:
            recommendations = system_info.monitor_recommendations(report)
            suggested_governor = recommendations.governor.suggested
            suggested_turbo = recommendations.turbo.suggested
        else:
            suggested_governor = None
            suggested_turbo = None
        return report, suggested_governor, suggested_turbo

    def _report_dispatch_error(self, error):
        message = str(error)[:160]
        # A broken pipe may persist; one error per episode suffices.
        if message == self._pipe_delivery_error:
            return
        self._pipe_delivery_error = message
        if self._diagnostics:
            self._diagnostics.warning("Urwid report dispatch error: %s", error)

    def _dispatch_report_result(self, result):
        # Called in a worker. The Urwid watch_pipe callback owns UI updates.
        if not self.running:
            self._refresh_coordinator.acknowledge(result.generation)
            return
        wakeup_fd = self._refresh_pipe_fd
        if wakeup_fd is None:
            self._refresh_coordinator.acknowledge(result.generation)
            return
        self._refresh_results.put(result)
        try:
            os.write(wakeup_fd, b"1")
            self._pipe_delivery_error = None
        except OSError as error:
            # Keep the result in the queue. The periodic Urwid alarm will
            # deliver it even when the pipe's write end is unavailable.
            self._report_dispatch_error(error)

    def _surface_diagnostic_error(self):
        if not self._diagnostics:
            return
        count, message = self._diagnostics.error_status()
        if count <= self._diagnostic_error_shown or not message:
            return
        self._diagnostic_error_shown = count
        self.footer_text.set_text(
            "Diagnostic log write failure (check directory/permissions): "
            f"{message[:120]} | Press Q to quit"
        )

    def _refresh_ready(self, _data):
        try:
            result = self._refresh_results.get_nowait()
        except Empty:
            return True

        if not self._refresh_coordinator.is_current(result.generation):
            return True

        try:
            if self._pipe_delivery_error:
                self.footer_text.set_text(
                    "Report pipe unavailable; using periodic refresh: "
                    f"{self._pipe_delivery_error[:100]} | Press Q to quit"
                )
            if self._diagnostics:
                delivery_seconds = (
                    max(0.0, time.monotonic() - result.completed_at)
                    if result.completed_at else 0.0
                )
                self._diagnostics.info(
                    "Urwid refresh generation=%d queue=%.3fs "
                    "collect=%.3fs delivery=%.3fs",
                    result.generation, result.queue_seconds,
                    result.duration, delivery_seconds,
                )
            self._surface_diagnostic_error()
            if result.error is not None or result.report is None:
                message = str(
                    result.error or RuntimeError("No system report returned")
                )
                self.title_header.set_text(
                    f"{self.type} Mode - telemetry error: {message[:100]}"
                )
                if self._diagnostics:
                    self._diagnostics.warning(
                        "Telemetry collection error: %s", message
                    )
            else:
                report, suggested_governor, suggested_turbo = result.report
                self._display_report(
                    report, suggested_governor, suggested_turbo
                )
        except Exception as error:
            # Both display and diagnostic failures must preserve progress.
            try:
                self.title_header.set_text(
                    f"{self.type} Mode - display error: {str(error)[:100]}"
                )
                if self._diagnostics:
                    self._diagnostics.warning(
                        "Urwid report presentation failed: %s", error
                    )
            except Exception:
                # Logging or a broken widget must not crash the main loop.
                pass
        finally:
            # This acknowledgement is unconditional: even the logging sink
            # can fail while handling a successfully collected report.
            try:
                if self._diagnostics and result.requested_at:
                    self._diagnostics.info(
                        "Urwid end-to-end refresh generation=%d elapsed=%.3fs",
                        result.generation,
                        max(0.0, time.monotonic() - result.requested_at),
                    )
            except Exception:
                pass
            try:
                self._refresh_coordinator.acknowledge(result.generation)
                self._stalled_refresh_reported = False
            finally:
                try:
                    self._surface_diagnostic_error()
                except Exception:
                    pass

        if self.running and self._alarm_handle is None:
            self._alarm_handle = self.loop.set_alarm_in(2, self.update)
        return True

    def _display_report(self, report, suggested_governor, suggested_turbo):
        # Capture focus only now. The user may have scrolled while
        # the worker was collecting telemetry.
        if len(self.left_content) > 0:
            _, self.last_focus_left = self.left_listbox.body.get_focus()
            if self.last_focus_left is None:
                self.last_focus_left = 0

        if len(self.right_content) > 0:
            _, self.last_focus_right = self.right_listbox.body.get_focus()
            if self.last_focus_right is None:
                self.last_focus_right = 0

        current_time = time.strftime("%H:%M:%S")
        status_suffix = ""
        if self.type == ViewType.LIVE and self._policy_status is not None:
            try:
                policy_state = self._policy_status()
            except Exception:
                policy_state = "status unavailable"
            if policy_state != "running":
                status_suffix = " - POLICY " + policy_state
        self.title_header.set_text(
            f"{self.type} Mode - {current_time}{status_suffix}"
        )

        self.format_system_info(
            report,
            suggested_governor,
            suggested_turbo,
        )

        if len(self.left_content) > 0:
            self.left_listbox.set_focus(
                min(
                    self.last_focus_left,
                    len(self.left_content) - 1,
                )
            )

        if len(self.right_content) > 0:
            self.right_listbox.set_focus(
                min(
                    self.last_focus_right,
                    len(self.right_content) - 1,
                )
            )

    def handle_input(self, key):
        if key in ("q", "Q"):
            raise urwid.ExitMainLoop()

    def format_system_info(
        self,
        report: SystemReport,
        suggested_governor: str | None = None,
        suggested_turbo: bool | None = None,
    ):
        presentation = present_report(report)
        self.left_content.clear()
        self.right_content.clear()

        # Consistent left alignment in both independently scrollable columns.
        def aligned_text(text: str) -> urwid.Text:
            return urwid.Text(text, align="left")

        # Left Column - System Info and CPU Stats
        self.left_content.extend(
            [
                urwid.AttrMap(aligned_text("System Information"), "header"),
                aligned_text(""),
                aligned_text(f"Linux distro: {report.distro_name} {report.distro_ver}"),
                aligned_text(f"Linux kernel: {report.kernel_version}"),
                aligned_text(f"Processor: {report.processor_model}"),
                aligned_text(
                    f"Cores: {report.total_core}"
                    if report.total_core is not None
                    else "Cores: Unknown"
                ),
                aligned_text(f"Architecture: {report.arch}"),
                aligned_text(f"Driver: {report.cpu_driver}"),
                aligned_text(""),
            ]
        )

        self.left_content.append(
            aligned_text(
                configuration_file_text(config.path, config.has_config())
            )
        )
        self.left_content.append(aligned_text(""))

        # CPU Stats
        self.left_content.extend(
            [
                urwid.AttrMap(aligned_text("Current CPU Stats"), "header"),
                aligned_text(""),
                aligned_text(
                    "CPU max frequency: "
                    + frequency_limit_text(report.cpu_max_freq)
                ),
                aligned_text(
                    "CPU min frequency: "
                    + frequency_limit_text(report.cpu_min_freq)
                ),
                aligned_text(""),
                aligned_text("Core   Usage  Temp  Freq (MHz)"),
            ]
        )

        for core in report.cores_info:
            temperature = (
                f"{core.temperature:.0f}°C"
                if core.temperature > 0
                else "—"
            )
            frequency = (
                f"{core.frequency:.0f}"
                if core.frequency > 0
                else "—"
            )
            self.left_content.append(
                aligned_text(
                    f"CPU{core.id:<2} {core.usage:>5.1f}%  "
                    f"{temperature:>4}  {frequency:>4}"
                )
            )

        offline_text = offline_cpus_text(report.offline_cpus)
        if offline_text:
            self.left_content.append(aligned_text(""))
            self.left_content.append(aligned_text(offline_text))

        if report.cpu_fan_speed is not None:
            self.left_content.append(aligned_text(""))
            self.left_content.append(
                aligned_text(f"CPU fan speed: {report.cpu_fan_speed} RPM")
            )

        # Right Column - Battery, Platform Profile, CPU Power State, and System Stats
        if battery_present(report.battery_info):
            self.right_content.extend(
                [
                    urwid.AttrMap(aligned_text("Battery Stats"), "header"),
                    aligned_text(f"Battery status: {presentation.battery.status.text}"),
                    aligned_text(
                        f"Battery percentage: {presentation.battery.level.text}"
                    ),
                    aligned_text(
                        f"AC plugged: {presentation.battery.ac.text}"
                    ),
                    aligned_text(
                        "Charging start threshold: "
                        f"{presentation.battery.charge_start.text}"
                    ),
                    aligned_text(
                        "Charging stop threshold: "
                        f"{presentation.battery.charge_stop.text}"
                    ),
                    aligned_text(
                        f"{battery_power_label(report.battery_info)}: "
                        + presentation.battery.power_watts.text
                    ),
                    aligned_text(""),
                ]
            )

        else:
            self.right_content.extend(
                [
                    urwid.AttrMap(aligned_text("Battery Stats"), "header"),
                    aligned_text(
                        f"Battery status: {presentation.battery.status.text}"
                    ),
                    aligned_text(""),
                ]
            )

        # Platform Profile
        self.right_content.append(
            urwid.AttrMap(aligned_text("Platform Profile"), "header")
        )
        for line in format_platform_profile_summary(report.platform_profile):
            self.right_content.append(aligned_text(line))
        self.right_content.append(aligned_text(""))

        # CPU Power State
        self.right_content.extend(
            [
                urwid.AttrMap(aligned_text("CPU Power State"), "header"),
                aligned_text(
                    f"Governor: {presentation.governor.text}"
                ),
            ]
        )

        if (
            self.suggestion
            and report.current_gov is not None
            and suggested_governor is not None
            and suggested_governor != report.current_gov
        ):
            self.right_content.append(
                urwid.AttrMap(
                    aligned_text(f"Suggested governor: {suggested_governor}"),
                    "suggestion",
                )
            )

        self.right_content.append(
            aligned_text(f"EPP: {presentation.epp.text}")
        )
        self.right_content.append(
            aligned_text(f"EPB: {presentation.epb.text}")
        )

        if report.current_hwp_dynamic_boost is not None:
            self.right_content.append(
                aligned_text(
                    f"HWP Dynamic Boost: {presentation.hwp_dynamic_boost.text}"
                )
            )

        self.right_content.append(
            aligned_text(f"Turbo Boost: {presentation.turbo.text}")
        )

        if (
            self.suggestion
            and report.is_turbo_on[0] is not None
            and suggested_turbo is not None
            and suggested_turbo != report.is_turbo_on[0]
        ):
            self.right_content.append(
                urwid.AttrMap(
                    aligned_text(
                        f"Suggested Turbo Boost: {'On' if suggested_turbo else 'Off'}"
                    ),
                    "suggestion",
                )
            )

        self.right_content.append(aligned_text(""))

        # System Statistics
        self.right_content.extend(
            [
                urwid.AttrMap(aligned_text("System Statistics"), "header"),
                aligned_text(f"CPU usage: {report.cpu_usage:.1f}%"),
                aligned_text(f"System load: {report.load:.2f}"),
            ]
        )

        if report.avg_load:
            self.right_content.append(
                aligned_text(
                    "Load average: "
                    f"{report.avg_load[0]:.2f} / "
                    f"{report.avg_load[1]:.2f} / "
                    f"{report.avg_load[2]:.2f}"
                )
            )

        self.right_content.append(
            aligned_text(
                "Average CPU temperature: "
                f"{presentation.average_temperature.text}"
            )
        )

    def run(self, on_quit: Callable[[], None] | None = None):
        self.on_quit = on_quit
        self.running = True

        try:
            if self._diagnostics:
                try:
                    self._diagnostics._activate()
                except (OSError, RuntimeError) as error:
                    # Diagnostics are optional; a non-writable log
                    # destination must not prevent telemetry display.
                    self._diagnostics._report_error(error)
                    self._surface_diagnostic_error()
                else:
                    self._diagnostics.info(
                        "%s UI started; terminal PID=%d",
                        self.type, os.getpid(),
                    )
            self._refresh_pipe_fd = self.loop.watch_pipe(
                self._refresh_ready
            )
            # A full or orphaned watch pipe must never block the collector.
            os.set_blocking(self._refresh_pipe_fd, False)
            self._alarm_handle = self.loop.set_alarm_in(
                0,
                self.update,
            )
            self.loop.run()
        except KeyboardInterrupt:
            # Logging is optional, including during signal handling.
            if self._diagnostics:
                try:
                    self._diagnostics.info("Terminal interrupted by Ctrl+C")
                except Exception:
                    pass
            sys.exit(0)
        finally:
            self.running = False
            callback, self.on_quit = self.on_quit, None

            # Release each resource even when a different cleanup step
            # fails. Diagnostics must not interfere with closing the
            # coordinator, alarm or watched pipe.
            try:
                try:
                    self._refresh_coordinator.close()
                finally:
                    alarm_handle, self._alarm_handle = self._alarm_handle, None
                    try:
                        if alarm_handle is not None:
                            self.loop.remove_alarm(alarm_handle)
                    finally:
                        wakeup_fd, self._refresh_pipe_fd = (
                            self._refresh_pipe_fd, None
                        )
                        if wakeup_fd is not None:
                            try:
                                self.loop.remove_watch_pipe(wakeup_fd)
                            finally:
                                try:
                                    os.close(wakeup_fd)
                                except OSError:
                                    pass
            finally:
                try:
                    if callback:
                        callback()
                finally:
                    if self._diagnostics:
                        try:
                            self._diagnostics.info("%s UI stopped", self.type)
                        except Exception:
                            pass
                        try:
                            self._diagnostics.shutdown()
                        except Exception:
                            pass
