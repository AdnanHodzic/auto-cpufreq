"""GTK widgets for displaying a read-only SystemReport.

The UI renderer owns no refresh worker, GLib timer or policy command.
Both GTK dashboard and Monitor embed this same view.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from auto_cpufreq.modules.report_presentation import (
    present_report, present_platform_profile, offline_cpus_text,
    frequency_limit_text, battery_present,
)
from auto_cpufreq.modules.system_info import battery_power_label

HBOX_PADDING = 20
SECTION_SPACING = 12

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

        system_frame, self.system_grid = _new_section("System Information")
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
            _, self.system_values[key] = _add_row(
                self.system_grid, row, name
            )
        self.left_column.pack_start(system_frame, False, False, 0)

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

        self.offline_label = Gtk.Label(label="")
        self.offline_label.set_halign(Gtk.Align.START)
        self.offline_label.set_xalign(0)
        self.offline_label.set_no_show_all(True)
        self.cpu_box.pack_start(self.offline_label, False, False, 0)

        self.left_column.pack_start(cpu_frame, False, False, 0)

        self.right_column = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=SECTION_SPACING,
        )
        self.right_column.set_valign(Gtk.Align.START)
        self.columns.pack_start(self.right_column, True, True, 0)

        platform_frame, self.platform_grid = _new_section("Platform Profile")
        self.platform_names = {}
        self.platform_values = {}
        for row, (key, name) in enumerate(
            (
                ("interface", "Interface"),
                ("current", "Current profile"),
                ("available", "Available profiles (0)"),
                ("provider", "Provider"),
            )
        ):
            name_label, value_label = _add_row(
                self.platform_grid, row, name
            )
            self.platform_names[key] = name_label
            self.platform_values[key] = value_label

        # Keep long kernel-provided lists readable without increasing the
        # window's minimum width. The complete values stay visible by wrapping.
        for key in ("available", "provider"):
            value_label = self.platform_values[key]
            value_label.set_max_width_chars(44)
            value_label.set_line_wrap(True)
            value_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        self.right_column.pack_start(platform_frame, False, False, 0)

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
        self.battery_names = {}
        self.battery_values = {}
        for row, (key, name) in enumerate(
            (
                ("status", "Status"),
                ("charge", "Charge"),
                ("ac", "AC power"),
                ("start", "Start threshold"),
                ("stop", "Stop threshold"),
                ("power", "Battery power"),
            )
        ):
            name_label, value_label = _add_row(
                self.battery_grid, row, name
            )
            self.battery_names[key] = name_label
            self.battery_values[key] = value_label
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
        self.left_column.pack_start(stats_frame, False, False, 0)

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
                if column == 1:
                    # Keep later columns stable when usage reaches 100.0%.
                    label.set_width_chars(len("100.0%"))
                self.cores_grid.attach(label, column, row, 1, 1)

        self.cores_grid.show_all()

    def apply_report(self, report, pending_power_updates=()):
        presentation = present_report(report)
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

        profile = present_platform_profile(report.platform_profile)
        self.platform_values["interface"].set_text(profile.interface)
        if profile.detected:
            for row in (1, 2):
                _set_row_visible(self.platform_grid, row, True)
            self.platform_values["current"].set_text(profile.current)
            self.platform_names["available"].set_text(
                profile.available_label
            )
            self.platform_values["available"].set_text(profile.available)
        else:
            for row in (1, 2):
                _set_row_visible(self.platform_grid, row, False)

        _set_row_visible(
            self.platform_grid, 3, profile.provider_visible
        )
        if profile.provider_visible:
            self.platform_names["provider"].set_text(
                profile.provider_label
            )
            self.platform_values["provider"].set_text(profile.provider)

        self.max_freq_value.set_text(
            frequency_limit_text(report.cpu_max_freq)
        )
        self.min_freq_value.set_text(
            frequency_limit_text(report.cpu_min_freq)
        )
        self._refresh_core_rows(report.cores_info)

        if report.cpu_fan_speed is not None:
            self.fan_label.set_text(
                f"CPU fan speed: {report.cpu_fan_speed} RPM"
            )
            self.fan_label.show()
        else:
            self.fan_label.hide()

        offline_text = offline_cpus_text(report.offline_cpus)
        if offline_text:
            self.offline_label.set_text(offline_text)
            self.offline_label.show()
        else:
            self.offline_label.hide()

        if "governor" not in pending_power_updates:
            self.power_values["governor"].set_text(
                presentation.governor.text
            )
        self.power_values["epp"].set_text(
            presentation.epp.text
        )
        self.power_values["epb"].set_text(
            presentation.epb.text
        )

        hwp_available = report.current_hwp_dynamic_boost is not None
        _set_row_visible(self.power_grid, 3, hwp_available)
        if hwp_available:
            self.power_values["hwp"].set_text(
                presentation.hwp_dynamic_boost.text
            )

        if "turbo" not in pending_power_updates:
            self.power_values["turbo"].set_text(
                presentation.turbo.text
            )

        battery = report.battery_info
        self.battery_values["status"].set_text(
            presentation.battery.status.text
        )
        if not battery_present(battery):
            for row in range(1, 6):
                _set_row_visible(self.battery_grid, row, False)
        else:
            for row in range(1, 6):
                _set_row_visible(self.battery_grid, row, True)
            self.battery_values["charge"].set_text(
                presentation.battery.level.text
            )
            self.battery_values["ac"].set_text(
                presentation.battery.ac.text
            )
            self.battery_values["start"].set_text(
                presentation.battery.charge_start.text
            )
            self.battery_values["stop"].set_text(
                presentation.battery.charge_stop.text
            )
            self.battery_names["power"].set_text(
                battery_power_label(battery)
            )
            self.battery_values["power"].set_text(
                presentation.battery.power_watts.text
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

        self.stats_values["temp"].set_text(
            presentation.average_temperature.text
        )


