import os
import sys
from queue import Empty, SimpleQueue
from threading import Thread
from typing import Callable
import urwid
import time
from .system_info import (
    SystemReport,
    format_platform_profile_summary,
    system_info,
)
from auto_cpufreq.config.config import config
from enum import Enum


class ViewType(str, Enum):
    STATS = "Stats"
    MONITOR = "Monitor"
    LIVE = "Live"

    def __str__(self) -> str:
        return self.value


class SystemMonitor:
    def __init__(self, type: ViewType, suggestion: bool = False):
        self.type: ViewType = type
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

        self.footer = urwid.AttrMap(
            urwid.Text(
                "Press Q or Ctrl+C to quit | Use ↑↓ or PageUp/PageDown to scroll",
                align="center",
            ),
            "footer",
        )

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
        self.suggestion = suggestion
        self.running = False
        self._refresh_pipe_fd: int | None = None
        self._alarm_handle = None
        self._refresh_results = SimpleQueue()

    def update(self, loop: urwid.MainLoop, user_data: dict) -> None:
        self._alarm_handle = None

        if not self.running:
            return

        Thread(target=self._collect_report, daemon=True).start()

    def _collect_report(self):
        try:
            report = system_info.generate_system_report()

            if self.suggestion:
                suggested_governor = system_info.governor_suggestion(report)
                suggested_turbo = system_info.turbo_on_suggestion(report)
            else:
                suggested_governor = None
                suggested_turbo = None

            result = (
                report,
                suggested_governor,
                suggested_turbo,
                None,
            )
        except Exception as exc:
            result = (None, None, None, exc)

        if not self.running:
            return

        self._refresh_results.put(result)

        wakeup_fd = self._refresh_pipe_fd
        if wakeup_fd is None:
            return

        try:
            os.write(wakeup_fd, b"1")
        except OSError:
            # The monitor may have been closed while collection
            # was still finishing.
            pass

    def _refresh_ready(self, _data):
        try:
            (
                report,
                suggested_governor,
                suggested_turbo,
                error,
            ) = self._refresh_results.get_nowait()
        except Empty:
            return True

        if error is not None:
            raise error

        if report is None:
            raise RuntimeError(
                "System monitor refresh completed without a report"
            )

        # Capture focus only now. The user may have scrolled while
        # the worker was collecting telemetry.
        if len(self.left_content) > 0:
            _, self.last_focus_left = self.left_listbox.get_focus()
            if self.last_focus_left is None:
                self.last_focus_left = 0

        if len(self.right_content) > 0:
            _, self.last_focus_right = self.right_listbox.get_focus()
            if self.last_focus_right is None:
                self.last_focus_right = 0

        current_time = time.strftime("%H:%M:%S")
        self.title_header.set_text(
            f"{self.type} Mode - {current_time}"
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

        if self.running:
            self._alarm_handle = self.loop.set_alarm_in(
                2,
                self.update,
            )

        return True

    def handle_input(self, key):
        if key in ("q", "Q"):
            raise urwid.ExitMainLoop()

    def format_system_info(
        self,
        report: SystemReport,
        suggested_governor: str | None = None,
        suggested_turbo: bool | None = None,
    ):
        self.left_content.clear()
        self.right_content.clear()

        # Helper function to create centered text
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

        if config.has_config():
            self.left_content.append(
                aligned_text(f"Using settings defined in {config.path} file")
            )
            self.left_content.append(aligned_text(""))

        # CPU Stats
        self.left_content.extend(
            [
                urwid.AttrMap(aligned_text("Current CPU Stats"), "header"),
                aligned_text(""),
                aligned_text(
                    f"CPU max frequency: {report.cpu_max_freq:.0f} MHz"
                    if report.cpu_max_freq is not None
                    else "CPU max frequency: Unknown"
                ),
                aligned_text(
                    f"CPU min frequency: {report.cpu_min_freq:.0f} MHz"
                    if report.cpu_min_freq is not None
                    else "CPU min frequency: Unknown"
                ),
                aligned_text(""),
                aligned_text("Core    Usage   Temperature     Frequency"),
            ]
        )

        for core in report.cores_info:
            temperature = (
                f"{core.temperature:>6.0f} °C"
                if core.temperature > 0
                else "     —"
            )
            frequency = (
                f"{core.frequency:>6.0f} MHz"
                if core.frequency > 0
                else "     —"
            )
            self.left_content.append(
                aligned_text(
                    f"CPU{core.id:<2}    {core.usage:>4.1f}%    "
                    f"{temperature}    {frequency}"
                )
            )

        if report.cpu_fan_speed is not None:
            self.left_content.append(aligned_text(""))
            self.left_content.append(
                aligned_text(f"CPU fan speed: {report.cpu_fan_speed} RPM")
            )

        # Right Column - Battery, Platform Profile, CPU Power State, and System Stats
        if report.battery_info is not None:
            self.right_content.extend(
                [
                    urwid.AttrMap(aligned_text("Battery Stats"), "header"),
                    aligned_text(f"Battery status: {str(report.battery_info)}"),
                    aligned_text(
                        f"Battery percentage: {(str(report.battery_info.battery_level) + '%') if report.battery_info.battery_level is not None else 'Unknown'}"
                    ),
                    aligned_text(
                        f'AC plugged: {("Yes" if report.battery_info.is_ac_plugged else "No") if report.battery_info.is_ac_plugged is not None else "Unknown"}'
                    ),
                    aligned_text(
                        f'Charging start threshold: {report.battery_info.charging_start_threshold if report.battery_info.is_ac_plugged is not None else "Unknown"}'
                    ),
                    aligned_text(
                        f'Charging stop threshold: {report.battery_info.charging_stop_threshold if report.battery_info.is_ac_plugged is not None else "Unknown"}'
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
                    f"Governor: {report.current_gov or 'Unknown'}"
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
            aligned_text(f"EPP: {report.current_epp or 'Unavailable'}")
        )
        self.right_content.append(
            aligned_text(f"EPB: {report.current_epb or 'Unavailable'}")
        )

        if report.current_hwp_dynamic_boost is not None:
            self.right_content.append(
                aligned_text(
                    f"HWP Dynamic Boost: {'On' if report.current_hwp_dynamic_boost else 'Off'}"
                )
            )

        if report.is_turbo_on[0] is not None:
            turbo_status = "On" if report.is_turbo_on[0] else "Off"
        elif report.is_turbo_on[1] is not None:
            turbo_status = (
                "Driver managed"
                if report.is_turbo_on[1]
                else "Unavailable"
            )
        else:
            turbo_status = "Unavailable"
        self.right_content.append(aligned_text(f"Turbo Boost: {turbo_status}"))

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

        avg_temp = report.cpu_avg_temp
        if avg_temp is None and report.cores_info:
            temperatures = [
                core.temperature
                for core in report.cores_info
                if core.temperature > 0
            ]
            if temperatures:
                avg_temp = sum(temperatures) / len(temperatures)

        if avg_temp is not None:
            self.right_content.append(
                aligned_text(f"Average CPU temperature: {avg_temp:.1f} °C")
            )

    def run(self, on_quit: Callable[[], None] | None = None):
        self.on_quit = on_quit
        self.running = True

        try:
            self._refresh_pipe_fd = self.loop.watch_pipe(
                self._refresh_ready
            )
            self._alarm_handle = self.loop.set_alarm_in(
                0,
                self.update,
            )
            self.loop.run()
        except KeyboardInterrupt:
            sys.exit(0)
        finally:
            self.running = False

            callback = self.on_quit
            self.on_quit = None

            try:
                alarm_handle = self._alarm_handle
                self._alarm_handle = None

                if alarm_handle is not None:
                    self.loop.remove_alarm(alarm_handle)

                wakeup_fd = self._refresh_pipe_fd
                self._refresh_pipe_fd = None

                if wakeup_fd is not None:
                    try:
                        self.loop.remove_watch_pipe(wakeup_fd)
                    finally:
                        try:
                            os.close(wakeup_fd)
                        except OSError:
                            pass
            finally:
                if callback:
                    callback()
