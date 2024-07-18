import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, Gtk

import sys
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from os.path import isfile
from platform import python_version
from subprocess import getoutput, PIPE, run

from auto_cpufreq.core import distro_info, get_formatted_version, get_override, sysinfo
from auto_cpufreq.globals import GITHUB, IS_INSTALLED_WITH_AUR, IS_INSTALLED_WITH_SNAP

PKEXEC_ERROR = "Error executing command as another user: Not authorized\n\nThis incident has been reported.\n"

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

class RadioButtonView(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)

        self.set_hexpand(True)
        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.label = Gtk.Label("Governor Override", name="bold")

        self.default = Gtk.RadioButton.new_with_label_from_widget(None, "Default")
        self.default.connect("toggled", self.on_button_toggled,  "reset")
        self.default.set_halign(Gtk.Align.END)
        self.powersave = Gtk.RadioButton.new_with_label_from_widget(self.default, "Powersave")
        self.powersave.connect("toggled", self.on_button_toggled,  "powersave")
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
                if result.stderr.decode() == PKEXEC_ERROR: self.set_selected()
            else: self.set_by_app = False

    def set_selected(self):
        override = get_override()
        match override:
            case "powersave": self.powersave.set_active(True)
            case "performance": self.performance.set_active(True)
            case "default":
                # because this is the default button, it does not trigger the callback when set by the app
                if self.set_by_app: self.set_by_app = False
                self.default.set_active(True)

class CurrentGovernorBox(Gtk.Box):
    def __init__(self):
        super().__init__(spacing=25)
        self.static = Gtk.Label(label="Current Governor", name="bold")
        self.governor = Gtk.Label(label=getoutput("cpufreqctl.auto-cpufreq --governor").strip().split(" ")[0], halign=Gtk.Align.END)

        self.pack_start(self.static, False, False, 0)
        self.pack_start(self.governor, False, False, 0)

    def refresh(self):
        self.governor.set_label(getoutput("cpufreqctl.auto-cpufreq --governor").strip().split(" ")[0])

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
                assert result.stderr.decode() != PKEXEC_ERROR, Exception("Authorization was cancelled")
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

class DaemonNotRunningView(Gtk.Box):
    def __init__(self, parent):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)

        self.label = Gtk.Label(label="auto-cpufreq daemon is not running. Please click the install button")
        self.install_button = Gtk.Button.new_with_label("Install")

        self.install_button.connect("clicked", self.install_daemon, parent)

        self.pack_start(self.label, False, False, 0)
        self.pack_start(self.install_button, False, False, 0)

    def install_daemon(self, button, parent):
        try:
            # run in thread to prevent GUI from hanging
            with ThreadPoolExecutor() as executor:
                kwargs = {"shell": True, "stdout": PIPE, "stderr": PIPE}
                future = executor.submit(run, "pkexec auto-cpufreq --install", **kwargs)
                result = future.result()
            assert result.stderr.decode() != PKEXEC_ERROR, Exception("Authorization was cancelled")
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
