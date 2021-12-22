#!/usr/bin/env python3
#
# auto-cpufreq - core functionality

import os
import platform as pl
import shutil
import sys
import psutil
import distro
import time
import click
import warnings
import configparser
from math import isclose
from pathlib import Path
from shutil import which
from subprocess import getoutput, call, run, check_output, DEVNULL

sys.path.append("../")
from auto_cpufreq.power_helper import *

warnings.filterwarnings("ignore")

# ToDo:
# - re-enable CPU fan speed display and make more generic and not only for thinkpad
# - replace get system/CPU load from: psutil.getloadavg() | available in 5.6.2)

SCRIPTS_DIR = Path("/usr/local/share/auto-cpufreq/scripts/")

# from the highest performance to the lowest
ALL_GOVERNORS = (
    "performance",
    "ondemand",
    "conservative",
    "schedutil",
    "userspace",
    "powersave",
)
CPUS = os.cpu_count()

# Note:
# "load1m" & "cpuload" can't be global vars and to in order to show correct data must be
# decraled where their execution takes place

# powersave/performance system load thresholds
powersave_load_threshold = (75 * CPUS) / 100
performance_load_threshold = (50 * CPUS) / 100

# auto-cpufreq stats file path
auto_cpufreq_stats_path = None
auto_cpufreq_stats_file = None

if os.getenv("PKG_MARKER") == "SNAP":
    auto_cpufreq_stats_path = Path("/var/snap/auto-cpufreq/current/auto-cpufreq.stats")
else:
    auto_cpufreq_stats_path = Path("/var/run/auto-cpufreq.stats")

# daemon check
dcheck = getoutput("snapctl get daemon")


def file_stats():
    global auto_cpufreq_stats_file
    auto_cpufreq_stats_file = open(auto_cpufreq_stats_path, "w")
    sys.stdout = auto_cpufreq_stats_file


def get_config(config_file=""):
    if not hasattr(get_config, "dict"):
        get_config.dict = dict()

        config = configparser.ConfigParser()
        config.read(config_file)

        for section in config.sections():
            get_config.dict[section] = dict(config.items(section))

    return get_config.dict


# get distro name
try:
    dist_name = distro.id()
except PermissionError:
    # Current work-around for Pop!_OS where symlink causes permission issues
    print("Warning: Cannot get distro name")
    if os.path.exists("/etc/pop-os/os-release"):
        print("Pop!_OS detected")
        print(
            "Pop!_OS uses a symbolic link for the os-release file, this causes issues and can be fixed by converting to a hard link"
        )
        print(
            "You can change the symbolic link to a hard link for /etc/os-release -> /etc/pop-os/os-release"
        )

        yN = input("Continue? [y/N] ")
        print()
        if yN.lower() == "y":
            
            # Check if using a Snap install (How do I do this?)
            isSnap = False
            if isSnap:
                print(
                    "Snap install detected, you must manually run the following commands in another terminal:"
                )
                print()
                print("Backup the /etc/os-release file:")
                print("sudo mv /etc/os-release /etc/os-release-backup")
                print()
                input("Press [Enter] to continue...")
                print()
                print("Create hard link to /etc/os-release:")
                print("sudo ln /etc/pop-os/os-release /etc/os-release")
                print()
                input("Press [Enter] to continue...")
            
            # Runs when installed with installer/manually
            else:
                # Backup /etc/os-release
                print("Backing up /etc/os-release to /etc/os-release-backup")
                os.system("sudo mv /etc/os-release /etc/os-release-backup")
                # Create hard link to /etc/os-release
                print("Creating hard link for /etc/os-release")
                os.system("sudo ln /etc/pop-os/os-release /etc/os-release")
            print()
            print("Checking to see if solution worked...")
            try:
                dist_name = distro.id()
                print("Success!")
            except PermissionError:
                print("Failed, aborting...")
                sys.exit(1)
        else:
            print("Operation aborted by user")
            sys.exit(1)
    else:
        print("Check /etc/os-release permissions and make sure it is not a symbolic link")
        print("Aborting...")
        sys.exit(1)

