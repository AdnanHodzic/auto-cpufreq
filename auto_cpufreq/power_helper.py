# * add status as one of the available options
# * alert user on snap if detected and how to remove first time live/stats message starts
# * if daemon is disabled and auto-cpufreq is removed (snap) remind user to enable it back
from logging import root
import os, sys, click
from subprocess import getoutput, call, run, check_output, DEVNULL

sys.path.append("../")
from auto_cpufreq.core import *
from auto_cpufreq.tlp_stat_parser import TLPStatusParser

# app_name var
if sys.argv[0] == "power_helper.py":
    app_name = "python3 power_helper.py"
else:
    app_name = "auto-cpufreq"


def header():
    print("\n------------------------- auto-cpufreq: Power helper -------------------------\n")


def helper_opts():
    print("\nFor full list of options run: python3 power_helper.py --help")


# used to check if binary exists on the system
def does_command_exists(cmd):
    return which(cmd) is not None


systemctl_exists = does_command_exists("systemctl")
bluetoothctl_exists = does_command_exists("bluetoothctl")
tlp_stat_exists = does_command_exists("tlp-stat")
powerprofilesctl_exists = does_command_exists("powerprofilesctl")

# detect if gnome power profile service is running
if os.getenv("PKG_MARKER") != "SNAP":
    if systemctl_exists:
        try:
            gnome_power_status = call(
                ["systemctl", "is-active", "--quiet", "power-profiles-daemon"]
            )
        except:
            print("\nUnable to determine init system")
            print("If this causes any problems, please submit an issue:")
            print("https://github.com/AdnanHodzic/auto-cpufreq/issues")

# alert in case TLP service is running
def tlp_service_detect():
    if tlp_stat_exists:
        status_output = getoutput("tlp-stat -s")
        tlp_status = TLPStatusParser(status_output)
        if tlp_status.is_enabled():
            print(
                "\n----------------------------------- Warning -----------------------------------\n"
            )
            print("Detected you are running a TLP service!")
            print(
                "This daemon might interfere with auto-cpufreq which can lead to unexpected results."
            )
            print(
                "We strongly encourage you to remove TLP unless you really know what you are doing."
            )


# alert about TLP when using snap
def tlp_service_detect_snap():
    print("\n----------------------------------- Warning -----------------------------------\n")
    print("Unable to detect if you are using a TLP service!")
    print("This daemon might interfere with auto-cpufreq which can lead to unexpected results.")
    print("We strongly encourage you not to use TLP unless you really know what you are doing.")


# alert in case gnome power profile service is running
def gnome_power_detect():
    if systemctl_exists:
        if gnome_power_status == 0:
            print(
                "\n----------------------------------- Warning -----------------------------------\n"
            )
            print("Detected running GNOME Power Profiles daemon service!")
            print("This daemon might interfere with auto-cpufreq and should be disabled.")
            print("\nSteps to perform this action using auto-cpufreq: power_helper script:")
            print("git clone https://github.com/AdnanHodzic/auto-cpufreq.git")
            print("cd auto-cpufreq/auto_cpufreq")
            print("python3 power_helper.py --gnome_power_disable")


# automatically disable gnome power profile service in case it's running during install
def gnome_power_detect_install():
    if systemctl_exists:
        if gnome_power_status == 0:
            print(
                "\n----------------------------------- Warning -----------------------------------\n"
            )
            print("Detected running GNOME Power Profiles daemon service!")
            print("This daemon might interfere with auto-cpufreq and has been disabled.\n")
            print('This daemon is not automatically disabled in "monitor" mode and')
            print("will be enabled after auto-cpufreq is removed.\n")


# notification on snap
def gnome_power_detect_snap():
    print("\n----------------------------------- Warning -----------------------------------\n")
    print("Unable to detect state of GNOME Power Profiles daemon service!")
    print("This daemon might interfere with auto-cpufreq and should be disabled.")
    print("\nSteps to perform this action using auto-cpufreq: power_helper script:")
    print("git clone https://github.com/AdnanHodzic/auto-cpufreq.git")
    print("cd auto-cpufreq/auto_cpufreq")
    print("python3 power_helper.py --gnome_power_disable")


# stops gnome >= 40 power profiles (live)
def gnome_power_stop_live():
    if systemctl_exists:
        if gnome_power_status == 0 and powerprofilesctl_exists:
            call(["powerprofilesctl", "set", "balanced"])
            call(["systemctl", "stop", "power-profiles-daemon"])

# starts gnome >= 40 power profiles (live)
def gnome_power_start_live():
    if systemctl_exists:
        call(["systemctl", "start", "power-profiles-daemon"])

# enable gnome >= 40 power profiles (uninstall)
def gnome_power_svc_enable():
    if systemctl_exists:
        try:
            print("\n* Enabling GNOME power profiles")
            call(["systemctl", "unmask", "power-profiles-daemon"])
            call(["systemctl", "start", "power-profiles-daemon"])
            call(["systemctl", "enable", "power-profiles-daemon"])
            call(["systemctl", "daemon-reload"])
        except:
            print("\nUnable to enable GNOME power profiles")
            print("If this causes any problems, please submit an issue:")
            print("https://github.com/AdnanHodzic/auto-cpufreq/issues")


# gnome power profiles current status
def gnome_power_svc_status():
    if systemctl_exists:
        try:
            print("* GNOME power profiles status")
            call(["systemctl", "status", "power-profiles-daemon"])
        except:
            print("\nUnable to see GNOME power profiles status")
            print("If this causes any problems, please submit an issue:")
            print("https://github.com/AdnanHodzic/auto-cpufreq/issues")


