# * add gnome_power_detect message after install (make it more visible)
# * make sure daemon is enabled after auto-cpufreq --remove (non snap)
# * if daemon is disabled and auto-cpufreq is removed (snap) remind user to enable it back
import os, sys, click
from subprocess import getoutput, call, run, check_output, DEVNULL

sys.path.append('../')
from auto_cpufreq.core import *

# app_name var
#if os.getenv("PKG_MARKER") == "SNAP":
#    app_name = "auto-cpufreq"
if sys.argv[0] == "gnome_power.py":
    app_name="gnome_power.py"
else:
    app_name="auto-cpufreq"

# detect if gnome power profile service is running
gnome_power_stats = call(["systemctl", "is-active", "--quiet", "power-profiles-daemon"])
# ToDo: remove
print(gnome_power_stats)
print(os.getenv('PKG_MARKER'))

# alert in case gnome power profile service is running
def gnome_power_detect():
    # ToDo: broken, can't be checked like this
    if os.getenv('PKG_MARKER') == "SNAP" and gnome_power_stats == 0:
        print("\nDetected running GNOME Power Profiles daemon service:")
        print("This daemon might interfere with auto-cpufreq and should be disabled!\n")
        print("Due to Snap limitations, it needs to be disabled manually by running, i.e:")
        print("cd ~/auto-cpufreq/auto_cpufreq")
        print("python3 gnome_power.py --disable")
    elif gnome_power_stats == 0:
        print("\nDetected running GNOME Power Profiles daemon service:")
        print("This daemon might interfere with auto-cpufreq and it will be disabled!")
        gnome_power_disable()
        print("\nIf you wish to enable this daemon to run concurrently with auto-cpufreq run:")
        print("cd ~/auto-cpufreq/auto_cpufreq")
        print("python3 gnome_power.py --enable")

# disable gnome >= 40 power profiles (live)
def gnome_power_disable_live():
    if(gnome_power_stats != 0):
        # ToDo: remove
        print("\nDisabling GNOME power profiles")
        call(["systemctl", "stop", "power-profiles-daemon"])
    else:
        print("GNOME power already disabled")

# disable gnome >= 40 power profiles (install)
def gnome_power_disable():
    if(gnome_power_stats != 0):
        # ToDo: remove
        print("\nDisabling GNOME power profiles")
        call(["systemctl", "stop", "power-profiles-daemon"])
        call(["systemctl", "disable", "power-profiles-daemon"])
        call(["systemctl", "mask", "power-profiles-daemon"])
    else:
        print("GNOME power already disabled")

# enable gnome >= 40 power profiles (uninstall)
def gnome_power_enable():
    # ToDo: remove
    if(gnome_power_stats != 0):
        print("\nEnabling GNOME power profiles")
        call(["systemctl", "unmask", "power-profiles-daemon"])
        call(["systemctl", "start", "power-profiles-daemon"])
        call(["systemctl", "enable", "power-profiles-daemon"])
    else:
        print("GNOME power already enabled")

def valid_options():
    print("--enable\t\tEnable GNOME Power Profiles daemon")
    print("--disable\t\tDisable GNOME Power Profiles daemon\n")

# cli
@click.command()
@click.option("--enable", is_flag=True, help="Monitor and see suggestions for CPU optimizations")
@click.option("--disable", is_flag=True, help="Monitor and make (temp.) suggested CPU optimizations")
def main(enable, disable):

    root_check()
    if len(sys.argv) == 1:
        footer()
        print("Provided none of valid options.\n\nRun: \"" + app_name + " --help\" for more info")
        footer()
    else:
        if enable:
            root_check()
            print("Enabling")
        elif disable:
            print("Disabling")
        else:
            print("whatever")

if __name__ == '__main__':
    main()