# display running version of auto-cpufreq
def app_version():

    print("auto-cpufreq version:")

    # snap package
    if os.getenv("PKG_MARKER") == "SNAP":
        print(getoutput("echo Snap: $SNAP_VERSION"))
    # aur package
    elif dist_name in ["arch", "manjaro", "garuda"]:
        aur_pkg_check = call("pacman -Qs auto-cpufreq > /dev/null", shell=True)
        if aur_pkg_check == 1:
            print(
                "Git commit:",
                check_output(["git", "describe", "--always"]).strip().decode(),
            )
        else:
            print(getoutput("pacman -Qi auto-cpufreq | grep Version"))
    else:
        # source code (auto-cpufreq-installer)
        try:
            print(
                "Git commit:",
                check_output(["git", "describe", "--always"]).strip().decode(),
            )
        except Exception as e:
            print(repr(e))
            pass


def app_res_use():
    p = psutil.Process()
    print("auto-cpufreq system resource consumption:")
    print("cpu usage:", p.cpu_percent(), "%")
    print("memory use:", round(p.memory_percent(), 2), "%")


# set/change state of turbo
def turbo(value: bool = None):
    """
    Get and set turbo mode
    """
    p_state = Path("/sys/devices/system/cpu/intel_pstate/no_turbo")
    cpufreq = Path("/sys/devices/system/cpu/cpufreq/boost")

    if p_state.exists():
        inverse = True
        f = p_state
    elif cpufreq.exists():
        f = cpufreq
        inverse = False
    else:
        print("Warning: CPU turbo is not available")
        return False

    if value is not None:
        if inverse:
            value = not value

        try:
            f.write_text(str(int(value)) + "\n")
        except PermissionError:
            print("Warning: Changing CPU turbo is not supported. Skipping.")
            return False

    value = bool(int(f.read_text().strip()))
    if inverse:
        value = not value

    return value


# display current state of turbo
def get_turbo():

    if turbo():
        print("Currently turbo boost is: on")
    else:
        print("Currently turbo boost is: off")


def charging():
    """
    get charge state: is battery charging or discharging
    """
    power_supply_path = "/sys/class/power_supply/"
    power_supplies = os.listdir(Path(power_supply_path))

    # check if we found power supplies. on a desktop these are not found
    # and we assume we are on a powercable.
    if len(power_supplies) == 0:
        # nothing found found, so nothing to check
        return True
    # we found some power supplies, lets check their state
    else:
        for supply in power_supplies:
            # skip battery of hid devices
            # see issue #321
            if "hid" in supply.lower():
                continue
            try:
                with open(Path(power_supply_path + supply + "/type")) as f:
                    supply_type = f.read()[:-1]
                    if supply_type == "Mains":
                        # we found an AC
                        try:
                            with open(Path(power_supply_path + supply + "/online")) as f:
                                val = int(f.read()[:-1])
                                if val == 1:
                                    # we are definitely charging
                                    return True
                        except FileNotFoundError:
                            # we could not find online, check next item
                            continue
                    elif supply_type == "Battery":
                        # we found a battery, check if its being discharged
                        try:
                            with open(Path(power_supply_path + supply + "/status")) as f:
                                val = str(f.read()[:-1])
                                if val == "Discharging":
                                    # we found a discharging battery
                                    return False
                        except FileNotFoundError:
                            # could not find status, check the next item
                            continue
                    else:
                        # continue to next item because current is not
                        # "Mains" or "Battery"
                        continue
            except FileNotFoundError:
                # could not find type, check the next item
                continue

    # we cannot determine discharging state, assume we are on powercable
    return True


def get_avail_gov():
    f = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors")
    return f.read_text().strip().split(" ")


def get_avail_powersave():
    """
    Iterate over ALL_GOVERNORS in reverse order: from powersave to performance
    :return:
    """
    for g in ALL_GOVERNORS[::-1]:
        if g in get_avail_gov():
            return g


