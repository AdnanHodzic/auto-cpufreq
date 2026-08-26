import gi
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

import sys
from io import StringIO
from os.path import isfile
from platform import python_version
from subprocess import getoutput, PIPE, run
from threading import Thread
import time

from auto_cpufreq.config.config import config, find_config_file
from auto_cpufreq.core import distro_info, get_formatted_version, get_override, get_turbo_override, sysinfo
from auto_cpufreq.globals import GITHUB, IS_INSTALLED_WITH_AUR, IS_INSTALLED_WITH_SNAP
from auto_cpufreq.modules.system_info import system_info
from auto_cpufreq.power_helper import bluetoothctl_exists

auto_cpufreq_stats_path = ("/var/snap/auto-cpufreq/current" if IS_INSTALLED_WITH_SNAP else "/var/run") + "/auto-cpufreq.stats"

def get_stats():
    if not isfile(auto_cpufreq_stats_path):
        return ""
    with open(auto_cpufreq_stats_path, "r") as file:
        return "".join(file.readlines()[-50:])

def get_version():
    # snap package
    if IS_INSTALLED_WITH_SNAP: return getoutput(r"echo \(Snap\) $SNAP_VERSION")
    # aur package
    elif IS_INSTALLED_WITH_AUR: return getoutput("pacman -Qi auto-cpufreq | grep Version")
    else:
        # source code (auto-cpufreq-installer)
        try: return get_formatted_version()
        except Exception as e:
            print(repr(e))
            pass

def get_bluetooth_boot_status():
    if not bluetoothctl_exists:
        return None
    btconf = "/etc/bluetooth/main.conf"
    try:
        with open(btconf, "r") as f:
            in_policy_section = False
            for line in f:
                stripped = line.strip()
                if stripped.startswith("["):
                    in_policy_section = stripped.lower() == "[policy]"
                    continue
                if not in_policy_section:
                    continue
                if stripped.startswith("#") or not stripped:
                    continue
                if stripped.startswith("AutoEnable="):
                    value = stripped.split("=", 1)[1].strip().lower()
                    return "on" if value == "true" else "off"
            return "on"
    except Exception:
        return None

def _run_privileged_async(arguments, callback):
    def worker():
        try:
            result = run(
                ["pkexec", "auto-cpufreq", *arguments],
                stdout=PIPE,
                stderr=PIPE,
                text=True,
            )
            error = None
        except OSError as e:
            result = None
            error = e

        GLib.idle_add(callback, result, error)

    Thread(target=worker, daemon=True).start()


def _privileged_command_error(result, error):
    if error is not None:
        return str(error)
    if result is None:
        return "Command failed to start"
    if result.returncode == 0:
        return None
    if result.returncode == 126:
        return "Authorization was cancelled"
    if result.returncode == 127:
        return "Authorization failed"

    stderr = (result.stderr or "").strip()
    return stderr or (
        f"Command failed with exit status "
        f"{result.returncode}"
    )


def _request_status_refresh(widget):
    parent = widget.get_toplevel()
    refresh = getattr(parent, "request_refresh", None)

    if callable(refresh):
        refresh()


def _run_power_state_command(
    widget,
    state_key,
    arguments,
    callback,
):
    parent = widget.get_toplevel()
    begin = getattr(parent, "begin_power_state_apply", None)
    finish = getattr(parent, "finish_power_state_apply", None)

    tracked = (
        callable(begin)
        and callable(finish)
        and begin(state_key)
    )

    def complete(result, error):
        if tracked:
            finish(
                state_key,
                _privileged_command_error(result, error) is None,
            )

        return callback(result, error)

    _run_privileged_async(arguments, complete)


