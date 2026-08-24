import gi
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from contextlib import redirect_stdout
from io import StringIO
from os.path import isfile
from subprocess import PIPE, run
from threading import Thread

from auto_cpufreq.config.config import config, find_config_file
from auto_cpufreq.core import check_for_update, daemon_is_running
from auto_cpufreq.globals import GITHUB, IS_INSTALLED_WITH_SNAP
from auto_cpufreq.gui.objects import BluetoothBootControl, DaemonNotRunningView, DropDownMenu, MonitorModeView, RadioButtonView, CPUTurboOverride, UpdateDialog
from auto_cpufreq.gui.objects import get_stats
from auto_cpufreq.modules.system_info import system_info
from auto_cpufreq.power_helper import bluetoothctl_exists

if IS_INSTALLED_WITH_SNAP:
    CSS_FILE = "/snap/auto-cpufreq/current/style.css"
    ICON_FILE = "/snap/auto-cpufreq/current/icon.png"
else:
    CSS_FILE = "/usr/local/share/auto-cpufreq/scripts/style.css"
    ICON_FILE = "/usr/local/share/auto-cpufreq/images/icon.png"

HBOX_PADDING = 20
CONTROL_OPTION_MARGIN = 8
SECTION_SPACING = 12

DEFAULT_REFRESH_INTERVAL = 2
REFRESH_INTERVALS = (1, 2, 5)

# The daemon normally applies overrides on its next ~2 second cycle.
# Keep the affected state hidden until a later, fresh report is collected.
CONTROL_APPLY_DELAY_SECONDS = 3


def _new_section(title):
    frame = Gtk.Frame()
    heading = Gtk.Label(label=title, name="bold")
    heading.set_halign(Gtk.Align.START)
    frame.set_label_widget(heading)

    grid = Gtk.Grid()
    grid.set_column_spacing(18)
    grid.set_row_spacing(4)
    grid.set_margin_top(8)
    grid.set_margin_bottom(8)
    grid.set_margin_start(10)
    grid.set_margin_end(10)
    frame.add(grid)
    return frame, grid


def _add_row(grid, row, name):
    name_label = Gtk.Label(label=name)
    name_label.set_halign(Gtk.Align.START)
    name_label.set_xalign(0)

    value_label = Gtk.Label(label="—")
    value_label.set_halign(Gtk.Align.START)
    value_label.set_xalign(0)
    value_label.set_hexpand(True)

    grid.attach(name_label, 0, row, 1, 1)
    grid.attach(value_label, 1, row, 1, 1)
    return name_label, value_label


def _set_row_visible(grid, row, visible):
    for column in (0, 1):
        child = grid.get_child_at(column, row)
        if child is None:
            continue
        child.set_no_show_all(True)
        if visible:
            child.show()
        else:
            child.hide()


def _battery_status(battery):
    if battery is None:
        return "Unavailable"
    if battery.is_charging is True:
        return "Charging"
    if battery.is_ac_plugged is False:
        return "Discharging"
    if battery.is_ac_plugged is True:
        return "Not charging"
    return "Unknown"


def _governor_status(report):
    return report.current_gov or "Unavailable"


def _turbo_status(report):
    enabled, driver_managed = report.is_turbo_on

    if enabled is None:
        if driver_managed is True:
            return "Driver managed"
        return "Unavailable"

    return "On" if enabled else "Off"