def get_avail_performance():
    for g in ALL_GOVERNORS:
        if g in get_avail_gov():
            return g


def get_current_gov():
    return print(
        "Currently using:",
        getoutput("cpufreqctl.auto-cpufreq --governor").strip().split(" ")[0],
        "governor",
    )


def cpufreqctl():
    """
    deploy cpufreqctl script
    """

    # detect if running on a SNAP
    if os.getenv("PKG_MARKER") == "SNAP":
        pass
    else:
        # deploy cpufreqctl.auto-cpufreq script
        if os.path.isfile("/usr/bin/cpufreqctl"):
            shutil.copy(SCRIPTS_DIR / "cpufreqctl.sh", "/usr/bin/cpufreqctl.auto-cpufreq")
        else:
            shutil.copy(SCRIPTS_DIR / "cpufreqctl.sh", "/usr/bin/cpufreqctl.auto-cpufreq")


def cpufreqctl_restore():
    """
    remove cpufreqctl.auto-cpufreq script
    """
    # detect if running on a SNAP
    if os.getenv("PKG_MARKER") == "SNAP":
        pass
    else:
        if os.path.isfile("/usr/bin/cpufreqctl.auto-cpufreq"):
            os.remove("/usr/bin/cpufreqctl.auto-cpufreq")


def footer(l=79):
    print("\n" + "-" * l + "\n")


def daemon_not_found():
    print("\n" + "-" * 32 + " Daemon check " + "-" * 33 + "\n")
    print(
        "ERROR:\n\nDaemon not enabled, must run install first, i.e: \nsudo auto-cpufreq --install"
    )
    footer()


def deploy_complete_msg():
    print("\n" + "-" * 17 + " auto-cpufreq daemon installed and running " + "-" * 17 + "\n")
    print("To view live stats, run:\nauto-cpufreq --stats")
    print("\nTo disable and remove auto-cpufreq daemon, run:\nsudo auto-cpufreq --remove")
    footer()


def deprecated_log_msg():
    print("\n" + "-" * 24 + " auto-cpufreq log file renamed " + "-" * 24 + "\n")
    print("The --log flag has been renamed to --stats\n")
    print("To view live stats, run:\nauto-cpufreq --stats")
    footer()


def remove_complete_msg():
    print("\n" + "-" * 25 + " auto-cpufreq daemon removed " + "-" * 25 + "\n")
    print("auto-cpufreq successfully removed.")
    footer()


def deploy_daemon():
    print("\n" + "-" * 21 + " Deploying auto-cpufreq as a daemon " + "-" * 22 + "\n")

    # deploy cpufreqctl script func call
    cpufreqctl()

    # turn off bluetooth on boot
    bluetooth_disable()

    auto_cpufreq_stats_path.touch(exist_ok=True)

    print("\n* Deploy auto-cpufreq install script")
    shutil.copy(SCRIPTS_DIR / "auto-cpufreq-install.sh", "/usr/bin/auto-cpufreq-install")

    print("\n* Deploy auto-cpufreq remove script")
    shutil.copy(SCRIPTS_DIR / "auto-cpufreq-remove.sh", "/usr/bin/auto-cpufreq-remove")

    # output warning if gnome power profile is running
    gnome_power_detect_install()
    gnome_power_svc_disable()

    # output warning if TLP service is detected
    tlp_service_detect()

    call("/usr/bin/auto-cpufreq-install", shell=True)


# remove auto-cpufreq daemon
def remove():

    # check if auto-cpufreq is installed
    if not os.path.exists("/usr/bin/auto-cpufreq-remove"):
        print("\nauto-cpufreq daemon is not installed.\n")
        sys.exit(1)

    print("\n" + "-" * 21 + " Removing auto-cpufreq daemon " + "-" * 22 + "\n")

    # turn on bluetooth on boot
    bluetooth_enable()

    # output warning if gnome power profile is stopped
    gnome_power_rm_reminder()
    gnome_power_svc_enable()

    # run auto-cpufreq daemon remove script
    call("/usr/bin/auto-cpufreq-remove", shell=True)

    # remove auto-cpufreq-remove
    os.remove("/usr/bin/auto-cpufreq-remove")

    # delete stats file
    if auto_cpufreq_stats_path.exists():
        if auto_cpufreq_stats_file is not None:
            auto_cpufreq_stats_file.close()

        auto_cpufreq_stats_path.unlink()

    # restore original cpufrectl script
    cpufreqctl_restore()


