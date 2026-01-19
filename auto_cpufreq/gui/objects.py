import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

import sys
from concurrent.futures import ThreadPoolExecutor
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
    if isfile(auto_cpufreq_stats_path):
        with open(auto_cpufreq_stats_path, "r") as file: stats = [line for line in (file.readlines() [-50:])]
        return "".join(stats)

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
        if button.get_active():
            if not self.set_by_app:
                result = run(f"pkexec auto-cpufreq --force={override}", shell=True, stdout=PIPE, stderr=PIPE)
                if result.returncode in (126, 127):
                    self.set_by_app = True
                    self.set_selected()
            else: self.set_by_app = False

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
        if button.get_active():
            if not self.set_by_app:
                result = run(f"pkexec auto-cpufreq --turbo={override}", shell=True, stdout=PIPE, stderr=PIPE)
                if result.returncode in (126, 127):
                    self.set_by_app = True
                    self.set_selected()
            else: self.set_by_app = False

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
    def __init__(self):
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
        if button.get_active():
            if not self.set_by_app:
                if action == "on":
                    result = run("pkexec auto-cpufreq --bluetooth_boot_on", shell=True, stdout=PIPE, stderr=PIPE)
                else:
                    result = run("pkexec auto-cpufreq --bluetooth_boot_off", shell=True, stdout=PIPE, stderr=PIPE)
                if result.returncode in (126, 127):
                    self.set_by_app = True
                    self.set_selected()
            else: self.set_by_app = False

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

        self.governor_label = Gtk.Label(label="")
        self.governor_label.set_halign(Gtk.Align.START)

        self.epp_label = Gtk.Label(label="")
        self.epp_label.set_halign(Gtk.Align.START)

        self.epb_label = Gtk.Label(label="")
        self.epb_label.set_halign(Gtk.Align.START)
        self.epb_label.set_no_show_all(True)

        self.pack_start(self.header, False, False, 0)
        self.pack_start(self.governor_label, False, False, 0)
        self.pack_start(self.epp_label, False, False, 0)
        self.pack_start(self.epb_label, False, False, 0)

        self.refresh()

    def refresh(self):
        try:
            report = system_info.generate_system_report()

            gov = report.current_gov if report.current_gov else "Unknown"
            self.governor_label.set_label(f'Setting to use: "{gov}" governor')

            if report.current_epp:
                self.epp_label.set_label(f"EPP setting: {report.current_epp}")
                self.epp_label.show()
            else:
                self.epp_label.set_label("Not setting EPP (not supported by system)")
                self.epp_label.show()

            if report.current_epb:
                self.epb_label.set_label(f'Setting to use: "{report.current_epb}" EPB')
                self.epb_label.show()
            else:
                self.epb_label.hide()

        except Exception:
            self.governor_label.set_label('Setting to use: "Unknown" governor')
            self.epp_label.set_label("EPP setting: Unknown")
            self.epb_label.hide()

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
        confirm = ConfirmDialog(parent, message="Are you sure you want to remove the daemon?")
        response = confirm.run()
        confirm.destroy()
        if response == Gtk.ResponseType.YES:
            try:
                # run in thread to prevent GUI from hanging
                with ThreadPoolExecutor() as executor:
                    kwargs = {"shell": True, "stdout": PIPE, "stderr": PIPE}
                    future = executor.submit(run, "pkexec auto-cpufreq --remove", **kwargs)
                    result = future.result()
                assert result.returncode not in (126, 127), Exception("Authorization was cancelled")
                dialog = Gtk.MessageDialog(
                    transient_for=parent,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="Daemon successfully removed"
                )
                dialog.format_secondary_text("The app will now close. Please reopen to apply changes")
                dialog.run()
                dialog.destroy()
                parent.destroy()
            except Exception as e:
                dialog = Gtk.MessageDialog(
                    transient_for=parent,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Daemon removal failed"
                )
                dialog.format_secondary_text(f"The following error occured:\n{e}")
                dialog.run()
                dialog.destroy()

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
        self.license = Gtk.Label(label="Licensed under LGPL3", name="small")
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
    def __init__(self, parent):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.parent = parent
        self.running = True

        self.header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.header.set_margin_bottom(10)

        self.title = Gtk.Label(label="Monitor Mode", name="bold")
        self.title.set_halign(Gtk.Align.START)
        self.header.pack_start(self.title, True, True, 0)

        self.back_button = Gtk.Button.new_with_label("Back")
        self.back_button.connect("clicked", self.on_back_clicked)
        self.header.pack_end(self.back_button, False, False, 0)

        self.pack_start(self.header, False, False, 0)

        self.columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        self.columns.set_vexpand(True)
        self.columns.set_hexpand(True)

        self.left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.left_box.set_valign(Gtk.Align.START)
        self.columns.pack_start(self.left_box, True, True, 0)

        self.separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.columns.pack_start(self.separator, False, False, 0)

        self.right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.right_box.set_valign(Gtk.Align.START)
        self.columns.pack_start(self.right_box, True, True, 0)

        self.pack_start(self.columns, True, True, 0)

        self.refresh()
        self.refresh_id = GLib.timeout_add_seconds(5, self.refresh_in_thread)

    def refresh_in_thread(self):
        if not self.running:
            return False
        Thread(target=self._refresh, daemon=True).start()
        return True

    def _refresh(self):
        try:
            report = system_info.generate_system_report()
            GLib.idle_add(self._update_display, report)
        except Exception as e:
            GLib.idle_add(self._show_error, str(e))

    def refresh(self):
        try:
            report = system_info.generate_system_report()
            self._update_display(report)
        except Exception as e:
            self._show_error(str(e))

    def _show_error(self, error_msg):
        self._clear_boxes()
        self.left_box.pack_start(self._label(f"Error: {error_msg}"), False, False, 0)
        self.left_box.show_all()

    def _clear_boxes(self):
        for child in self.left_box.get_children():
            self.left_box.remove(child)
        for child in self.right_box.get_children():
            self.right_box.remove(child)

    def _header(self, text):
        label = Gtk.Label(label=text, name="bold")
        label.set_halign(Gtk.Align.START)
        return label

    def _label(self, text):
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        return label

    def _suggestion(self, text):
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        label.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.9, 0.7, 0.1, 1.0))
        return label

    def _separator(self, text):
        label = Gtk.Label(label="-" * 28 + f" {text} " + "-" * 28)
        label.set_halign(Gtk.Align.START)
        return label

    def _update_display(self, report):
        self._clear_boxes()

        current_time = time.strftime("%H:%M:%S")
        self.title.set_text(f"Monitor Mode - {current_time}")


        self.left_box.pack_start(self._separator("System Information"), False, False, 5)
        self.left_box.pack_start(self._label(f"Linux distro: {report.distro_name} {report.distro_ver}"), False, False, 0)
        self.left_box.pack_start(self._label(f"Linux kernel: {report.kernel_version}"), False, False, 0)
        self.left_box.pack_start(self._label(f"Processor: {report.processor_model}"), False, False, 0)
        self.left_box.pack_start(self._label(f"Cores: {report.total_core}"), False, False, 0)
        self.left_box.pack_start(self._label(f"Architecture: {report.arch}"), False, False, 0)
        self.left_box.pack_start(self._label(f"Driver: {report.cpu_driver}"), False, False, 0)

        config_path = config.path if config.has_config() else find_config_file(None)
        if isfile(config_path):
            self.left_box.pack_start(self._label(f"\nUsing settings defined in {config_path}"), False, False, 0)

        self.left_box.pack_start(self._label(""), False, False, 0)

        self.left_box.pack_start(self._separator("Current CPU Stats"), False, False, 5)
        self.left_box.pack_start(self._label(f"CPU max frequency: {report.cpu_max_freq:.0f} MHz" if report.cpu_max_freq else "CPU max frequency: Unknown"), False, False, 0)
        self.left_box.pack_start(self._label(f"CPU min frequency: {report.cpu_min_freq:.0f} MHz" if report.cpu_min_freq else "CPU min frequency: Unknown"), False, False, 0)
        self.left_box.pack_start(self._label(""), False, False, 0)
        self.left_box.pack_start(self._label("Core    Usage   Temperature     Frequency"), False, False, 0)

        for core in report.cores_info:
            self.left_box.pack_start(
                self._label(f"CPU{core.id:<2}    {core.usage:>4.1f}%    {core.temperature:>6.0f} °C    {core.frequency:>6.0f} MHz"),
                False, False, 0
            )

        if report.cpu_fan_speed:
            self.left_box.pack_start(self._label(""), False, False, 0)
            self.left_box.pack_start(self._label(f"CPU fan speed: {report.cpu_fan_speed} RPM"), False, False, 0)


        if report.battery_info is not None:
            self.right_box.pack_start(self._separator("Battery Stats"), False, False, 5)
            self.right_box.pack_start(self._label(f"Battery status: {str(report.battery_info)}"), False, False, 0)
            battery_level = f"{report.battery_info.battery_level}%" if report.battery_info.battery_level is not None else "Unknown"
            self.right_box.pack_start(self._label(f"Battery percentage: {battery_level}"), False, False, 0)
            ac_status = "Yes" if report.battery_info.is_ac_plugged else "No" if report.battery_info.is_ac_plugged is not None else "Unknown"
            self.right_box.pack_start(self._label(f"AC plugged: {ac_status}"), False, False, 0)
            self.right_box.pack_start(self._label(f"Charging start threshold: {report.battery_info.charging_start_threshold}"), False, False, 0)
            self.right_box.pack_start(self._label(f"Charging stop threshold: {report.battery_info.charging_stop_threshold}"), False, False, 0)
            self.right_box.pack_start(self._label(""), False, False, 0)

        self.right_box.pack_start(self._separator("CPU Frequency Scaling"), False, False, 5)
        current_gov = report.current_gov if report.current_gov else "Unknown"
        self.right_box.pack_start(self._label(f'Setting to use: "{current_gov}" governor'), False, False, 0)

        suggested_gov = system_info.governor_suggestion()
        if report.current_gov and suggested_gov != report.current_gov:
            self.right_box.pack_start(self._suggestion(f'Suggesting use of: "{suggested_gov}" governor'), False, False, 0)

        if report.current_epp:
            self.right_box.pack_start(self._label(f"EPP setting: {report.current_epp}"), False, False, 0)
        else:
            self.right_box.pack_start(self._label("Not setting EPP (not supported by system)"), False, False, 0)

        if report.current_epb:
            self.right_box.pack_start(self._label(f'Setting to use: "{report.current_epb}" EPB'), False, False, 0)

        self.right_box.pack_start(self._label(""), False, False, 0)

        self.right_box.pack_start(self._separator("System Statistics"), False, False, 5)
        self.right_box.pack_start(self._label(f"Total CPU usage: {report.cpu_usage:.1f} %"), False, False, 0)
        self.right_box.pack_start(self._label(f"Total system load: {report.load:.2f}"), False, False, 0)

        avg_temp = 0.0
        if report.cores_info:
            avg_temp = sum(core.temperature for core in report.cores_info) / len(report.cores_info)
            self.right_box.pack_start(self._label(f"Average temp. of all cores: {avg_temp:.2f} °C"), False, False, 0)

        if report.avg_load:
            load_status = "Load optimal" if report.load < 1.0 else "Load high"
            self.right_box.pack_start(
                self._label(f"{load_status} (load average: {report.avg_load[0]:.2f}, {report.avg_load[1]:.2f}, {report.avg_load[2]:.2f})"),
                False, False, 0
            )

        if report.cores_info:
            usage_status = "Optimal" if report.cpu_usage < 70 else "High"
            temp_status = "high" if avg_temp > 75 else "normal"
            self.right_box.pack_start(
                self._label(f"{usage_status} total CPU usage: {report.cpu_usage:.1f}%, {temp_status} average core temp: {avg_temp:.1f}°C"),
                False, False, 0
            )

        turbo_status = "Unknown"
        if report.is_turbo_on[0] is not None:
            turbo_status = "On" if report.is_turbo_on[0] else "Off"
        elif report.is_turbo_on[1] is not None:
            turbo_status = f"Auto mode {'enabled' if report.is_turbo_on[1] else 'disabled'}"
        self.right_box.pack_start(self._label(f"Setting turbo boost: {turbo_status}"), False, False, 0)

        if report.is_turbo_on[0] is not None:
            suggested_turbo = system_info.turbo_on_suggestion()
            if suggested_turbo != report.is_turbo_on[0]:
                turbo_text = "on" if suggested_turbo else "off"
                self.right_box.pack_start(self._suggestion(f"Suggesting to set turbo boost: {turbo_text}"), False, False, 0)

        self.left_box.show_all()
        self.right_box.show_all()
        return False

    def on_back_clicked(self, button):
        self.cleanup()
        self.parent.remove(self)
        self.parent.daemon_not_running()
        self.parent.show_all()

    def cleanup(self):
        self.running = False
        if hasattr(self, 'refresh_id') and self.refresh_id:
            GLib.source_remove(self.refresh_id)


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
        try:
            # run in thread to prevent GUI from hanging
            with ThreadPoolExecutor() as executor:
                kwargs = {"shell": True, "stdout": PIPE, "stderr": PIPE}
                future = executor.submit(run, "pkexec auto-cpufreq --install", **kwargs)
                result = future.result()
            assert result.returncode not in (126, 127), Exception("Authorization was cancelled")
            # enable for debug. causes issues if kept
            # elif result.stderr is not None:
            #     raise Exception(result.stderr.decode())
            dialog = Gtk.MessageDialog(
                transient_for=parent,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Daemon successfully installed"
            )
            dialog.format_secondary_text("The app will now close. Please reopen to apply changes")
            dialog.run()
            dialog.destroy()
            parent.destroy()
        except Exception as e:
            dialog = Gtk.MessageDialog(
                transient_for=parent,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Daemon install failed"
            )
            dialog.format_secondary_text(f"The following error occured:\n{e}")
            dialog.run()
            dialog.destroy()