import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, Gio, GdkPixbuf

from contextlib import redirect_stdout
from io import StringIO
from subprocess import PIPE, run
from threading import Thread

from auto_cpufreq.globals import AUTO_CPUFREQ_DAEMON_IS_RUNNING, GITHUB, IS_INSTALLED_WITH_SNAP
from auto_cpufreq.gui.objects import RadioButtonView, SystemStatsLabel, CPUFreqStatsLabel, CurrentGovernorBox, DropDownMenu, DaemonNotRunningView, UpdateDialog
from auto_cpufreq.update import check_for_update

if IS_INSTALLED_WITH_SNAP:
    CSS_FILE = '/snap/auto-cpufreq/current/style.css'
    ICON_FILE = '/snap/auto-cpufreq/current/icon.png'
else:
    CSS_FILE = '/usr/local/share/auto-cpufreq/scripts/style.css'
    ICON_FILE = '/usr/local/share/auto-cpufreq/images/icon.png'

HBOX_PADDING = 20
PKEXEC_ERROR = 'Error executing command as another user: Not authorized\n\nThis incident has been reported.\n'

class ToolWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title='auto-cpufreq')
        self.set_default_size(600, 480)
        self.set_border_width(10)
        self.set_resizable(False)

        load_css()
        self.set_icon(GdkPixbuf.Pixbuf.new_from_file_at_scale(filename=ICON_FILE, width=500, height=500, preserve_aspect_ratio=True))

        self.build()

    def build(self):
        if IS_INSTALLED_WITH_SNAP:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            # reference: https://forum.snapcraft.io/t/pkexec-not-found-python-gtk-gnome-app/36579
            label = Gtk.Label(label='GUI not available due to Snap package confinement limitations.\nPlease install auto-cpufreq using auto-cpufreq-installer\nVisit the GitHub repo for more info')
            label.set_justify(Gtk.Justification.CENTER)
            button = Gtk.LinkButton.new_with_label(uri=GITHUB, label='GitHub Repo')
            
            box.pack_start(label, False, False, 0)
            box.pack_start(button, False, False, 0)
            self.add(box)
        elif AUTO_CPUFREQ_DAEMON_IS_RUNNING: 
            self.systemstats = SystemStatsLabel()

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=HBOX_PADDING)
            hbox.pack_start(self.systemstats, False, False, 0)
            self.add(hbox)

            vbox_right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=52)
            
            self.menu = DropDownMenu(self)
            hbox.pack_end(self.menu, False, False, 0)
            
            self.currentgovernor = CurrentGovernorBox()
            vbox_right.pack_start(self.currentgovernor, False, False, 0)
            vbox_right.pack_start(RadioButtonView(), False, False, 0)

            self.cpufreqstats = CPUFreqStatsLabel()
            vbox_right.pack_start(self.cpufreqstats, False, False, 0)

            hbox.pack_start(vbox_right, False, False, 0)

            GLib.timeout_add_seconds(2, self.refresh_in_thread)
        else: self.add(DaemonNotRunningView(self))

    def handle_update(self):
        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            if not check_for_update(): return
        
        captured_output = new_stdout.getvalue().splitlines()
        dialog = UpdateDialog(self, captured_output[1], captured_output[2])
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES: return
        
        if run(['pkexec', 'auto-cpufreq', '--update'], input='y\n', encoding='utf-8', stderr=PIPE).stderr == PKEXEC_ERROR:
            error = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, 'Error updating')
            error.format_secondary_text('Authorization Failed')
            error.run()
            error.destroy()
            return
        
        success = Gtk.MessageDialog(self, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, 'Update successful')
        success.format_secondary_text('The app will now close. Please reopen to apply changes')
        success.run()
        success.destroy()
        exit(0)

    def refresh_in_thread(self):
        def refresh():
            self.systemstats.refresh()
            self.currentgovernor.refresh()
            self.cpufreqstats.refresh()

        Thread(target=refresh).start()
        return True

def load_css():
    screen = Gdk.Screen.get_default()
    gtk_provider = Gtk.CssProvider()
    gtk_context = Gtk.StyleContext()
    gtk_context.add_provider_for_screen(screen, gtk_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    gtk_provider.load_from_file(Gio.File.new_for_path(CSS_FILE))