class RadioButtonView(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)

        self.set_hexpand(True)
        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.label = Gtk.Label("Governor Override", name="bold")

        self.default = Gtk.RadioButton.new_with_label_from_widget(None, "Default")
        self.default.connect("toggled", self.on_button_toggled, "reset")
        self.default.set_halign(Gtk.Align.END)
        self.powersave = Gtk.RadioButton.new_with_label_from_widget(self.default, "Powersave")
        self.powersave.connect("toggled", self.on_button_toggled, "powersave")
        self.powersave.set_halign(Gtk.Align.END)
        self.performance = Gtk.RadioButton.new_with_label_from_widget(self.default, "Performance")
        self.performance.connect("toggled", self.on_button_toggled, "performance")
        self.performance.set_halign(Gtk.Align.END)

        # this keeps track of whether or not the button was toggled by the app or the user to prompt for authorization
        self.set_by_app = True
        self.set_selected()

        self.pack_start(self.label, False, False, 0)
        self.pack_start(self.default, True, True, 0)
        self.pack_start(self.powersave, True, True, 0)
        self.pack_start(self.performance, True, True, 0)

    def on_button_toggled(self, button, override):
        if not button.get_active():
            return
        if self.set_by_app:
            self.set_by_app = False
            return

        self.set_sensitive(False)
        _run_power_state_command(
            self,
            "governor",
            [f"--force={override}"],
            self._finish_command,
        )

    def _finish_command(self, result, error):
        self.set_sensitive(True)

        if _privileged_command_error(result, error) is None:
            _request_status_refresh(self)
        else:
            self.set_by_app = True
            self.set_selected()

        return False

    def set_selected(self):
        override = get_override()
        match override:
            case "powersave": self.powersave.set_active(True)
            case "performance": self.performance.set_active(True)
            case "default":
                # because this is the default button, it does not trigger the callback when set by the app
                self.default.set_active(True)
                if self.set_by_app: self.set_by_app = False

class CPUTurboOverride(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)

        self.set_hexpand(True)
        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.label = Gtk.Label("CPU Turbo Override", name="bold")

        self.auto = Gtk.RadioButton.new_with_label_from_widget(None, "Auto")
        self.auto.connect("toggled", self.on_button_toggled,  "auto")
        self.auto.set_halign(Gtk.Align.END)
        self.never = Gtk.RadioButton.new_with_label_from_widget(self.auto, "Never")
        self.never.connect("toggled", self.on_button_toggled,  "never")
        self.never.set_halign(Gtk.Align.END)
        self.always = Gtk.RadioButton.new_with_label_from_widget(self.auto, "Always")
        self.always.connect("toggled", self.on_button_toggled, "always")
        self.always.set_halign(Gtk.Align.END)

        self.set_by_app = True
        self.set_selected()

        self.pack_start(self.label, False, False, 0)
        self.pack_start(self.auto, True, True, 0)
        self.pack_start(self.never, True, True, 0)
        self.pack_start(self.always, True, True, 0)

    def on_button_toggled(self, button, override):
        if not button.get_active():
            return
        if self.set_by_app:
            self.set_by_app = False
            return

        self.set_sensitive(False)
        _run_power_state_command(
            self,
            "turbo",
            [f"--turbo={override}"],
            self._finish_command,
        )

    def _finish_command(self, result, error):
        self.set_sensitive(True)

        if _privileged_command_error(result, error) is None:
            _request_status_refresh(self)
        else:
            self.set_by_app = True
            self.set_selected()

        return False

    def set_selected(self):
        override = get_turbo_override()
        match override:
            case "never": self.never.set_active(True)
            case "always": self.always.set_active(True)
            case "auto":
                # because this is the default button, it does not trigger the callback when set by the app
                self.auto.set_active(True)
                if self.set_by_app: self.set_by_app = False

