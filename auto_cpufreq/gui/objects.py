import gi
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from os.path import isfile
from platform import python_version
from subprocess import getoutput, PIPE, run
from threading import Thread

from auto_cpufreq.config.config import config
from auto_cpufreq.gui.diagnostics import diagnostics
from auto_cpufreq.gui.desktop import open_containing_folder
# Keep existing import path for downstream consumers while the implementation
# lives next to the other view-specific GTK code.
from auto_cpufreq.gui.monitor_view import MonitorModeView
from auto_cpufreq.core import get_formatted_version, get_override, get_turbo_override
from auto_cpufreq.globals import GITHUB, IS_INSTALLED_WITH_AUR, IS_INSTALLED_WITH_SNAP
from auto_cpufreq.power_helper import bluetoothctl_exists



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

    try:
        Thread(target=worker, daemon=True).start()
    except RuntimeError as error:
        # Deliver the failure through the same GTK callback, allowing every
        # control to restore its enabled state without duplicated handling.
        GLib.idle_add(callback, None, error)


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
        # The command may finish after the window has been destroyed.
        # Never update detached widgets or schedule a new refresh then.
        if getattr(parent, "destroyed", False):
            return False
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
        parent = self.get_toplevel()
        _run_privileged_async(
            [option],
            lambda result, error: (
                self._finish_command(result, error)
                if not getattr(parent, "destroyed", False) else False
            ),
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

        debug = Gtk.CheckMenuItem(label="Enable debug logging")
        debug.set_active(diagnostics.enabled)
        debug.connect("toggled", self._toggle_debug_logging, parent)
        menu.append(debug)

        log_location = Gtk.MenuItem(label="Debug log location")
        log_location.connect("activate", self._show_debug_log_location, parent)
        menu.append(log_location)

        about = Gtk.MenuItem(label="About")
        about.connect("activate", self.about_dialog, parent)
        menu.append(about)

        menu.show_all()
        return menu

    def _toggle_debug_logging(self, item, parent):
        if getattr(self, "_syncing_debug_logging", False):
            return
        try:
            diagnostics.set_enabled(item.get_active())
        except (OSError, RuntimeError) as error:
            self._syncing_debug_logging = True
            try:
                item.set_active(diagnostics.enabled)
            finally:
                self._syncing_debug_logging = False

            dialog = Gtk.MessageDialog(
                transient_for=parent,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Unable to change debug logging",
            )
            dialog.format_secondary_text(str(error))
            dialog.set_destroy_with_parent(True)
            dialog.connect("response", lambda widget, _response: widget.destroy())
            dialog.show_all()


    def _show_debug_log_location(self, _item, parent):
        log_path = diagnostics.log_path
        logging_enabled = diagnostics.enabled
        if not log_path.is_file():
            if logging_enabled:
                status = "Log file unavailable. Check for logging errors."
            else:
                status = (
                    "No log file yet. Enable debug logging to create one."
                )
        elif logging_enabled:
            status = "Debug logging is enabled."
        else:
            status = "Debug logging is disabled. Showing the last session path."

        dialog = Gtk.MessageDialog(
            transient_for=parent,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.CLOSE,
            text="GTK debug log location",
        )
        dialog.format_secondary_text(
            f"File: {log_path.name}\n"
            f"Directory: {log_path.parent}\n\n"
            f"{status}\n\n"
            "Each session supports three 1 MiB backups. "
            "Review the contents before sharing."
        )
        dialog.add_button("Copy full path", Gtk.ResponseType.APPLY)
        dialog.add_button("Open folder", Gtk.ResponseType.YES)
        response = dialog.run()
        if response == Gtk.ResponseType.APPLY:
            dialog.get_clipboard(Gdk.SELECTION_CLIPBOARD).set_text(
                str(log_path), -1
            )
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            if logging_enabled:
                hint = (
                    "Debug logging is enabled, but the directory is missing. "
                    "Check for logging errors."
                )
            else:
                hint = "Enable debug logging first to create the log directory."
            open_containing_folder(parent, log_path, missing_hint=hint)

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
        icon_file = "/opt/auto-cpufreq/current/share/images/icon.png"
        if not isfile(icon_file):
            icon_file = "/usr/local/share/auto-cpufreq/images/icon.png"
        img_buffer = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            filename=icon_file,
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
        super().__init__(title="auto-cpufreq update available", transient_for=parent)
        self.box = self.get_content_area()
        self.set_default_size(400, 100)
        self.add_buttons("Update", Gtk.ResponseType.YES, "Cancel", Gtk.ResponseType.NO)
        self.label = Gtk.Label(label="An update for auto-cpufreq is available\n")
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

        self.debug_logging_button = Gtk.CheckButton(
            label="Enable debug logging"
        )
        self.debug_logging_button.set_active(diagnostics.enabled)
        self.debug_logging_button.connect(
            "toggled", self._toggle_debug_logging, parent
        )
        self.pack_start(self.debug_logging_button, False, False, 0)

    def _toggle_debug_logging(self, button, parent):
        if button.get_active() == diagnostics.enabled:
            return
        try:
            diagnostics.set_enabled(button.get_active())
        except (OSError, RuntimeError) as error:
            button.set_active(diagnostics.enabled)
            dialog = Gtk.MessageDialog(
                transient_for=parent,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Unable to change debug logging",
            )
            dialog.format_secondary_text(str(error))
            dialog.set_destroy_with_parent(True)
            dialog.connect("response", lambda widget, _response: widget.destroy())
            dialog.show_all()

    def start_monitor(self, button, parent):
        parent.remove(self)
        parent.monitor_mode()
        parent.show_all()

    def install_daemon(self, button, parent):
        self.set_sensitive(False)
        _run_privileged_async(
            ["--install"],
            lambda result, error: (
                self._finish_install(parent, result, error)
                if not getattr(parent, "destroyed", False) else False
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