class SystemReportView(Gtk.Box):
    """Shared read-only presentation of SystemReport."""

    def __init__(self):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
        )

        self.columns = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=HBOX_PADDING,
        )
        self.left_column = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=SECTION_SPACING,
        )
        self.left_column.set_valign(Gtk.Align.START)
        self.columns.pack_start(self.left_column, True, True, 0)

        system_frame, system_grid = _new_section("System Information")
        self.system_values = {}
        for row, (key, name) in enumerate(
            (
                ("distro", "Linux distro"),
                ("kernel", "Linux kernel"),
                ("processor", "Processor"),
                ("cores", "Logical CPUs"),
                ("architecture", "Architecture"),
                ("driver", "CPU driver"),
            )
        ):
            _, self.system_values[key] = _add_row(system_grid, row, name)
        self.left_column.pack_start(system_frame, False, False, 0)

        self.config_label = Gtk.Label(label="")
        self.config_label.set_halign(Gtk.Align.START)
        self.config_label.set_xalign(0)
        self.config_label.set_line_wrap(True)
        self.left_column.pack_start(self.config_label, False, False, 0)

        cpu_frame = Gtk.Frame()
        cpu_heading = Gtk.Label(label="CPU Statistics", name="bold")
        cpu_heading.set_halign(Gtk.Align.START)
        cpu_frame.set_label_widget(cpu_heading)

        self.cpu_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )
        self.cpu_box.set_margin_top(8)
        self.cpu_box.set_margin_bottom(8)
        self.cpu_box.set_margin_start(10)
        self.cpu_box.set_margin_end(10)
        cpu_frame.add(self.cpu_box)

        limits_grid = Gtk.Grid()
        limits_grid.set_column_spacing(18)
        limits_grid.set_row_spacing(4)
        _, self.max_freq_value = _add_row(
            limits_grid, 0, "Maximum frequency"
        )
        _, self.min_freq_value = _add_row(
            limits_grid, 1, "Minimum frequency"
        )
        self.cpu_box.pack_start(limits_grid, False, False, 0)

        self.cores_grid = Gtk.Grid()
        self.cores_grid.set_column_spacing(18)
        self.cores_grid.set_row_spacing(3)
        self.cpu_box.pack_start(self.cores_grid, False, False, 0)

        self.fan_label = Gtk.Label(label="")
        self.fan_label.set_halign(Gtk.Align.START)
        self.fan_label.set_xalign(0)
        self.fan_label.set_no_show_all(True)
        self.cpu_box.pack_start(self.fan_label, False, False, 0)

        self.left_column.pack_start(cpu_frame, False, False, 0)

        self.right_column = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=SECTION_SPACING,
        )
        self.right_column.set_valign(Gtk.Align.START)
        self.columns.pack_start(self.right_column, True, True, 0)

        power_frame, self.power_grid = _new_section("CPU Power State")
        self.power_values = {}
        for row, (key, name) in enumerate(
            (
                ("governor", "Governor"),
                ("epp", "EPP"),
                ("epb", "EPB"),
                ("hwp", "HWP Dynamic Boost"),
                ("turbo", "Turbo Boost"),
            )
        ):
            _, self.power_values[key] = _add_row(
                self.power_grid, row, name
            )
        _set_row_visible(self.power_grid, 3, False)
        self.right_column.pack_start(power_frame, False, False, 0)

        battery_frame, self.battery_grid = _new_section("Battery")
        self.battery_values = {}
        for row, (key, name) in enumerate(
            (
                ("status", "Status"),
                ("charge", "Charge"),
                ("ac", "AC power"),
                ("start", "Start threshold"),
                ("stop", "Stop threshold"),
                ("power", "Power draw"),
            )
        ):
            _, self.battery_values[key] = _add_row(
                self.battery_grid, row, name
            )
        self.right_column.pack_start(battery_frame, False, False, 0)

        stats_frame, stats_grid = _new_section("System Statistics")
        self.stats_values = {}
        for row, (key, name) in enumerate(
            (
                ("usage", "CPU usage"),
                ("load", "System load"),
                ("load_avg", "Load average (1 / 5 / 15 min)"),
                ("temp", "Average CPU temperature"),
            )
        ):
            _, self.stats_values[key] = _add_row(stats_grid, row, name)
        self.right_column.pack_start(stats_frame, False, False, 0)

        self.pack_start(self.columns, True, True, 0)

    def prepend_right(self, widget):
        self.right_column.pack_start(
            widget, False, False, 0
        )
        self.right_column.reorder_child(widget, 0)

    def _refresh_core_rows(self, cores):
        for child in self.cores_grid.get_children():
            self.cores_grid.remove(child)

        for column, text in enumerate(
            ("CPU", "Usage", "Temperature", "Frequency")
        ):
            label = Gtk.Label(label=text, name="bold")
            label.set_halign(Gtk.Align.START)
            label.set_xalign(0)
            self.cores_grid.attach(label, column, 0, 1, 1)

        for row, core in enumerate(cores, start=1):
            values = (
                f"CPU{core.id}",
                f"{core.usage:.1f}%",
                (
                    f"{core.temperature:.0f} °C"
                    if core.temperature > 0
                    else "—"
                ),
                (
                    f"{core.frequency:.0f} MHz"
                    if core.frequency > 0
                    else "—"
                ),
            )
            for column, text in enumerate(values):
                label = Gtk.Label(label=text)
                label.set_halign(Gtk.Align.START)
                label.set_xalign(0)
                self.cores_grid.attach(label, column, row, 1, 1)

        self.cores_grid.show_all()

    def apply_report(self, report, pending_power_updates=()):
        self.system_values["distro"].set_text(
            f"{report.distro_name} {report.distro_ver}".strip()
        )
        self.system_values["kernel"].set_text(
            report.kernel_version or "Unknown"
        )
        self.system_values["processor"].set_text(
            report.processor_model or "Unknown"
        )
        self.system_values["cores"].set_text(
            str(report.total_core)
            if report.total_core is not None
            else "Unknown"
        )
        self.system_values["architecture"].set_text(
            report.arch or "Unknown"
        )
        self.system_values["driver"].set_text(
            report.cpu_driver or "Unknown"
        )

        config_path = config.path if config.has_config() else find_config_file(None)
        if config_path and isfile(config_path):
            self.config_label.set_text(f"Configuration: {config_path}")
            self.config_label.show()
        else:
            self.config_label.hide()

        self.max_freq_value.set_text(
            f"{report.cpu_max_freq:.0f} MHz"
            if report.cpu_max_freq is not None
            else "Unavailable"
        )
        self.min_freq_value.set_text(
            f"{report.cpu_min_freq:.0f} MHz"
            if report.cpu_min_freq is not None
            else "Unavailable"
        )
        self._refresh_core_rows(report.cores_info)

        if report.cpu_fan_speed:
            self.fan_label.set_text(
                f"CPU fan speed: {report.cpu_fan_speed} RPM"
            )
            self.fan_label.show()
        else:
            self.fan_label.hide()

        if "governor" not in pending_power_updates:
            self.power_values["governor"].set_text(
                _governor_status(report)
            )
        self.power_values["epp"].set_text(
            report.current_epp or "Unavailable"
        )
        self.power_values["epb"].set_text(
            report.current_epb or "Unavailable"
        )

        hwp_available = report.current_hwp_dynamic_boost is not None
        _set_row_visible(self.power_grid, 3, hwp_available)
        if hwp_available:
            self.power_values["hwp"].set_text(
                "On" if report.current_hwp_dynamic_boost else "Off"
            )

        if "turbo" not in pending_power_updates:
            self.power_values["turbo"].set_text(
                _turbo_status(report)
            )

        battery = report.battery_info
        self.battery_values["status"].set_text(
            _battery_status(battery)
        )
        if battery is None:
            for key in ("charge", "ac", "start", "stop", "power"):
                self.battery_values[key].set_text("Unavailable")
        else:
            self.battery_values["charge"].set_text(
                f"{battery.battery_level}%"
                if battery.battery_level is not None
                else "Unavailable"
            )
            self.battery_values["ac"].set_text(
                "Connected"
                if battery.is_ac_plugged is True
                else "Disconnected"
                if battery.is_ac_plugged is False
                else "Unknown"
            )
            self.battery_values["start"].set_text(
                str(battery.charging_start_threshold)
                if battery.charging_start_threshold is not None
                else "Unavailable"
            )
            self.battery_values["stop"].set_text(
                str(battery.charging_stop_threshold)
                if battery.charging_stop_threshold is not None
                else "Unavailable"
            )
            self.battery_values["power"].set_text(
                f"{battery.power_consumption:.2f} W"
                if battery.power_consumption is not None
                else "Unavailable"
            )

        self.stats_values["usage"].set_text(
            f"{report.cpu_usage:.1f}%"
        )
        self.stats_values["load"].set_text(f"{report.load:.2f}")
        if report.avg_load:
            self.stats_values["load_avg"].set_text(
                f"{report.avg_load[0]:.2f} / "
                f"{report.avg_load[1]:.2f} / "
                f"{report.avg_load[2]:.2f}"
            )
        else:
            self.stats_values["load_avg"].set_text("Unavailable")

        average_temp = report.cpu_avg_temp
        if average_temp is None:
            temperatures = [
                core.temperature
                for core in report.cores_info
                if core.temperature > 0
            ]
            if temperatures:
                average_temp = sum(temperatures) / len(temperatures)

        self.stats_values["temp"].set_text(
            f"{average_temp:.1f} °C"
            if average_temp is not None
            else "Unavailable"
        )


class ToolWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="auto-cpufreq")
        self.set_default_size(920, 680)
        self.set_border_width(10)
        self.set_resizable(True)
        self.refresh_in_progress = False
        self.refresh_pending = False
        self.refresh_interval = DEFAULT_REFRESH_INTERVAL
        self.refresh_id = None
        self.pending_power_updates = set()
        self.pending_power_release = set()
        self.power_apply_sources = {}
        self.destroyed = False
        self.connect("destroy", self._cleanup_refresh)
        self.load_css()
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            filename=ICON_FILE,
            width=500,
            height=500,
            preserve_aspect_ratio=True,
        )
        self.set_icon(pixbuf)
        self.build()

    def main(self):
        self.report_view = SystemReportView()

        controls_frame = Gtk.Frame()
        controls_heading = Gtk.Label(label="Controls", name="bold")
        controls_heading.set_halign(Gtk.Align.START)
        controls_frame.set_label_widget(controls_heading)

        controls_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
        )
        controls_box.set_margin_top(8)
        controls_box.set_margin_bottom(8)
        controls_box.set_margin_start(10)
        controls_box.set_margin_end(10)
        controls_frame.add(controls_box)

        self.menu = DropDownMenu(self)
        self._add_refresh_interval_menu()
        controls_box.pack_start(self.menu, False, False, 0)

        self.governor_control = RadioButtonView()
        self.governor_control.label.set_xalign(0.0)
        self.governor_control.default.set_margin_start(CONTROL_OPTION_MARGIN)
        controls_box.pack_start(self.governor_control, False, False, 0)

        self.control_label_group = Gtk.SizeGroup(
            mode=Gtk.SizeGroupMode.HORIZONTAL
        )
        self.control_label_group.add_widget(self.governor_control.label)
        self.control_option_groups = [
            Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
            for _ in range(3)
        ]
        for group, button in zip(
            self.control_option_groups,
            (
                self.governor_control.default,
                self.governor_control.powersave,
                self.governor_control.performance,
            ),
        ):
            group.add_widget(button)
            button.set_halign(Gtk.Align.START)

        if "Warning: CPU turbo is not available" not in get_stats():
            self.turbo_control = CPUTurboOverride()
            self.turbo_control.label.set_xalign(0.0)
            self.turbo_control.auto.set_margin_start(CONTROL_OPTION_MARGIN)
            controls_box.pack_start(self.turbo_control, False, False, 0)
            self.control_label_group.add_widget(self.turbo_control.label)
            for group, button in zip(
                self.control_option_groups,
                (
                    self.turbo_control.auto,
                    self.turbo_control.never,
                    self.turbo_control.always,
                ),
            ):
                group.add_widget(button)
                button.set_halign(Gtk.Align.START)

        if bluetoothctl_exists:
            self.bluetooth_control = BluetoothBootControl()
            self.bluetooth_control.label.set_xalign(0.0)
            self.bluetooth_control.on_btn.set_margin_start(
                CONTROL_OPTION_MARGIN
            )
            self.control_label_group.add_widget(
                self.bluetooth_control.label
            )
            self.control_option_groups[0].add_widget(
                self.bluetooth_control.on_btn
            )
            self.control_option_groups[1].add_widget(
                self.bluetooth_control.off_btn
            )
            self.bluetooth_control.on_btn.set_halign(Gtk.Align.START)
            self.bluetooth_control.off_btn.set_halign(Gtk.Align.START)
            spacer = Gtk.Label()
            self.control_option_groups[2].add_widget(spacer)
            self.bluetooth_control.inner_box.pack_start(
                spacer, True, True, 0
            )
            controls_box.pack_start(
                self.bluetooth_control, False, False, 0
            )

        self.report_view.prepend_right(controls_frame)

        # Applying… continues to address the shared
        # observed governor/Turbo rows directly.
        self.power_values = self.report_view.power_values

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        self.scrolled.set_can_focus(False)
        self.scrolled.add(self.report_view)
        self.add(self.scrolled)

        self.refresh_in_thread()
        self._schedule_refresh()

    def begin_power_state_apply(self, key):
        if (
            self.destroyed
            or key not in getattr(self, "power_values", {})
        ):
            return False

        source_id = self.power_apply_sources.pop(key, None)
        if source_id is not None:
            GLib.source_remove(source_id)

        # A newer action for this field supersedes any older
        # release that was waiting behind an in-flight refresh.
        self.pending_power_release.discard(key)
        self.pending_power_updates.add(key)
        self.power_values[key].set_text("Applying…")
        return True

    def finish_power_state_apply(self, key, success):
        if (
            self.destroyed
            or key not in self.pending_power_updates
        ):
            return False

        if not success:
            self.pending_power_updates.discard(key)
            self.pending_power_release.discard(key)
            self.request_refresh()
            return True

        source_id = GLib.timeout_add_seconds(
            CONTROL_APPLY_DELAY_SECONDS,
            self._release_power_state_apply,
            key,
        )
        self.power_apply_sources[key] = source_id
        return True

    def _release_power_state_apply(self, key):
        self.power_apply_sources.pop(key, None)

        if (
            self.destroyed
            or key not in self.pending_power_updates
        ):
            return False

        # Never let a report that started before this point replace
        # "Applying…". If one is already running, queue a fresh one.
        if self.refresh_in_progress:
            self.pending_power_release.add(key)
            self.refresh_pending = True
            return False

        self.pending_power_updates.discard(key)
        self.refresh_in_thread()
        return False

    def _add_refresh_interval_menu(self):
        refresh_item = Gtk.MenuItem(
            label="Refresh interval"
        )
        refresh_menu = Gtk.Menu()
        group = None

        for seconds in REFRESH_INTERVALS:
            label = (
                f"{seconds} second"
                if seconds == 1
                else f"{seconds} seconds"
            )

            item = Gtk.RadioMenuItem.new_with_label(
                group,
                label,
            )

            if group is None:
                group = item.get_group()

            item.set_active(
                seconds == self.refresh_interval
            )

            item.connect(
                "toggled",
                self._on_refresh_interval_selected,
                seconds,
            )

            refresh_menu.append(item)

        refresh_item.set_submenu(refresh_menu)

        self.menu.menu.prepend(
            Gtk.SeparatorMenuItem()
        )
        self.menu.menu.prepend(refresh_item)
        self.menu.menu.show_all()

    def _on_refresh_interval_selected(
        self,
        item,
        seconds,
    ):
        if item.get_active():
            self.set_refresh_interval(seconds)

    def set_refresh_interval(self, seconds):
        if seconds not in REFRESH_INTERVALS:
            return

        if seconds == self.refresh_interval:
            return

        self.refresh_interval = seconds
        self._schedule_refresh()
        self.request_refresh()

    def _schedule_refresh(self):
        if self.refresh_id is not None:
            GLib.source_remove(self.refresh_id)

        self.refresh_id = GLib.timeout_add_seconds(
            self.refresh_interval,
            self.refresh_in_thread,
        )

    def request_refresh(self):
        if self.destroyed:
            return False

        if self.refresh_in_progress:
            self.refresh_pending = True
            return True

        return self.refresh_in_thread()

    def _run_pending_refresh(self):
        if (
            not self.refresh_pending
            or self.destroyed
        ):
            return

        self.refresh_pending = False

        # These fields waited for an older report to finish.
        # The refresh started below is therefore the first report
        # collected after their apply delay elapsed.
        for key in self.pending_power_release:
            self.pending_power_updates.discard(key)
        self.pending_power_release.clear()

        self.refresh_in_thread()

    def _cleanup_refresh(self, *_args):
        self.destroyed = True
        self.refresh_in_progress = False
        self.refresh_pending = False

        if self.refresh_id is not None:
            GLib.source_remove(self.refresh_id)
            self.refresh_id = None

        for source_id in self.power_apply_sources.values():
            GLib.source_remove(source_id)
        self.power_apply_sources.clear()
        self.pending_power_updates.clear()
        self.pending_power_release.clear()

    def snap(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        # reference: https://forum.snapcraft.io/t/pkexec-not-found-python-gtk-gnome-app/36579
        label = Gtk.Label(label="GUI not available due to Snap package confinement limitations.\nPlease install auto-cpufreq using auto-cpufreq-installer\nVisit the GitHub repo for more info")
        label.set_justify(Gtk.Justification.CENTER)
        button = Gtk.LinkButton.new_with_label(
            uri=GITHUB,
            label="GitHub Repo"
        )
        
        box.pack_start(label, False, False, 0)
        box.pack_start(button, False, False, 0)
        self.add(box)

    def handle_update(self):
        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            if not check_for_update(): return
        captured_output = new_stdout.getvalue().splitlines()
        dialog = UpdateDialog(self, captured_output[1], captured_output[2])
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES: return
        updater = run(["pkexec", "auto-cpufreq", "--update"], input="y\n", encoding="utf-8", stderr=PIPE)
        if updater.returncode in (126, 127):
            error = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, "Error updating")
            error.format_secondary_text("Authorization Failed")
            error.run()
            error.destroy()
            return
        success = Gtk.MessageDialog(self, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, "Update successful")
        success.format_secondary_text("The app will now close. Please reopen to apply changes")
        success.run()
        success.destroy()
        exit(0)

    def daemon_not_running(self):
        self.box = DaemonNotRunningView(self)
        self.add(self.box)

    def monitor_mode(self):
        self.monitor_view = MonitorModeView(
            self,
            SystemReportView(),
            refresh_interval=self.refresh_interval,
        )
        self.add(self.monitor_view)

    def build(self):
        if IS_INSTALLED_WITH_SNAP: self.snap()
        elif daemon_is_running(): self.main()
        else: self.daemon_not_running()

    def load_css(self):
        screen = Gdk.Screen.get_default()
        self.gtk_provider = Gtk.CssProvider()
        self.gtk_context = Gtk.StyleContext()
        self.gtk_context.add_provider_for_screen(screen, self.gtk_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.gtk_provider.load_from_file(Gio.File.new_for_path(CSS_FILE))

    def refresh_in_thread(self):
        if self.destroyed:
            return False
        if self.refresh_in_progress:
            return True

        self.refresh_in_progress = True
        Thread(target=self._refresh, daemon=True).start()
        return True

    def _refresh(self):
        try:
            report = system_info.generate_system_report()
        except Exception:
            if not self.destroyed:
                GLib.idle_add(self._finish_refresh)
            return

        if not self.destroyed:
            GLib.idle_add(self._apply_refresh, report)

    def _apply_refresh(self, report):
        if self.destroyed:
            self.refresh_in_progress = False
            return False

        try:
            self.report_view.apply_report(
                report,
                self.pending_power_updates,
            )
        finally:
            self.refresh_in_progress = False
            self._run_pending_refresh()

        return False

    def _finish_refresh(self):
        self.refresh_in_progress = False
        self._run_pending_refresh()
        return False