class BluetoothBootControl(Gtk.Box):
    def __init__(self, show_advanced_button=True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        self.set_hexpand(True)

        self.advanced_btn = Gtk.Button(label="Advanced Settings")
        self.advanced_btn.connect("clicked", self.on_advanced_clicked)
        self.advanced_btn.set_halign(Gtk.Align.START)

        self.revealer = Gtk.Revealer()
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.revealer.set_transition_duration(200)

        self.inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.inner_box.set_hexpand(True)

        self.label = Gtk.Label("Bluetooth on Boot", name="bold")

        self.on_btn = Gtk.RadioButton.new_with_label_from_widget(None, "On")
        self.on_btn.connect("toggled", self.on_button_toggled, "on")
        self.on_btn.set_halign(Gtk.Align.END)
        self.off_btn = Gtk.RadioButton.new_with_label_from_widget(self.on_btn, "Off")
        self.off_btn.connect("toggled", self.on_button_toggled, "off")
        self.off_btn.set_halign(Gtk.Align.END)

        self.set_by_app = True
        self.set_selected()

        self.inner_box.pack_start(self.label, False, False, 0)
        self.inner_box.pack_start(self.on_btn, True, True, 0)
        self.inner_box.pack_start(self.off_btn, True, True, 0)

        self.revealer.add(self.inner_box)

        if show_advanced_button:
            self.pack_start(self.advanced_btn, False, False, 0)
        self.pack_start(self.revealer, False, False, 0)

    def on_advanced_clicked(self, button):
        revealed = self.revealer.get_reveal_child()
        self.revealer.set_reveal_child(not revealed)
        if revealed:
            self.advanced_btn.set_label("Advanced Settings")
        else:
            self.advanced_btn.set_label("Hide Advanced Settings")

    def on_button_toggled(self, button, action):
        if not button.get_active():
            return
        if self.set_by_app:
            self.set_by_app = False
            return

        option = (
            "--bluetooth_boot_on"
            if action == "on"
            else "--bluetooth_boot_off"
        )

        self.set_sensitive(False)
        self.advanced_btn.set_sensitive(False)
        _run_privileged_async(
            [option],
            self._finish_command,
        )

    def _finish_command(self, result, error):
        self.set_sensitive(True)
        self.advanced_btn.set_sensitive(True)

        if _privileged_command_error(result, error) is not None:
            self.set_by_app = True
            self.set_selected()

        return False

    def set_selected(self):
        status = get_bluetooth_boot_status()
        match status:
            case "off": self.off_btn.set_active(True)
            case "on" | _:
                # because this is the default button, it does not trigger the callback when set by the app
                self.on_btn.set_active(True)
                if self.set_by_app: self.set_by_app = False

class CurrentGovernorBox(Gtk.Box):
    def __init__(self):
        super().__init__(spacing=25)
        self.static = Gtk.Label(label="Current Governor", name="bold")
        self.governor = Gtk.Label(label=getoutput("cpufreqctl.auto-cpufreq --governor").strip().split(" ")[0], halign=Gtk.Align.END)

        self.pack_start(self.static, False, False, 0)
        self.pack_start(self.governor, False, False, 0)

    def refresh(self):
        self.governor.set_label(getoutput("cpufreqctl.auto-cpufreq --governor").strip().split(" ")[0])

class BatteryInfoBox(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        self.header = Gtk.Label(label="-" * 20 + " Battery Stats " + "-" * 20)
        self.header.set_halign(Gtk.Align.START)

        self.status_label = Gtk.Label(label="")
        self.status_label.set_halign(Gtk.Align.START)

        self.percentage_label = Gtk.Label(label="")
        self.percentage_label.set_halign(Gtk.Align.START)

        self.ac_label = Gtk.Label(label="")
        self.ac_label.set_halign(Gtk.Align.START)

        self.start_threshold_label = Gtk.Label(label="")
        self.start_threshold_label.set_halign(Gtk.Align.START)

        self.stop_threshold_label = Gtk.Label(label="")
        self.stop_threshold_label.set_halign(Gtk.Align.START)

        self.pack_start(self.header, False, False, 0)
        self.pack_start(self.status_label, False, False, 0)
        self.pack_start(self.percentage_label, False, False, 0)
        self.pack_start(self.ac_label, False, False, 0)
        self.pack_start(self.start_threshold_label, False, False, 0)
        self.pack_start(self.stop_threshold_label, False, False, 0)

        self.refresh()

    def refresh(self):
        try:
            battery_info = system_info.battery_info()

            self.status_label.set_label(f"Battery status: {str(battery_info)}")

            if battery_info.battery_level is not None:
                percentage_text = f"{battery_info.battery_level}%"
            else:
                percentage_text = "Unknown"
            self.percentage_label.set_label(f"Battery percentage: {percentage_text}")

            if battery_info.is_ac_plugged is not None:
                ac_text = "Yes" if battery_info.is_ac_plugged else "No"
            else:
                ac_text = "Unknown"
            self.ac_label.set_label(f"AC plugged: {ac_text}")

            if battery_info.is_ac_plugged is not None:
                start_text = str(battery_info.charging_start_threshold) if battery_info.charging_start_threshold is not None else "None"
            else:
                start_text = "Unknown"
            self.start_threshold_label.set_label(f"Charging start threshold: {start_text}")

            if battery_info.is_ac_plugged is not None:
                stop_text = str(battery_info.charging_stop_threshold) if battery_info.charging_stop_threshold is not None else "None"
            else:
                stop_text = "Unknown"
            self.stop_threshold_label.set_label(f"Charging stop threshold: {stop_text}")

        except Exception:
            self.status_label.set_label("Battery status: Unknown")
            self.percentage_label.set_label("Battery percentage: Unknown")
            self.ac_label.set_label("AC plugged: Unknown")
            self.start_threshold_label.set_label("Charging start threshold: Unknown")
            self.stop_threshold_label.set_label("Charging stop threshold: Unknown")

class CPUFreqScalingBox(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        self.header = Gtk.Label(label="-" * 20 + " CPU Frequency Scaling " + "-" * 20)
        self.header.set_halign(Gtk.Align.START)

        self.epp_label = Gtk.Label(label="")
        self.epp_label.set_halign(Gtk.Align.START)

        self.epb_label = Gtk.Label(label="")
        self.epb_label.set_halign(Gtk.Align.START)
        self.epb_label.set_no_show_all(True)

        self.hwp_dynamic_boost_label = Gtk.Label(label="")
        self.hwp_dynamic_boost_label.set_halign(Gtk.Align.START)
        self.hwp_dynamic_boost_label.set_no_show_all(True)

        self.pack_start(self.header, False, False, 0)
        self.pack_start(self.epp_label, False, False, 0)
        self.pack_start(self.epb_label, False, False, 0)
        self.pack_start(self.hwp_dynamic_boost_label, False, False, 0)

        self.refresh()

    def refresh(self):
        try:
            report = system_info.generate_system_report()

            if report.current_epp:
                self.epp_label.set_label(f"Current EPP: {report.current_epp}")
                self.epp_label.show()
            else:
                self.epp_label.set_label("Not setting EPP (not supported by system)")
                self.epp_label.show()

            if report.current_epb:
                self.epb_label.set_label(f"Current EPB: {report.current_epb}")
                self.epb_label.show()
            else:
                self.epb_label.hide()

            if report.current_hwp_dynamic_boost is not None:
                state = "on" if report.current_hwp_dynamic_boost else "off"
                self.hwp_dynamic_boost_label.set_label(
                    f"Intel HWP Dynamic Boost: {state}"
                )
                self.hwp_dynamic_boost_label.show()
            else:
                self.hwp_dynamic_boost_label.hide()

        except Exception:
            self.epp_label.set_label("Current EPP: Unknown")
            self.epb_label.hide()
            self.hwp_dynamic_boost_label.hide()

class SystemStatisticsBox(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        self.header = Gtk.Label(label="-" * 20 + " System Statistics " + "-" * 20)
        self.header.set_halign(Gtk.Align.START)

        self.cpu_usage_label = Gtk.Label(label="")
        self.cpu_usage_label.set_halign(Gtk.Align.START)

        self.load_label = Gtk.Label(label="")
        self.load_label.set_halign(Gtk.Align.START)

        self.temp_label = Gtk.Label(label="")
        self.temp_label.set_halign(Gtk.Align.START)
        self.temp_label.set_no_show_all(True)

        self.load_status_label = Gtk.Label(label="")
        self.load_status_label.set_halign(Gtk.Align.START)
        self.load_status_label.set_no_show_all(True)

        self.usage_status_label = Gtk.Label(label="")
        self.usage_status_label.set_halign(Gtk.Align.START)
        self.usage_status_label.set_no_show_all(True)

        self.turbo_label = Gtk.Label(label="")
        self.turbo_label.set_halign(Gtk.Align.START)

        self.fan_label = Gtk.Label(label="")
        self.fan_label.set_halign(Gtk.Align.START)
        self.fan_label.set_no_show_all(True)

        self.pack_start(self.header, False, False, 0)
        self.pack_start(self.cpu_usage_label, False, False, 0)
        self.pack_start(self.load_label, False, False, 0)
        self.pack_start(self.temp_label, False, False, 0)
        self.pack_start(self.fan_label, False, False, 0)
        self.pack_start(self.load_status_label, False, False, 0)
        self.pack_start(self.usage_status_label, False, False, 0)
        self.pack_start(self.turbo_label, False, False, 0)

        self.refresh()

    def refresh(self):
        try:
            report = system_info.generate_system_report()

            self.cpu_usage_label.set_label(f"Total CPU usage: {report.cpu_usage:.1f} %")

            self.load_label.set_label(f"Total system load: {report.load:.2f}")

            avg_temp = 0.0
            if report.cores_info:
                avg_temp = sum(core.temperature for core in report.cores_info) / len(report.cores_info)
                self.temp_label.set_label(f"Average temp. of all cores: {avg_temp:.2f} °C")
                self.temp_label.show()
            else:
                self.temp_label.hide()

            if report.cpu_fan_speed:
                self.fan_label.set_label(f"CPU fan speed: {report.cpu_fan_speed} RPM")
                self.fan_label.show()
            else:
                self.fan_label.hide()

            if report.avg_load:
                load_status = "Load optimal" if report.load < 1.0 else "Load high"
                self.load_status_label.set_label(
                    f"{load_status} (load average: {report.avg_load[0]:.2f}, {report.avg_load[1]:.2f}, {report.avg_load[2]:.2f})"
                )
                self.load_status_label.show()
            else:
                self.load_status_label.hide()

            if report.cores_info:
                usage_status = "Optimal" if report.cpu_usage < 70 else "High"
                temp_status = "high" if avg_temp > 75 else "normal"
                self.usage_status_label.set_label(
                    f"{usage_status} total CPU usage: {report.cpu_usage:.1f}%, {temp_status} average core temp: {avg_temp:.1f}°C"
                )
                self.usage_status_label.show()
            else:
                self.usage_status_label.hide()

            if report.is_turbo_on[0] is not None:
                turbo_status = "On" if report.is_turbo_on[0] else "Off"
            elif report.is_turbo_on[1] is not None:
                turbo_status = f"Auto mode {'enabled' if report.is_turbo_on[1] else 'disabled'}"
            else:
                turbo_status = "Unknown"
            self.turbo_label.set_label(f"Setting turbo boost: {turbo_status}")

        except Exception:
            self.cpu_usage_label.set_label("Total CPU usage: Unknown")
            self.load_label.set_label("Total system load: Unknown")
            self.temp_label.hide()
            self.fan_label.hide()
            self.load_status_label.hide()
            self.usage_status_label.hide()
            self.turbo_label.set_label("Setting turbo boost: Unknown")

class SystemStatsLabel(Gtk.Label):
    def __init__(self):
        super().__init__()
        self.refresh()

    def refresh(self):
        # change stdout and store label text to file-like object
        old_stdout = sys.stdout
        text = StringIO()
        sys.stdout = text
        distro_info()
        sysinfo()
        self.set_label(text.getvalue())
        sys.stdout = old_stdout
    
class CPUFreqStatsLabel(Gtk.Label):
    def __init__(self):
        super().__init__()
        self.refresh()
  
    def refresh(self):
        stats = get_stats().split("\n")
        start = None
        for i, line in enumerate(stats):
            if line == ("-" * 28 + " CPU frequency scaling " + "-" * 28):
                start = i
                break
        if start is not None:
            del stats[:i]
            del stats[-4:]
            self.set_label("\n".join(stats))
 
class DropDownMenu(Gtk.MenuButton):
    def __init__(self, parent):
        super().__init__()
        self.set_halign(Gtk.Align.END)
        self.set_valign(Gtk.Align.START)
        self.image = Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        self.add(self.image)
        self.menu = self.build_menu(parent)
        self.set_popup(self.menu)

    def build_menu(self, parent):
        menu = Gtk.Menu()

        daemon = Gtk.MenuItem(label="Remove Daemon")
        daemon.connect("activate", self._remove_daemon, parent)
        menu.append(daemon)

        about = Gtk.MenuItem(label="About")
        about.connect("activate", self.about_dialog, parent)
        menu.append(about)

        menu.show_all()
        return menu

    def about_dialog(self, MenuItem, parent):
        dialog = AboutDialog(parent)
        response = dialog.run()
        dialog.destroy()

    def _remove_daemon(self, MenuItem, parent):
        confirm = ConfirmDialog(
            parent,
            message="Are you sure you want to remove the daemon?",
        )
        response = confirm.run()
        confirm.destroy()

        if response != Gtk.ResponseType.YES:
            return

        self.set_sensitive(False)
        _run_privileged_async(
            ["--remove"],
            lambda result, error: self._finish_remove(
                parent,
                result,
                error,
            ),
        )

    def _finish_remove(self, parent, result, error):
        self.set_sensitive(True)

        try:
            command_error = _privileged_command_error(
                result,
                error,
            )
            if command_error is not None:
                raise RuntimeError(command_error)

            dialog = Gtk.MessageDialog(
                transient_for=parent,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Daemon successfully removed",
            )
            dialog.format_secondary_text(
                "The app will now close. "
                "Please reopen to apply changes"
            )
            dialog.run()
            dialog.destroy()
            parent.destroy()

        except Exception as e:
            dialog = Gtk.MessageDialog(
                transient_for=parent,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Daemon removal failed",
            )
            dialog.format_secondary_text(
                f"The following error occurred:\n{e}"
            )
            dialog.run()
            dialog.destroy()

        return False

class AboutDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="About", transient_for=parent)
        app_version = get_version()
        self.box = self.get_content_area()
        self.box.set_spacing(10)
        self.add_button("Close", Gtk.ResponseType.CLOSE)
        self.set_default_size(400, 350)
        img_buffer = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            filename="/usr/local/share/auto-cpufreq/images/icon.png",
            width=150,
            height=150,
            preserve_aspect_ratio=True
        )
        self.image = Gtk.Image.new_from_pixbuf(img_buffer)
        self.title = Gtk.Label(label="auto-cpufreq", name="bold")
        self.version = Gtk.Label(label=app_version)
        self.python = Gtk.Label(label=f"Python {python_version()}")
        self.github = Gtk.Label(label=GITHUB)
        self.license = Gtk.Label(label="Licensed under GNU GPL v3 or later", name="small")
        self.love = Gtk.Label(label="Made with <3", name="small")

        self.box.pack_start(self.image, False, False, 0)
        self.box.pack_start(self.title, False, False, 0)
        self.box.pack_start(self.version, False, False, 0)
        self.box.pack_start(self.python, False, False, 0)
        self.box.pack_start(self.github, False, False, 0)
        self.box.pack_start(self.license, False, False, 0)
        self.box.pack_start(self.love, False, False, 0)
        self.show_all()

class UpdateDialog(Gtk.Dialog):
    def __init__(self, parent, current_version: str, latest_version: str):
        super().__init__(title="Update Available", transient_for=parent)
        self.box = self.get_content_area()
        self.set_default_size(400, 100)
        self.add_buttons("Update", Gtk.ResponseType.YES, "Cancel", Gtk.ResponseType.NO)
        self.label = Gtk.Label(label="An update is available\n")
        self.current_version = Gtk.Label(label=current_version + "\n")
        self.latest_version = Gtk.Label(label=latest_version + "\n")

        self.box.pack_start(self.label, True, False, 0)
        self.box.pack_start(self.current_version, True, False, 0)
        self.box.pack_start(self.latest_version, True, False, 0)

        self.show_all()

class ConfirmDialog(Gtk.Dialog):
    def __init__(self, parent, message: str):
        super().__init__(title="Confirmation", transient_for=parent)
        self.box = self.get_content_area()
        self.set_default_size(400, 100)
        self.add_buttons("Yes", Gtk.ResponseType.YES, "No", Gtk.ResponseType.NO)
        self.label = Gtk.Label(label=message)

        self.box.pack_start(self.label, True, False, 0)

        self.show_all()


class MonitorModeView(Gtk.Box):
    def __init__(
        self,
        parent,
        report_view,
        refresh_interval=5,
    ):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )
        self.parent = parent
        self.report_view = report_view
        self.running = True
        self.refresh_interval = refresh_interval
        self.refresh_id = None

        self.header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL
        )
        self.header.set_margin_bottom(2)

        self.title = Gtk.Label(
            label="Monitor Mode",
            name="bold",
        )
        self.title.set_halign(Gtk.Align.START)
        self.header.pack_start(
            self.title, True, True, 0
        )

        self.back_button = Gtk.Button.new_with_label(
            "Back"
        )
        self.back_button.connect(
            "clicked",
            self.on_back_clicked,
        )
        self.header.pack_end(
            self.back_button, False, False, 0
        )

        self.pack_start(
            self.header, False, False, 0
        )

        self.error_label = Gtk.Label(label="")
        self.error_label.set_halign(Gtk.Align.START)
        self.error_label.set_xalign(0)
        self.error_label.set_no_show_all(True)
        self.pack_start(
            self.error_label, False, False, 0
        )

        suggestions = Gtk.Frame()
        heading = Gtk.Label(
            label="Suggestions",
            name="bold",
        )
        heading.set_halign(Gtk.Align.START)
        suggestions.set_label_widget(heading)

        grid = Gtk.Grid()
        grid.set_column_spacing(18)
        grid.set_row_spacing(4)
        grid.set_margin_top(8)
        grid.set_margin_bottom(8)
        grid.set_margin_start(10)
        grid.set_margin_end(10)
        suggestions.add(grid)

        governor_name = Gtk.Label(label="Governor")
        governor_name.set_halign(Gtk.Align.START)
        governor_name.set_xalign(0)

        self.governor_suggestion = Gtk.Label(
            label="—"
        )
        self.governor_suggestion.set_halign(
            Gtk.Align.START
        )
        self.governor_suggestion.set_xalign(0)

        grid.attach(governor_name, 0, 0, 1, 1)
        grid.attach(
            self.governor_suggestion,
            1, 0, 1, 1,
        )

        self.turbo_name = Gtk.Label(
            label="Turbo Boost"
        )
        self.turbo_name.set_halign(Gtk.Align.START)
        self.turbo_name.set_xalign(0)
        self.turbo_name.set_no_show_all(True)

        self.turbo_suggestion = Gtk.Label(
            label="—"
        )
        self.turbo_suggestion.set_halign(
            Gtk.Align.START
        )
        self.turbo_suggestion.set_xalign(0)
        self.turbo_suggestion.set_no_show_all(True)

        grid.attach(self.turbo_name, 0, 1, 1, 1)
        grid.attach(
            self.turbo_suggestion,
            1, 1, 1, 1,
        )

        self.report_view.prepend_right(
            suggestions
        )

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        self.scrolled.set_can_focus(True)
        self.scrolled.add(self.report_view)

        self.pack_start(
            self.scrolled, True, True, 0
        )

        self.refresh_in_thread()

    def refresh_in_thread(self):
        self.refresh_id = None

        if not self.running:
            return False

        Thread(
            target=self._refresh,
            daemon=True,
        ).start()

        return False

    def _refresh(self):
        try:
            report = (
                system_info.generate_system_report()
            )
            suggested_governor = (
                system_info.governor_suggestion(report)
            )

            suggested_turbo = None
            if report.is_turbo_on[0] is not None:
                suggested_turbo = (
                    system_info.turbo_on_suggestion(
                        report
                    )
                )

        except Exception as error:
            if self.running:
                GLib.idle_add(
                    self._show_error,
                    str(error),
                )
            return

        if self.running:
            GLib.idle_add(
                self._update_display,
                report,
                suggested_governor,
                suggested_turbo,
            )

    def _show_error(self, message):
        if not self.running:
            return False

        self.error_label.set_text(
            "Unable to refresh system information: "
            f"{message}"
        )
        self.error_label.show()

        self.refresh_id = (
            GLib.timeout_add_seconds(
                self.refresh_interval,
                self.refresh_in_thread,
            )
        )
        return False

    def _update_display(
        self,
        report,
        suggested_governor,
        suggested_turbo,
    ):
        if not self.running:
            return False

        self.error_label.hide()
        self.title.set_text(
            "Monitor Mode - "
            f"{time.strftime('%H:%M:%S')}"
        )

        # Same observed-state renderer as the normal GTK dashboard.
        self.report_view.apply_report(report)

        if (
            report.current_gov is not None
            and suggested_governor is not None
            and suggested_governor
            != report.current_gov
        ):
            self.governor_suggestion.set_text(
                f"Use {suggested_governor}"
            )
        else:
            self.governor_suggestion.set_text(
                "No change suggested"
            )

        turbo_available = (
            report.is_turbo_on[0] is not None
        )

        if turbo_available:
            self.turbo_name.show()
            self.turbo_suggestion.show()

            if (
                suggested_turbo is not None
                and suggested_turbo
                != report.is_turbo_on[0]
            ):
                self.turbo_suggestion.set_text(
                    "Turn on"
                    if suggested_turbo
                    else "Turn off"
                )
            else:
                self.turbo_suggestion.set_text(
                    "No change suggested"
                )
        else:
            self.turbo_name.hide()
            self.turbo_suggestion.hide()

        self.refresh_id = (
            GLib.timeout_add_seconds(
                self.refresh_interval,
                self.refresh_in_thread,
            )
        )
        return False

    def on_back_clicked(self, _button):
        self.cleanup()
        self.parent.remove(self)
        self.parent.daemon_not_running()
        self.parent.show_all()

    def cleanup(self):
        self.running = False

        if self.refresh_id is not None:
            GLib.source_remove(self.refresh_id)
            self.refresh_id = None