# disable bluetooth on boot
def bluetooth_disable():
    if os.getenv("PKG_MARKER") == "SNAP":
        bluetooth_notif_snap()
    elif bluetoothctl_exists:
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
        print(
            "* Turn off bluetooth on boot [skipping] (package providing bluetooth access is not present)"
        )


# enable bluetooth on boot
def bluetooth_enable():
    if os.getenv("PKG_MARKER") == "SNAP":
        bluetooth_on_notif_snap()
    if bluetoothctl_exists:
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
        print(
            "* Turn on bluetooth on boot [skipping] (package providing bluetooth access is not present)"
        )


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
    if systemctl_exists:
        if gnome_power_status != 0:
            print(
                "\n----------------------------------- Warning -----------------------------------\n"
            )
            print("Detected GNOME Power Profiles daemon service is stopped!")
            print("This service will now be enabled and started again.")


def gnome_power_rm_reminder_snap():
    print("\n----------------------------------- Warning -----------------------------------\n")
    print("Unable to detect state of GNOME Power Profiles daemon service!")
    print("Now it's recommended to enable this service.")
    print("\nSteps to perform this action using auto-cpufreq: power_helper script:")
    print("git clone https://github.com/AdnanHodzic/auto-cpufreq.git")
    print("cd auto-cpufreq/auto_cpufreq")
    print("python3 power_helper.py --gnome_power_enable")


def valid_options():
    print("--gnome_power_enable\t\tEnable GNOME Power Profiles daemon")
    print("--gnome_power_disable\t\tDisable GNOME Power Profiles daemon\n")


def disable_power_profiles_daemon():
    # always disable power-profiles-daemon
    try:
        print("\n* Disabling GNOME power profiles")
        call(["systemctl", "stop", "power-profiles-daemon"])
        call(["systemctl", "disable", "power-profiles-daemon"])
        call(["systemctl", "mask", "power-profiles-daemon"])
        call(["systemctl", "daemon-reload"])
    except:
        print("\nUnable to disable GNOME power profiles")
        print("If this causes any problems, please submit an issue:")
        print("https://github.com/AdnanHodzic/auto-cpufreq/issues")


# default gnome_power_svc_disable func (balanced)
def gnome_power_svc_disable():
    if systemctl_exists:
        # set balanced profile if its running before disabling it
        if gnome_power_status == 0 and powerprofilesctl_exists:
            print("Using profile: ", "balanced")
            call(["powerprofilesctl", "set", "balanced"])

            disable_power_profiles_daemon()

# default gnome_power_svc_disable func (performance)
def gnome_power_svc_disable_performance():
    if systemctl_exists:
        # set performance profile if its running before disabling it
        if gnome_power_status == 0 and powerprofilesctl_exists:
            print("Using profile: ", "performance")
            call(["powerprofilesctl", "set", "performance"])

            disable_power_profiles_daemon()


# cli
@click.pass_context
# external gnome power srevice disable function
def gnome_power_svc_disable_ext(ctx, power_selection):
    raw_power_disable = ctx.params["gnome_power_disable"]
    gnome_power_disable = str(raw_power_disable).replace('[','').replace(']','').replace(",", "").replace("(","").replace(")","").replace("'","")

    if systemctl_exists:
        # 0 is active
        if gnome_power_status != 0:
            if os.getenv("PKG_MARKER") == "SNAP":
                print("Power Profiles Daemon is already disabled, re-enable by running:\n"
                        "sudo python3 power_helper.py --gnome_power_enable\n"
                        "\nfollowed by running:\n"
                        "sudo python3 power_helper.py --gnome_power_disable"
                        )
            else:
                print("Power Profiles Daemon is already disabled, first remove auto-cpufreq:\n"
                        "sudo auto-cpufreq --remove\n"
                        "\nfollowed by installing auto-cpufreq in performance mode:\n"
                        "sudo auto-cpufreq --install_performance"
                        )

        # set balanced profile if its running before disabling it
        if gnome_power_status == 0 and powerprofilesctl_exists:
            if os.getenv("PKG_MARKER") == "SNAP":
                print("Using profile: ", gnome_power_disable)
                call(["powerprofilesctl", "set", gnome_power_disable])

                disable_power_profiles_daemon()
            else:
                print("Install auto-cpufreq in performance mode by running:\n"
                        "sudo auto-cpufreq --install_performance\n"
                        )


@click.command()
@click.option("--gnome_power_disable", help="Disable GNOME Power profiles service (default: balanced)", type=click.Choice(['balanced', 'performance'], case_sensitive=False))
# ToDo:
# * update readme/docs
@click.option("--power_selection", hidden=True)
@click.option("--gnome_power_enable", is_flag=True, help="Enable GNOME Power profiles service")

@click.option("--gnome_power_status", is_flag=True, help="Get status of GNOME Power profiles service"
)
@click.option("--bluetooth_boot_on", is_flag=True, help="Turn on Bluetooth on boot")
@click.option("--bluetooth_boot_off", is_flag=True, help="Turn off Bluetooth on boot")
def main(
    power_selection,
    gnome_power_enable,
    gnome_power_disable,
    gnome_power_status,
    bluetooth_boot_off,
    bluetooth_boot_on,
):

    root_check()
    if len(sys.argv) == 1:
        header()
        print(
            'Unrecognized option!\n\nRun: "' + app_name + ' --help" for list of available options.'
        )
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
            gnome_power_svc_disable_ext(power_selection)
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


if __name__ == "__main__":
    main()
