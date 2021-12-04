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

def header():
    print("\n------------------------- auto-cpufreq: Power helper -------------------------\n")

def helper_opts():
    print("\nFor full list of options run: python3 power_helper.py --help")

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
        print("* Disabling GNOME power profiles")
        call(["systemctl", "stop", "power-profiles-daemon"])
        call(["systemctl", "disable", "power-profiles-daemon"])
        call(["systemctl", "mask", "power-profiles-daemon"])
        call(["systemctl", "daemon-reload"])
    else:
        print("* GNOME power profiles already disabled")

# enable gnome >= 40 power profiles (uninstall)
def gnome_power_svc_enable():
    if(gnome_power_stats != 0):
        print("* Enabling GNOME power profiles")
        call(["systemctl", "unmask", "power-profiles-daemon"])
        call(["systemctl", "start", "power-profiles-daemon"])
        call(["systemctl", "enable", "power-profiles-daemon"])
        call(["systemctl", "daemon-reload"])
    else:
        print("* GNOME power profiles already enabled")


# gnome power profiles current status
def gnome_power_svc_status():
    print("* GNOME power profiles status")
    call(["systemctl", "status", "power-profiles-daemon"])


# disable bluetooth on boot
def bluetooth_disable():
    if os.getenv("PKG_MARKER") == "SNAP":
        bluetooth_notif_snap()
    elif which("bluetoothctl") is not None:
        print("* Turn off bluetooth on boot")
        btconf = Path("/etc/bluetooth/main.conf")
        try:
            orig_set = "AutoEnable=true"
            change_set = "AutoEnable=false"
            with btconf.open(mode="r+") as f:
                content = f.read()
                f.seek(0)
                f.truncate()
                f.write(content.replace(orig_set, change_set))
        except Exception as e:
            print(f"\nERROR:\nWas unable to turn off bluetooth on boot\n{repr(e)}")
    else:
        print("* Turn off bluetooth on boot [skipping] (package providing bluetooth access is not present)")


# enable bluetooth on boot
def bluetooth_enable():
    if os.getenv("PKG_MARKER") == "SNAP":
        bluetooth_on_notif_snap()
    if which("bluetoothctl") is not None:
        print("* Turn on bluetooth on boot")
        btconf = "/etc/bluetooth/main.conf"
        try:
            orig_set = "AutoEnable=true"
            change_set = "AutoEnable=false"
            with open(btconf, "r+") as f:
                content = f.read()
                f.seek(0)
                f.truncate()
                f.write(content.replace(change_set, orig_set))
        except Exception as e:
            print(f"\nERROR:\nWas unable to turn on bluetooth on boot\n{repr(e)}")
    else:
        print("* Turn on bluetooth on boot [skipping] (package providing bluetooth access is not present)")


# turn off bluetooth on snap message
def bluetooth_notif_snap():
    print("\n* Unable to turn off bluetooth on boot due to Snap package restrictions!")
    print("\nSteps to perform this action using auto-cpufreq: power_helper script:")
    print("python3 power_helper.py --bluetooth_boot_off")

# turn off bluetooth on snap message
def bluetooth_on_notif_snap():
    print("\n* Unable to turn on bluetooth on boot due to Snap package restrictions!")
    print("\nSteps to perform this action using auto-cpufreq: power_helper script:")
    print("python3 power_helper.py --bluetooth_boot_on")

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
        print("Unable to detect state of GNOME Power Profiles daemon service!")
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
@click.option("--bluetooth_boot_on", is_flag=True, help="Turn on Bluetooth on boot")
@click.option("--bluetooth_boot_off", is_flag=True, help="Turn off Bluetooth on boot")
def main(gnome_power_enable, gnome_power_disable, gnome_power_status, bluetooth_boot_off, bluetooth_boot_on):

    root_check()
    if len(sys.argv) == 1:
        header()
        print("Unrecognized option!\n\nRun: \"" + app_name + " --help\" for list of available options.")
        footer()
    else:
        if gnome_power_enable:
            header()
            root_check()
            gnome_power_svc_enable()
            helper_opts()
            footer()
        elif gnome_power_disable:
            header()
            root_check()
            gnome_power_svc_disable()
            helper_opts()
            footer()
        elif gnome_power_status:
            header()
            root_check()
            gnome_power_svc_status()
            helper_opts()
            footer()
        elif bluetooth_boot_off:
            header()
            root_check()
            bluetooth_disable()
            helper_opts()
            footer()
        elif bluetooth_boot_on:
            header()
            root_check()
            bluetooth_enable()
            helper_opts()
            footer()

if __name__ == '__main__':
    main()
