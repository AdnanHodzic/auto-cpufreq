import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib, Gdk, Gio, GdkPixbuf

import os
import sys
from threading import Thread

sys.path.append("../")
from auto_cpufreq.core import is_running
from auto_cpufreq.gui.objects import RadioButtonView, SystemStatsLabel, CPUFreqStatsLabel, CurrentGovernorBox, DropDownMenu, DaemonNotRunningView

if os.getenv("PKG_MARKER") == "SNAP":
    ICON_FILE = "/snap/auto-cpufreq/current/icon.png"
    CSS_FILE = "/snap/auto-cpufreq/current/style.css"
else:
    ICON_FILE = "/usr/local/share/auto-cpufreq/images/icon.png"
    CSS_FILE = "/usr/local/share/auto-cpufreq/scripts/style.css"

HBOX_PADDING = 20

class ToolWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="auto-cpufreq")
        self.set_default_size(600, 480)
        self.set_border_width(10)
        self.set_resizable(False)
        self.load_css()
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filename=ICON_FILE, width=500, height=500, preserve_aspect_ratio=True)
        self.set_icon(pixbuf)
        self.build()

    def main(self):
        # self.vbox_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # self.vbox_top.set_valign(Gtk.Align.CENTER)
        # self.vbox_top.set_halign(Gtk.Align.CENTER)
        #self.add(self.vbox_top)

        # Main HBOX
        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=HBOX_PADDING)
       
        self.systemstats = SystemStatsLabel()
        self.hbox.pack_start(self.systemstats, False, False, 0)
        self.add(self.hbox)

        self.vbox_right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=52)
        
        self.menu = DropDownMenu(self)
        self.hbox.pack_end(self.menu, False, False, 0)
        
        self.currentgovernor = CurrentGovernorBox()
        self.vbox_right.pack_start(self.currentgovernor, False, False, 0)
        self.vbox_right.pack_start(RadioButtonView(), False, False, 0)

        self.cpufreqstats = CPUFreqStatsLabel()
        self.vbox_right.pack_start(self.cpufreqstats, False, False, 0)

        self.hbox.pack_start(self.vbox_right, False, False, 0)


        GLib.timeout_add_seconds(5, self.refresh_in_thread)

    def daemon_not_running(self):
        self.box = DaemonNotRunningView(self)
        self.add(self.box)

    def build(self):
        if is_running("auto-cpufreq", "--daemon"):
            self.main()
        else:
            self.daemon_not_running()

    def load_css(self):
        screen = Gdk.Screen.get_default()
        self.gtk_provider = Gtk.CssProvider()
        self.gtk_context = Gtk.StyleContext()
        self.gtk_context.add_provider_for_screen(screen, self.gtk_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.gtk_provider.load_from_file(Gio.File.new_for_path(CSS_FILE))

    def refresh_in_thread(self):
        Thread(target=self._refresh).start()
        return True

    def _refresh(self):
        self.systemstats.refresh()
        self.currentgovernor.refresh()
        self.cpufreqstats.refresh()