def gov_check():
    for gov in get_avail_gov():
        if gov not in ALL_GOVERNORS:
            print("\n" + "-" * 18 + " Checking for necessary scaling governors " + "-" * 19 + "\n")
            sys.exit("ERROR:\n\nCouldn't find any of the necessary scaling governors.\n")


# root check func
def root_check():
    if not os.geteuid() == 0:
        print("\n" + "-" * 33 + " Root check " + "-" * 34 + "\n")
        print("ERROR:\n\nMust be run root for this functionality to work, i.e: \nsudo " + app_name)
        footer()
        exit(1)


# refresh countdown
def countdown(s):
    # Fix for wrong stats output and "TERM environment variable not set"
    os.environ["TERM"] = "xterm"

    for remaining in range(s, 0, -1):
        sys.stdout.write("\r")
        sys.stdout.write('\t\t\t"auto-cpufreq" refresh in:{:2d}'.format(remaining))
        sys.stdout.flush()
        time.sleep(1)

    if auto_cpufreq_stats_file is not None:
        auto_cpufreq_stats_file.seek(0)
        auto_cpufreq_stats_file.truncate(0)

        # execution timestamp
        from datetime import datetime

        now = datetime.now()
        current_time = now.strftime("%B %d (%A) - %H:%M:%S")
        print("\n\t\tExecuted on:", current_time)

    else:
        run("clear")


# get cpu usage + system load for (last minute)
def display_load():

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m)
    print("Average temp. of all cores:", avg_all_core_temp, "°C", "\n")


# set powersave and enable turbo
def set_powersave():
    gov = get_config()
    if "battery" in gov:
        if "governor" in gov["battery"]:
            gov = gov["battery"]["governor"]
    else:
        gov = get_avail_powersave()
    print(f'Setting to use: "{gov}" governor')
    run(f"cpufreqctl.auto-cpufreq --governor --set={gov}", shell=True)
    if (
        Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference").exists()
        and Path("/sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost").exists() is False
    ):
        run("cpufreqctl.auto-cpufreq --epp --set=balance_power", shell=True)
        print('Setting to use: "balance_power" EPP')

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m)
    print("Average temp. of all cores:", avg_all_core_temp, "°C")

    # conditions for setting turbo in powersave
    auto = get_config()
    if "battery" in auto:
        if "turbo" in auto["battery"]:
            auto = auto["battery"]["turbo"]
    else:
        auto = "auto"

    if auto == "always":
        print("Configuration file enforces turbo boost")
        print("setting turbo boost: on")
        turbo(True)
    elif auto == "never":
        print("Configuration file disables turbo boost")
        print("setting turbo boost: off")
        turbo(False)
    else:
        if psutil.cpu_percent(percpu=False, interval=0.01) >= 30.0 or isclose(
            max(psutil.cpu_percent(percpu=True, interval=0.01)), 100
        ):
            print("\nHigh CPU load")

            # high cpu usage trigger
            if cpuload >= 20:
                print("setting turbo boost: on")
                turbo(True)

            # set turbo state based on average of all core temperatures
            elif cpuload <= 20 and avg_all_core_temp >= 70:
                print(
                    "Optimal total CPU usage:",
                    cpuload,
                    "%, high average core temp:",
                    avg_all_core_temp,
                    "°C",
                )
                print("setting turbo boost: off")
                turbo(False)
            else:
                print("setting turbo boost: off")
                turbo(False)

        elif load1m > powersave_load_threshold:
            print("\nHigh system load")

            # high cpu usage trigger
            if cpuload >= 20:
                print("setting turbo boost: on")
                turbo(True)

            # set turbo state based on average of all core temperatures
            elif cpuload <= 20 and avg_all_core_temp >= 65:
                print(
                    "Optimal total CPU usage:",
                    cpuload,
                    "%, high average core temp:",
                    avg_all_core_temp,
                    "°C",
                )
                print("setting turbo boost: off")
                turbo(False)
            else:
                print("setting turbo boost: off")
                turbo(False)

        else:
            print("\nLoad optimal")

            # high cpu usage trigger
            if cpuload >= 20:
                print("setting turbo boost: on")
                turbo(True)

            # set turbo state based on average of all core temperatures
            elif cpuload <= 20 and avg_all_core_temp >= 60:
                print(
                    "Optimal total CPU usage:",
                    cpuload,
                    "%, high average core temp:",
                    avg_all_core_temp,
                    "°C",
                )
                print("setting turbo boost: off")
                turbo(False)
            else:
                print("setting turbo boost: off")
                turbo(False)

    footer()