class DaemonNotRunningView(Gtk.Box):
    def __init__(self, parent):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)

        self.label = Gtk.Label(label="auto-cpufreq daemon is not running")
        self.sublabel = Gtk.Label(label="Install the daemon for permanent optimization, or use Monitor mode to preview")

        self.button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, halign=Gtk.Align.CENTER)
        self.install_button = Gtk.Button.new_with_label("Install Daemon")
        self.monitor_button = Gtk.Button.new_with_label("Monitor Mode")

        self.install_button.connect("clicked", self.install_daemon, parent)
        self.monitor_button.connect("clicked", self.start_monitor, parent)

        self.button_box.pack_start(self.install_button, False, False, 0)
        self.button_box.pack_start(self.monitor_button, False, False, 0)

        self.pack_start(self.label, False, False, 0)
        self.pack_start(self.sublabel, False, False, 0)
        self.pack_start(self.button_box, False, False, 0)

    def start_monitor(self, button, parent):
        parent.remove(self)
        parent.monitor_mode()
        parent.show_all()

    def install_daemon(self, button, parent):
        self.set_sensitive(False)
        _run_privileged_async(
            ["--install"],
            lambda result, error: self._finish_install(
                parent,
                result,
                error,
            ),
        )

    def _finish_install(self, parent, result, error):
        self.set_sensitive(True)

        try:
            command_error = _privileged_command_error(
                result,
                error,
            )
            if command_error is not None:
                raise RuntimeError(command_error)

            dialog = Gtk.MessageDialog(
                transient_for=parent,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Daemon successfully installed",
            )
            dialog.format_secondary_text(
                "The app will now close. "
                "Please reopen to apply changes"
            )
            dialog.run()
            dialog.destroy()
            parent.destroy()

        except Exception as e:
            dialog = Gtk.MessageDialog(
                transient_for=parent,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Daemon install failed",
            )
            dialog.format_secondary_text(
                f"The following error occurred:\n{e}"
            )
            dialog.run()
            dialog.destroy()

        return False