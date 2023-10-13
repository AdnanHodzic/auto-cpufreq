#!/usr/bin/env python3

import sys

sys.path.append("../")

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib
from auto_cpufreq.gui.app import ToolWindow

def main():
    win = ToolWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    GLib.set_prgname("auto-cpufreq")
    Gtk.main()

if __name__ == "__main__":
    main()