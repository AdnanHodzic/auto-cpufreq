# * add status as one of the available options
# * alert user on snap if detected and how to remove first time live/stats message starts
# * if daemon is disabled and auto-cpufreq is removed (snap) remind user to enable it back
import os, sys, click
from subprocess import getoutput, call, run, check_output, DEVNULL

sys.path.append('../')
from auto_cpufreq.core import *

# app_name var
if sys.argv[0] == "power_helper.py":
    app_name="python3 power_helper.py"
else:
    app_name="auto-cpufreq"

# detect if gnome power profile service is running
if os.getenv('PKG_MARKER') != "SNAP":
    gnome_power_stats = call(["systemctl", "is-active", "--quiet", "power-profiles-daemon"])

# alert in case gnome power profile service is running
def gnome_power_detect():
    if gnome_power_stats == 0:
        print("\n----------------------------------- Warning -----------------------------------\n")
        print("Detected running GNOME Power Profiles daemon service!")
        print("This daemon might interfere with auto-cpufreq and should be disabled.")
        print("\nSteps to perform this action using auto-cpufreq: power_helper script:")
        print("git clone https://github.com/AdnanHodzic/auto-cpufreq.git")
        print("cd auto-cpufreq/auto_cpufreq")
        print("python3 power_helper.py --gnome-power-disable")


# notification on snap
def gnome_power_detect_snap():
        print("\n----------------------------------- Warning -----------------------------------\n")
        print("Unable to detect state of GNOME Power Profiles daemon service!")
        print("This daemon might interfere with auto-cpufreq and should be disabled.")
        print("\nSteps to perform this action using auto-cpufreq: power_helper script:")
        print("git clone https://github.com/AdnanHodzic/auto-cpufreq.git")
        print("cd auto-cpufreq/auto_cpufreq")
        print("python3 power_helper.py --gnome-power-disable")


# disable gnome >= 40 power profiles (live)
def gnome_power_disable_live():
    if(gnome_power_stats == 0):
        call(["systemctl", "stop", "power-profiles-daemon"])


# disable gnome >= 40 power profiles (install)
def gnome_power_svc_disable():
    if(gnome_power_stats == 0):
        print("\n* Disabling GNOME power profiles")
        call(["systemctl", "stop", "power-profiles-daemon"])
        call(["systemctl", "disable", "power-profiles-daemon"])
        call(["systemctl", "mask", "power-profiles-daemon"])
        call(["systemctl", "daemon-reload"])

# enable gnome >= 40 power profiles (uninstall)
def gnome_power_svc_enable():
    if(gnome_power_stats != 0):
        print("\n* Enabling GNOME power profiles")
        call(["systemctl", "unmask", "power-profiles-daemon"])
        call(["systemctl", "start", "power-profiles-daemon"])
        call(["systemctl", "enable", "power-profiles-daemon"])
        call(["systemctl", "daemon-reload"])

# gnome power profiles current status
def gnome_power_svc_status():
    print("\n* GNOME power profiles status")
    call(["systemctl", "status", "power-profiles-daemon"])

# gnome power removal reminder
def gnome_power_rm_reminder():
    if gnome_power_stats != 0:
        print("\n----------------------------------- Warning -----------------------------------\n")
        print("Detected GNOME Power Profiles daemon service is stopped!")
        print("Now it's recommended to enable this service.")
        print("\nSteps to perform this action using auto-cpufreq: power_helper script:")
        print("git clone https://github.com/AdnanHodzic/auto-cpufreq.git")
        print("cd auto-cpufreq/auto_cpufreq")
        print("python3 power_helper.py --gnome-power-enable")

def gnome_power_rm_reminder_snap():
        print("\n----------------------------------- Warning -----------------------------------\n")
        print("\nUnable to detect state of GNOME Power Profiles daemon service!")
        print("Now it's recommended to enable this service.")
        print("\nSteps to perform this action using auto-cpufreq: power_helper script:")
        print("git clone https://github.com/AdnanHodzic/auto-cpufreq.git")
        print("cd auto-cpufreq/auto_cpufreq")
        print("python3 power_helper.py --gnome-power-enable")

def valid_options():
    print("--gnome-power-enable\t\tEnable GNOME Power Profiles daemon")
    print("--gnome-power-disable\t\tDisable GNOME Power Profiles daemon\n")


# cli
@click.command()
@click.option("--gnome_power_enable", is_flag=True, help="Enable GNOME Power profiles service")
@click.option("--gnome_power_disable", is_flag=True, help="Disable GNOME Power profiles service")
@click.option("--gnome_power_status", is_flag=True, help="Get status of GNOME Power profiles service")
def main(gnome_power_enable, gnome_power_disable, gnome_power_status):

    root_check()
    if len(sys.argv) == 1:
        print("\n------------------------- auto-cpufreq: Power helper -------------------------\n")
        print("Unrecognized option!\n\nRun: \"" + app_name + " --help\" for list of available options.")
        footer()
    else:
        if gnome_power_enable:
            footer()
            root_check()
            print("Enabling GNOME Power Profiles")
            gnome_power_svc_enable()
            footer()
        elif gnome_power_disable:
            footer()
            root_check()
            print("Disabling GNOME Power Profiles")
            gnome_power_svc_disable()
            footer()
        elif gnome_power_status:
            footer()
            root_check()
            print("Status of GNOME Power Profiles")
            gnome_power_svc_status()
            footer()

if __name__ == '__main__':
    main()
