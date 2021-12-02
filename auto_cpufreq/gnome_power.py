# * add status as one of the available options
# * alert user on snap if detected and how to remove first time live/stats message starts
# * if daemon is disabled and auto-cpufreq is removed (snap) remind user to enable it back
import os, sys, click
from subprocess import getoutput, call, run, check_output, DEVNULL

sys.path.append('../')
from auto_cpufreq.core import *

# app_name var
if sys.argv[0] == "gnome_power.py":
    app_name="python3 gnome_power.py"
else:
    app_name="auto-cpufreq"

# detect if gnome power profile service is running
if os.getenv('PKG_MARKER') != "SNAP":
    gnome_power_stats = call(["systemctl", "is-active", "--quiet", "power-profiles-daemon"])

# alert in case gnome power profile service is running
def gnome_power_detect():
    if gnome_power_stats == 0:
        print("\nDetected running GNOME Power Profiles daemon service:")
        print("This daemon might interfere with auto-cpufreq and it will be disabled!")
        print("\nIf you wish to enable this daemon to run concurrently with auto-cpufreq run:")
        print("cd ~/auto-cpufreq/auto_cpufreq")
        print("python3 gnome_power.py --enable")

# notification on snap
def gnome_power_detect_snap():
        print("\nUnable to detect state of GNOME Power Profiles daemon service:")
        print("This daemon might interfere with auto-cpufreq and should be disabled!\n")
        print("Due to Snap limitations, it needs to be disabled manually by running, i.e:")
        print("cd ~/auto-cpufreq/auto_cpufreq")
        print("python3 gnome_power.py --disable")

# disable gnome >= 40 power profiles (live)
def gnome_power_disable_live():
    if(gnome_power_stats == 0):
        call(["systemctl", "stop", "power-profiles-daemon"])

# disable gnome >= 40 power profiles (install)
def gnome_power_disable():
    if(gnome_power_stats == 0):
        print("\n* Disabling GNOME power profiles")
        call(["systemctl", "stop", "power-profiles-daemon"])
        call(["systemctl", "disable", "power-profiles-daemon"])
        call(["systemctl", "mask", "power-profiles-daemon"])
    else:
        print("\n* Disabling GNOME power profiles (already disabled)")

# enable gnome >= 40 power profiles (uninstall)
def gnome_power_enable():
    if(gnome_power_stats == 0):
        print("\n* Enabling GNOME power profiles")
        call(["systemctl", "unmask", "power-profiles-daemon"])
        call(["systemctl", "start", "power-profiles-daemon"])
        call(["systemctl", "enable", "power-profiles-daemon"])
    else:
        print("\n* Enabling GNOME power profiles (already enabled)")

def valid_options():
    print("--enable\t\tEnable GNOME Power Profiles daemon")
    print("--disable\t\tDisable GNOME Power Profiles daemon\n")

# cli
# ToDo: implement status option
@click.command()
@click.option("--enable", is_flag=True, help="Monitor and see suggestions for CPU optimizations")
@click.option("--disable", is_flag=True, help="Monitor and make (temp.) suggested CPU optimizations")
def main(enable, disable):

    root_check()
    if len(sys.argv) == 1:
        print("---------------- auto-cpufreq: GNOME Power Profiles helper --------------------\n")
        print("Unrecognized option!\n\nRun: \"" + app_name + " --help\" for list of available options.")
        footer()
    else:
        if enable:
            # Todo: prettify output
            root_check()
            print("Enabling")
            gnome_power_enable()
        elif disable:
            # Todo: prettify output
            root_check()
            print("Disabling")
            gnome_power_disable()
        else:
            print("whatever")

if __name__ == '__main__':
    main()