# make turbo suggestions in powersave
def mon_powersave():

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m)
    print("Average temp. of all cores:", avg_all_core_temp, "°C")

    if psutil.cpu_percent(percpu=False, interval=0.01) >= 30.0 or isclose(
        max(psutil.cpu_percent(percpu=True, interval=0.01)), 100
    ):
        print("\nHigh CPU load")

        # high cpu usage trigger
        if cpuload >= 20:
            print("suggesting to set turbo boost: on")
            get_turbo()

        # set turbo state based on average of all core temperatures
        elif cpuload <= 20 and avg_all_core_temp >= 70:
            print(
                "Optimal total CPU usage:",
                cpuload,
                "%, high average core temp:",
                avg_all_core_temp,
                "°C",
            )
            print("suggesting to set turbo boost: off")
            get_turbo()
        else:
            print("suggesting to set turbo boost: off")
            get_turbo()

    elif load1m > powersave_load_threshold:
        print("\nHigh system load")

        # high cpu usage trigger
        if cpuload >= 20:
            print("suggesting to set turbo boost: on")
            get_turbo()

        # set turbo state based on average of all core temperatures
        elif cpuload <= 20 and avg_all_core_temp >= 65:
            print(
                "Optimal total CPU usage:",
                cpuload,
                "%, high average core temp:",
                avg_all_core_temp,
                "°C",
            )
            print("suggesting to set turbo boost: off")
            get_turbo()
        else:
            print("suggesting to set turbo boost: off")
            get_turbo()

    else:
        print("\nLoad optimal")

        # high cpu usage trigger
        if cpuload >= 20:
            print("suggesting to set turbo boost: on")
            get_turbo()

        # set turbo state based on average of all core temperatures
        elif cpuload <= 20 and avg_all_core_temp >= 60:
            print(
                "Optimal total CPU usage:",
                cpuload,
                "%, high average core temp:",
                avg_all_core_temp,
                "°C",
            )
            print("suggesting to set turbo boost: off")
            get_turbo()
        else:
            print("suggesting to set turbo boost: off")
            get_turbo()

    footer()


