import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, AppIndicator3 as appindicator

from subprocess import run

def main():
    indicator = appindicator.Indicator.new("auto-cpufreq-tray", "network-idle-symbolic", appindicator.IndicatorCategory.APPLICATION_STATUS)
    indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
    indicator.set_menu(build_menu())
    Gtk.main()

def build_menu():
    menu = Gtk.Menu()

    program = Gtk.MenuItem("auto-cpufreq")
    program.connect("activate", open_app)
    menu.append(program)

    _quit = Gtk.MenuItem("Quit")
    _quit.connect("activate", Gtk.main_quit)
    menu.append(_quit)
    menu.show_all()
    return menu

def open_app(MenuItem): run("sudo -E python app.py", shell=True)

if __name__ == "__main__": main()