# set performance and enable turbo
def set_performance():
    gov = get_config()
    if "charger" in gov:
        if "governor" in gov["charger"]:
            gov = gov["charger"]["governor"]
    else:
        gov = get_avail_performance()

    print(f'Setting to use: "{gov}" governor')
    run(
        f"cpufreqctl.auto-cpufreq --governor --set={gov}",
        shell=True,
    )
    if (
        Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference").exists()
        and Path("/sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost").exists() is False
    ):
        run("cpufreqctl.auto-cpufreq --epp --set=balance_performance", shell=True)
        print('Setting to use: "balance_performance" EPP')

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m)
    print("Average temp. of all cores:", avg_all_core_temp, "°C")

    auto = get_config()
    if "charger" in auto:
        if "turbo" in auto["charger"]:
            auto = auto["charger"]["turbo"]
    else:
        auto = "auto"

    if auto == "always":
        print("Configuration file enforces turbo boost")
        print("setting turbo boost: on")
        turbo(True)
    elif auto == "never":
        print("Configuration file disables turbo boost")
        print("setting turbo boost: off")
        turbo(True)
    else:
        if (
            psutil.cpu_percent(percpu=False, interval=0.01) >= 20.0
            or max(psutil.cpu_percent(percpu=True, interval=0.01)) >= 75
        ):
            print("\nHigh CPU load")

            # high cpu usage trigger
            if cpuload >= 20:
                print("setting turbo boost: on")
                turbo(True)

            # set turbo state based on average of all core temperatures
            elif avg_all_core_temp >= 70:
                print(
                    "Optimal total CPU usage:",
                    cpuload,
                    "%, high average core temp:",
                    avg_all_core_temp,
                    "°C",
                )
                print("setting turbo boost: off")
                turbo(False)
            else:
                print("setting turbo boost: on")
                turbo(True)

        elif load1m >= performance_load_threshold:
            print("\nHigh system load")

            # high cpu usage trigger
            if cpuload >= 20:
                print("setting turbo boost: on")
                turbo(True)

            # set turbo state based on average of all core temperatures
            elif avg_all_core_temp >= 65:
                print(
                    "Optimal total CPU usage:",
                    cpuload,
                    "%, high average core temp:",
                    avg_all_core_temp,
                    "°C",
                )
                print("setting turbo boost: off")
                turbo(False)
            else:
                print("setting turbo boost: on")
                turbo(True)

        else:
            print("\nLoad optimal")

            # high cpu usage trigger
            if cpuload >= 20:
                print("setting turbo boost: on")
                turbo(True)

            # set turbo state based on average of all core temperatures
            elif avg_all_core_temp >= 60:
                print(
                    "Optimal total CPU usage:",
                    cpuload,
                    "%, high average core temp:",
                    avg_all_core_temp,
                    "°C",
                )
                print("setting turbo boost: off")
                turbo(False)
            else:
                print("setting turbo boost: off")
                turbo(False)

    footer()


# make turbo suggestions in performance
def mon_performance():

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m)
    print("Average temp. of all cores:", avg_all_core_temp, "°C")

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    if (
        psutil.cpu_percent(percpu=False, interval=0.01) >= 20.0
        or max(psutil.cpu_percent(percpu=True, interval=0.01)) >= 75
    ):
        print("\nHigh CPU load")

        # high cpu usage trigger
        if cpuload >= 20:
            print("suggesting to set turbo boost: on")
            get_turbo()

        # set turbo state based on average of all core temperatures
        elif cpuload <= 25 and avg_all_core_temp >= 70:
            print(
                "Optimal total CPU usage:",
                cpuload,
                "%, high average core temp:",
                avg_all_core_temp,
                "°C",
            )
            print("suggesting to set turbo boost: off")
            get_turbo()
        else:
            print("suggesting to set turbo boost: on")
            get_turbo()

    elif load1m > performance_load_threshold:
        print("\nHigh system load")

        # high cpu usage trigger
        if cpuload >= 20:
            print("suggesting to set turbo boost: on")
            get_turbo()

        # set turbo state based on average of all core temperatures
        elif cpuload <= 25 and avg_all_core_temp >= 65:
            print(
                "Optimal total CPU usage:",
                cpuload,
                "%, high average core temp:",
                avg_all_core_temp,
                "°C",
            )
            print("suggesting to set turbo boost: off")
            get_turbo()
        else:
            print("suggesting to set turbo boost: on")
            get_turbo()

    else:
        print("\nLoad optimal")

        # high cpu usage trigger
        if cpuload >= 20:
            print("suggesting to set turbo boost: on")
            get_turbo()

        # set turbo state based on average of all core temperatures
        elif cpuload <= 25 and avg_all_core_temp >= 60:
            print(
                "Optimal total CPU usage:",
                cpuload,
                "%, high average core temp:",
                avg_all_core_temp,
                "°C",
            )
            print("suggesting to set turbo boost: off")
            get_turbo()
        else:
            print("suggesting to set turbo boost: on")
            get_turbo()

    footer()


def set_autofreq():
    """
    set cpufreq governor based if device is charging
    """
    print("\n" + "-" * 28 + " CPU frequency scaling " + "-" * 28 + "\n")

    # determine which governor should be used
    if charging():
        print("Battery is: charging\n")
        set_performance()
    else:
        print("Battery is: discharging\n")
        set_powersave()


def mon_autofreq():
    """
    make cpufreq suggestions
    :return:
    """
    print("\n" + "-" * 28 + " CPU frequency scaling " + "-" * 28 + "\n")

    # determine which governor should be used
    if charging():
        print("Battery is: charging\n")
        get_current_gov()
        print(f'Suggesting use of "{get_avail_performance()}" governor')
        mon_performance()
    else:
        print("Battery is: discharging\n")
        get_current_gov()
        print(f'Suggesting use of "{get_avail_powersave()}" governor')
        mon_powersave()


def python_info():
    print("Python:", pl.python_version())
    print("psutil package:", psutil.__version__)
    print("platform package:", pl.__version__)
    print("click package:", click.__version__)
    # workaround: Module 'distro' has no '__version__' member () (https://github.com/nir0s/distro/issues/265)
    # print("distro:", distro.__version__)
    run(
        "echo \"distro package\" $(pip3 show distro | sed -n -e 's/^.*Version: //p')",
        shell=True,
    )


def device_info():
    print("Computer type:", getoutput("dmidecode --string chassis-type"))


def distro_info():
    dist = "UNKNOWN distro"
    version = "UNKNOWN version"

    # get distro information in snap env.
    if os.getenv("PKG_MARKER") == "SNAP":
        try:
            with open("/var/lib/snapd/hostfs/etc/os-release", "r") as searchfile:
                for line in searchfile:
                    if line.startswith("NAME="):
                        dist = line[5 : line.find("$")].strip('"')
                        continue
                    elif line.startswith("VERSION="):
                        version = line[8 : line.find("$")].strip('"')
                        continue
        except PermissionError as e:
            print(repr(e))
            pass

        dist = f"{dist} {version}"
    else:
        # get distro information
        fdist = distro.linux_distribution()
        dist = " ".join(x for x in fdist)

    print("Linux distro: " + dist)
    print("Linux kernel: " + pl.release())


def sysinfo():
    """
    get system information
    """

    # processor_info
    model_name = getoutput("egrep 'model name' /proc/cpuinfo -m 1").split(":")[-1]
    print(f"Processor:{model_name}")

    # get core count
    total_cpu_count = int(getoutput("nproc --all"))
    print("Cores:", total_cpu_count)

    # get architecture
    cpu_arch = pl.machine()
    print("Architecture:", cpu_arch)

    # get driver
    driver = getoutput("cpufreqctl.auto-cpufreq --driver")
    print("Driver: " + driver)

    # get usage and freq info of cpus
    usage_per_cpu = psutil.cpu_percent(interval=1, percpu=True)
    # psutil current freq not used, gives wrong values with offline cpu's
    minmax_freq_per_cpu = psutil.cpu_freq(percpu=True)

    # max and min freqs, psutil reports wrong max/min freqs whith offline cores with percpu=False
    max_freq = max([freq.max for freq in minmax_freq_per_cpu])
    min_freq = min([freq.min for freq in minmax_freq_per_cpu])
    print("\n" + "-" * 30 + " Current CPU stats " + "-" * 30 + "\n")
    print(f"CPU max frequency: {max_freq:.0f} MHz")
    print(f"CPU min frequency: {min_freq:.0f} MHz\n")

    # get coreid's and frequencies of online cpus by parsing /proc/cpuinfo
    coreid_info = getoutput("egrep 'processor|cpu MHz|core id' /proc/cpuinfo").split("\n")
    cpu_core = dict()
    freq_per_cpu = []
    for i in range(0, len(coreid_info), 3):
        freq_per_cpu.append(float(coreid_info[i + 1].split(":")[-1]))
        cpu = int(coreid_info[i].split(":")[-1])
        core = int(coreid_info[i + 2].split(":")[-1])
        cpu_core[cpu] = core

    online_cpu_count = len(cpu_core)
    offline_cpus = [str(cpu) for cpu in range(total_cpu_count) if cpu not in cpu_core]

    # temperatures
    core_temp = psutil.sensors_temperatures()
    temp_per_cpu = [float("nan")] * online_cpu_count
    try:
        if "coretemp" in core_temp:
            # list labels in 'coretemp'
            core_temp_labels = [temp.label for temp in core_temp["coretemp"]]
            for i, cpu in enumerate(cpu_core):
                # get correct index in core_temp
                core = cpu_core[cpu]
                cpu_temp_index = core_temp_labels.index(f"Core {core}")
                temp_per_cpu[i] = core_temp["coretemp"][cpu_temp_index].current
        elif "k10temp" in core_temp:
            # https://www.kernel.org/doc/Documentation/hwmon/k10temp
            temp_per_cpu = [core_temp["k10temp"][0].current] * online_cpu_count
        elif "zenpower" in core_temp:
            # https://github.com/AdnanHodzic/auto-cpufreq/issues/145#issuecomment-763294009
            temp_per_cpu = [core_temp["zenpower"][0].current] * online_cpu_count
        elif "acpitz" in core_temp:
            temp_per_cpu = [core_temp["acpitz"][0].current] * online_cpu_count
        elif "thinkpad" in core_temp:
            temp_per_cpu = [core_temp["thinkpad"][0].current] * online_cpu_count
    except Exception as e:
        print(repr(e))
        pass

    print("Core\tUsage\tTemperature\tFrequency")
    for (cpu, usage, freq, temp) in zip(cpu_core, usage_per_cpu, freq_per_cpu, temp_per_cpu):
        print(f"CPU{cpu}:\t{usage:>5.1f}%    {temp:>3.0f} °C    {freq:>5.0f} MHz")

    if offline_cpus:
        print(f"\nDisabled CPUs: {','.join(offline_cpus)}")

    # get average temperature of all cores
    avg_cores_temp = sum(temp_per_cpu)
    global avg_all_core_temp
    avg_all_core_temp = float(avg_cores_temp / online_cpu_count)

    # print current fan speed | temporarily commented
    # current_fans = psutil.sensors_fans()['thinkpad'][0].current
    # print("\nCPU fan speed:", current_fans, "RPM")


def no_stats_msg():
    print("\n" + "-" * 29 + " auto-cpufreq stats " + "-" * 30 + "\n")
    print(
        'ERROR: auto-cpufreq stats are missing.\n\nMake sure to run: "auto-cpufreq --install" first'
    )


# read stats func
def read_stats():
    # read stats
    if os.path.isfile(auto_cpufreq_stats_path):
        call(["tail", "-n 50", "-f", str(auto_cpufreq_stats_path)], stderr=DEVNULL)
    else:
        no_stats_msg()
    footer()


# check if program (argument) is running
def is_running(program, argument):
    # iterate over all processes found by psutil
    # and find the one with name and args passed to the function
    for p in psutil.process_iter():
        for s in filter(lambda x: program in x, p.cmdline()):
            if argument in p.cmdline():
                return True


def daemon_running_msg():
    print("\n" + "-" * 24 + " auto-cpufreq running " + "-" * 30 + "\n")
    print(
        "ERROR: auto-cpufreq is running in daemon mode.\n\nMake sure to stop the deamon before running with --live or --monitor mode"
    )
    footer()


# check if auto-cpufreq --daemon is running
def running_daemon():
    if is_running("auto-cpufreq", "--daemon"):
        daemon_running_msg()
        exit(1)
    elif os.getenv("PKG_MARKER") == "SNAP" and dcheck == "enabled":
        daemon_running_msg()
        exit(1)
