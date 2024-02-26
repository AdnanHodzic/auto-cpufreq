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
import pickle
import warnings
import configparser
# import pkg_resources
import importlib.metadata
from math import isclose
from pathlib import Path
from shutil import which
from subprocess import getoutput, call, run, check_output, DEVNULL
import requests
import re

# execution timestamp used in countdown func
from datetime import datetime

sys.path.append("../")
from auto_cpufreq.power_helper import *

warnings.filterwarnings("ignore")

# add path to auto-cpufreq executables for GUI
os.environ["PATH"] += ":/usr/local/bin"

# ToDo:
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

# ignore these devices under /sys/class/power_supply/
POWER_SUPPLY_IGNORELIST = ["hidpp_battery"]

# Note:
# "load1m" & "cpuload" can't be global vars and to in order to show correct data must be
# decraled where their execution takes place

# powersave/performance system load thresholds
powersave_load_threshold = (75 * CPUS) / 100
performance_load_threshold = (50 * CPUS) / 100

# auto-cpufreq stats file path
auto_cpufreq_stats_path = None
auto_cpufreq_stats_file = None

# track governor override
if os.getenv("PKG_MARKER") == "SNAP":
    governor_override_state = Path("/var/snap/auto-cpufreq/current/override.pickle")
else:
    governor_override_state = Path("/opt/auto-cpufreq/override.pickle")

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
    if not hasattr(get_config, "config"):
        get_config.config = configparser.ConfigParser()

        if os.path.isfile(config_file):
            get_config.config.read(config_file)
            get_config.using_cfg_file = True

    return get_config.config

def get_override():
    if os.path.isfile(governor_override_state):
        with open(governor_override_state, "rb") as store:
            return pickle.load(store)
    else:
        return "default"

def set_override(override):
    if override in ["powersave", "performance"]:
        with open(governor_override_state, "wb") as store:
            pickle.dump(override, store)
        print(f"Set governor override to {override}")
    elif override == "reset":
        if os.path.isfile(governor_override_state):
            os.remove(governor_override_state)
        print("Governor override removed")
    elif override is not None:
        print("Invalid option.\nUse force=performance, force=powersave, or force=reset")



# get distro name
try:
    dist_name = distro.id()
except PermissionError:
    # Current work-around for Pop!_OS where symlink causes permission issues
    print("[!] Warning: Cannot get distro name")
    if os.path.exists("/etc/pop-os/os-release"):
            # Check if using a Snap 
            if os.getenv("PKG_MARKER") == "SNAP":
                print("[!] Snap install on PopOS detected, you must manually run the following" 
                        " commands in another terminal:\n")            
                print("[!] Backup the /etc/os-release file:")
                print("sudo mv /etc/os-release /etc/os-release-backup\n")                
                print("[!] Create hardlink to /etc/os-release:")
                print("sudo ln /etc/pop-os/os-release /etc/os-release\n")            
                print("[!] Aborting. Restart auto-cpufreq when you created the hardlink")
                sys.exit(1)
            else:
                # This should not be the case. But better be sure.
                print("[!] Check /etc/os-release permissions and make sure it is not a symbolic link")
                print("[!] Aborting...")
                sys.exit(1)

    else:
        print("[!] Check /etc/os-release permissions and make sure it is not a symbolic link")
        print("[!] Aborting...")
        sys.exit(1)

# display running version of auto-cpufreq
def app_version():

    print("auto-cpufreq version: ", end="")

    # snap package
    if os.getenv("PKG_MARKER") == "SNAP":
        print(getoutput(r"echo \(Snap\) $SNAP_VERSION"))
    # aur package
    elif dist_name in ["arch", "manjaro", "garuda"]:
        aur_pkg_check = call("pacman -Qs auto-cpufreq > /dev/null", shell=True)
        if aur_pkg_check == 1:
            print(get_formatted_version())
        else:
            print(getoutput("pacman -Qi auto-cpufreq | grep Version"))
    else:
        # source code (auto-cpufreq-installer)
        try:
            print(get_formatted_version())
        except Exception as e:
            print(repr(e))
            pass

def check_for_update():
    # returns True if a new release is available from the GitHub repo

    # Specify the repository and package name
    # IT IS IMPORTANT TO  THAT IF THE REPOSITORY STRUCTURE IS CHANGED, THE FOLLOWING FUNCTION NEEDS TO BE UPDATED ACCORDINGLY
    # Fetch the latest release information from GitHub API
    latest_release_url = f"https://api.github.com/repos/AdnanHodzic/auto-cpufreq/releases/latest"
    try:
        response = requests.get(latest_release_url)
        if response.status_code == 200:
            latest_release = response.json()
        else:
            message = response.json().get("message")
            print("Error fetching recent release!")
            if message is not None and message.startswith("API rate limit exceeded"):
                print("GitHub Rate limit exceeded. Please try again later within 1 hour or use different network/VPN.")
            else: 
                print("Unexpected status code:", response.status_code)
            return False
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
            requests.exceptions.RequestException, requests.exceptions.HTTPError) as err:
        print("Error Connecting to server!")
        return False

    latest_version = latest_release.get("tag_name")

    if latest_version is not None:
        # Get the current version of auto-cpufreq
        # Extract version number from the output string
        output = check_output(['auto-cpufreq', '--version']).decode('utf-8')
        try:
            version_line = next((re.search(r'\d+\.\d+\.\d+', line).group() for line in output.split('\n') if line.startswith('auto-cpufreq version')), None)
        except AttributeError:
            print("Error Retrieving Current Version!")
            exit(1)
        installed_version = "v" + version_line
        #Check whether the same is installed or not
        # Compare the latest version with the installed version and perform update if necessary
        if latest_version == installed_version:
            print("auto-cpufreq is up to date")
            return False
        else:
            print(f"Updates are available,\nCurrent version: {installed_version}\nLatest version: {latest_version}")
            print("Note that your previous custom settings might be erased with the following update")
            return True
    else:
        # Handle the case where "tag_name" key doesn't exist
        print("Malformed Released data!\nReinstall manually or Open an issue on GitHub for help!")

    
    
def new_update(custom_dir):
    os.chdir(custom_dir)
    print(f"Cloning the latest release to {custom_dir}")
    run(["git", "clone", "https://github.com/AdnanHodzic/auto-cpufreq.git"])
    os.chdir("auto-cpufreq")
    print(f"package cloned to directory {custom_dir}")
    run(['./auto-cpufreq-installer'], input='i\n', encoding='utf-8')

def get_literal_version(package_name):
    try:
        package_metadata = importlib.metadata.metadata(package_name)

        package_name = package_metadata['Name']
        metadata_version = package_metadata['Version']

        numbered_version, _, git_version = metadata_version.partition("+")

        # Construct the literal version string
        literal_version = f"{numbered_version}+{git_version}"

        return literal_version

    except importlib.metadata.PackageNotFoundError:
        return f"Package '{package_name}' not found"

# return formatted version for a better readability
def get_formatted_version():
    literal_version = get_literal_version("auto-cpufreq")
    splitted_version = literal_version.split("+")
    formatted_version = splitted_version[0]
    
    if len(splitted_version) > 1:
        formatted_version += " (git: " + splitted_version[1] + ")"

    return formatted_version

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
    # sort it so AC is 'always' first
    power_supplies = sorted(power_supplies)

    # check if we found power supplies. on a desktop these are not found
    # and we assume we are on a powercable.
    if len(power_supplies) == 0:
        # nothing found found, so nothing to check
        return True
    # we found some power supplies, lets check their state
    else:
        for supply in power_supplies:
            # Check if supply is in ignore list
            ignore_supply = any(item in supply for item in POWER_SUPPLY_IGNORELIST)
            # If found in ignore list, skip it.
            if ignore_supply:
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
        if not os.path.isfile("/usr/local/bin/cpufreqctl.auto-cpufreq"):
            shutil.copy(SCRIPTS_DIR / "cpufreqctl.sh", "/usr/local/bin/cpufreqctl.auto-cpufreq")


def cpufreqctl_restore():
    """
    remove cpufreqctl.auto-cpufreq script
    """
    # detect if running on a SNAP
    if os.getenv("PKG_MARKER") == "SNAP":
        pass
    else:
        if os.path.isfile("/usr/local/bin/cpufreqctl.auto-cpufreq"):
            os.remove("/usr/local/bin/cpufreqctl.auto-cpufreq")


def footer(l=79):
    print("\n" + "-" * l + "\n")


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
    shutil.copy(SCRIPTS_DIR / "auto-cpufreq-install.sh", "/usr/local/bin/auto-cpufreq-install")

    print("\n* Deploy auto-cpufreq remove script")
    shutil.copy(SCRIPTS_DIR / "auto-cpufreq-remove.sh", "/usr/local/bin/auto-cpufreq-remove")

    # output warning if gnome power profile is running
    gnome_power_detect_install()
    gnome_power_svc_disable()

    # output warning if TLP service is detected
    tlp_service_detect()

    call("/usr/local/bin/auto-cpufreq-install", shell=True)


def deploy_daemon_performance():
    print("\n" + "-" * 21 + " Deploying auto-cpufreq as a daemon (performance) " + "-" * 22 + "\n")

    # check that performance is in scaling_available_governors
    with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors") as available_governors:
        if "performance" not in available_governors.read():
            print("\"performance\" governor is unavailable on this system, run:\n"
                    "sudo sudo auto-cpufreq --install\n\n"
                    "to install auto-cpufreq using default \"balanced\" governor.\n")

    # deploy cpufreqctl script func call
    cpufreqctl()

    # turn off bluetooth on boot
    bluetooth_disable()

    auto_cpufreq_stats_path.touch(exist_ok=True)

    print("\n* Deploy auto-cpufreq install script")
    shutil.copy(SCRIPTS_DIR / "auto-cpufreq-install.sh", "/usr/local/bin/auto-cpufreq-install")

    print("\n* Deploy auto-cpufreq remove script")
    shutil.copy(SCRIPTS_DIR / "auto-cpufreq-remove.sh", "/usr/local/bin/auto-cpufreq-remove")

    # output warning if gnome power profile is running
    gnome_power_detect_install()
    #"gnome_power_svc_disable_performance" is not defined
    #gnome_power_svc_disable_performance()

    # output warning if TLP service is detected
    tlp_service_detect()

    call("/usr/local/bin/auto-cpufreq-install", shell=True)


# remove auto-cpufreq daemon
def remove_daemon():

    # check if auto-cpufreq is installed
    if not os.path.exists("/usr/local/bin/auto-cpufreq-remove"):
        print("\nauto-cpufreq daemon is not installed.\n")
        sys.exit(1)

    print("\n" + "-" * 21 + " Removing auto-cpufreq daemon " + "-" * 22 + "\n")

    # turn on bluetooth on boot
    bluetooth_enable()

    # output warning if gnome power profile is stopped
    gnome_power_rm_reminder()
    gnome_power_svc_enable()

    # run auto-cpufreq daemon remove script
    call("/usr/local/bin/auto-cpufreq-remove", shell=True)

    # remove auto-cpufreq-remove
    os.remove("/usr/local/bin/auto-cpufreq-remove")

    # delete override pickle if it exists
    if os.path.exists(governor_override_state):
        os.remove(governor_override_state)

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

    print("\t\t\"auto-cpufreq\" is about to refresh ", end = "")
    
    # empty log file if size is larger then 10mb
    if auto_cpufreq_stats_file is not None:
        log_size = os.path.getsize(auto_cpufreq_stats_path)
        if log_size >= 1e+7:
            auto_cpufreq_stats_file.seek(0)
            auto_cpufreq_stats_file.truncate(0)

    # auto-refresh counter
    for remaining in range(s, -1, -1):

        if remaining <= 3 and remaining >= 0:
            print(".", end="", flush=True)
        time.sleep(0.75)

    now = datetime.now()
    current_time = now.strftime("%B %d (%A) - %H:%M:%S")
    print("\n\t\tExecuted on:", current_time)


# get cpu usage + system load for (last minute)
def display_load():

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load: {:.2f}".format(load1m))
    print("Average temp. of all cores: {:.2f} °C \n".format(avg_all_core_temp))

# get system load average 1m, 5m, 15m (equivalent to uptime)
def display_system_load_avg():

    load1m, load5m, load15m = os.getloadavg()

    print(f" (load average: {load1m:.2f}, {load5m:.2f}, {load15m:.2f})")

# set minimum and maximum CPU frequencies
def set_frequencies():
    """
    Sets frequencies:
     - if option is used in auto-cpufreq.conf: use configured value
     - if option is disabled/no conf file used: set default frequencies
    Frequency setting is performed only once on power supply change
    """
    power_supply = "charger" if charging() else "battery"

    # don't do anything if the power supply hasn't changed
    if (
        hasattr(set_frequencies, "prev_power_supply")
        and power_supply == set_frequencies.prev_power_supply
    ):
        return
    else:
        set_frequencies.prev_power_supply = power_supply

    frequency = {
        "scaling_max_freq": {
            "cmdargs": "--frequency-max",
            "minmax": "maximum",
        },
        "scaling_min_freq": {
            "cmdargs": "--frequency-min",
            "minmax": "minimum",
        },
    }
    if not hasattr(set_frequencies, "max_limit"):
        set_frequencies.max_limit = int(getoutput(f"cpufreqctl.auto-cpufreq --frequency-max-limit"))
    if not hasattr(set_frequencies, "min_limit"):
        set_frequencies.min_limit = int(getoutput(f"cpufreqctl.auto-cpufreq --frequency-min-limit"))

    conf = get_config()

    for freq_type in frequency.keys():
        value = None
        if not conf.has_option(power_supply, freq_type):
            # fetch and use default frequencies
            if freq_type == "scaling_max_freq":
                curr_freq = int(getoutput(f"cpufreqctl.auto-cpufreq --frequency-max"))
                value = set_frequencies.max_limit
            else:
                curr_freq = int(getoutput(f"cpufreqctl.auto-cpufreq --frequency-min"))
                value = set_frequencies.min_limit
            if curr_freq == value:
                continue

        try:
            frequency[freq_type]["value"] = (
                value if value else int(conf[power_supply][freq_type].strip())
            )
        except ValueError:
            print(f"Invalid value for '{freq_type}': {frequency[freq_type]['value']}")
            exit(1)

        if not (
            set_frequencies.min_limit <= frequency[freq_type]["value"] <= set_frequencies.max_limit
        ):
            print(
                f"Given value for '{freq_type}' is not within the allowed frequencies {set_frequencies.min_limit}-{set_frequencies.max_limit} kHz"
            )
            exit(1)

        args = f"{frequency[freq_type]['cmdargs']} --set={frequency[freq_type]['value']}"
        message = f'Setting {frequency[freq_type]["minmax"]} CPU frequency to {round(frequency[freq_type]["value"]/1000)} Mhz'

        # set the frequency
        print(message)
        run(f"cpufreqctl.auto-cpufreq {args}", shell=True)


# set powersave and enable turbo
def set_powersave():
    conf = get_config()
    if conf.has_option("battery", "governor"):
        gov = conf["battery"]["governor"]
    else:
        gov = get_avail_powersave()
    print(f'Setting to use: "{gov}" governor')
    if get_override() != "default":
        print("Warning: governor overwritten using `--force` flag.")
    run(f"cpufreqctl.auto-cpufreq --governor --set={gov}", shell=True)


    if Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference").exists() is False:
        print('Not setting EPP (not supported by system)')
    else:
        dynboost_enabled = Path("/sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost").exists()

        if dynboost_enabled:
            dynboost_enabled = bool(int(
                os.popen("cat /sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost").read()
            ))

        if dynboost_enabled:
            print('Not setting EPP (dynamic boosting is enabled)')
        else:
            if conf.has_option("battery", "energy_performance_preference"):
                epp = conf["battery"]["energy_performance_preference"]
                run(f"cpufreqctl.auto-cpufreq --epp --set={epp}", shell=True)
                print(f'Setting to use: "{epp}" EPP')
            else:
                run("cpufreqctl.auto-cpufreq --epp --set=balance_power", shell=True)
                print('Setting to use: "balance_power" EPP')

    # set frequencies
    set_frequencies()

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load: {:.2f}".format(load1m))
    print("Average temp. of all cores: {:.2f} °C \n".format(avg_all_core_temp))

    # conditions for setting turbo in powersave
    if conf.has_option("battery", "turbo"):
        auto = conf["battery"]["turbo"]
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
            print("High CPU load", end=""), display_system_load_avg()

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
            print("High system load", end=""), display_system_load_avg()

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
            print("Load optimal", end=""), display_system_load_avg()

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
    print("Total system load: {:.2f}".format(load1m))
    print("Average temp. of all cores: {:.2f} °C \n".format(avg_all_core_temp))

    if psutil.cpu_percent(percpu=False, interval=0.01) >= 30.0 or isclose(
        max(psutil.cpu_percent(percpu=True, interval=0.01)), 100
    ):
        print("High CPU load", end=""), display_system_load_avg()

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
        print("High system load", end=""), display_system_load_avg()

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
        print("Load optimal", end=""), display_system_load_avg()

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
    conf = get_config()
    if conf.has_option("charger", "governor"):
        gov = conf["charger"]["governor"]
    else:
        gov = get_avail_performance()

    print(f'Setting to use: "{gov}" governor')
    if get_override() != "default":
        print("Warning: governor overwritten using `--force` flag.")
    run(
        f"cpufreqctl.auto-cpufreq --governor --set={gov}",
        shell=True,
    )


    if Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference").exists() is False:
        print('Not setting EPP (not supported by system)')
    else:
        dynboost_enabled = Path("/sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost").exists()

        if dynboost_enabled:
            dynboost_enabled = bool(int(
                os.popen("cat /sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost").read()
            ))

        if dynboost_enabled:
            print('Not setting EPP (dynamic boosting is enabled)')
        else:
            if conf.has_option("charger", "energy_performance_preference"):
                epp = conf["charger"]["energy_performance_preference"]
                run(f"cpufreqctl.auto-cpufreq --epp --set={epp}", shell=True)
                print(f'Setting to use: "{epp}" EPP')
            else:
                run("cpufreqctl.auto-cpufreq --epp --set=balance_performance", shell=True)
                print('Setting to use: "balance_performance" EPP')

    # set frequencies
    set_frequencies()

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load: {:.2f}".format(load1m))
    print("Average temp. of all cores: {:.2f} °C \n".format(avg_all_core_temp))

    if conf.has_option("charger", "turbo"):
        auto = conf["charger"]["turbo"]
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
        if (
            psutil.cpu_percent(percpu=False, interval=0.01) >= 20.0
            or max(psutil.cpu_percent(percpu=True, interval=0.01)) >= 75
        ):
            print("High CPU load", end=""), display_system_load_avg()

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
            print("High system load", end=""), display_system_load_avg()

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
            print("Load optimal", end=""), display_system_load_avg()

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
    print("Total system load: {:.2f}".format(load1m))
    print("Average temp. of all cores: {:.2f} °C \n".format(avg_all_core_temp))

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    if (
        psutil.cpu_percent(percpu=False, interval=0.01) >= 20.0
        or max(psutil.cpu_percent(percpu=True, interval=0.01)) >= 75
    ):
        print("High CPU load", end=""), display_system_load_avg()

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
        print("High system load", end=""), display_system_load_avg()

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
        print("Load optimal", end=""), display_system_load_avg()

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
    override = get_override()
    if override == "powersave":
        set_powersave()
    elif override == "performance":
        set_performance()
    elif charging():
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
    print("distro package:", distro.__version__)


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
    model_name = getoutput("grep -E 'model name' /proc/cpuinfo -m 1").split(":")[-1]
    print(f"Processor:{model_name}")

    # get core count
    total_cpu_count = int(getoutput("nproc"))
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

    # max and min freqs, psutil reports wrong max/min freqs with offline cores with percpu=False
    max_freq = max([freq.max for freq in minmax_freq_per_cpu])
    min_freq = min([freq.min for freq in minmax_freq_per_cpu])
    print("\n" + "-" * 30 + " Current CPU stats " + "-" * 30 + "\n")
    print(f"CPU max frequency: {max_freq:.0f} MHz")
    print(f"CPU min frequency: {min_freq:.0f} MHz\n")

    # get coreid's and frequencies of online cpus by parsing /proc/cpuinfo
    coreid_info = getoutput("grep -E 'processor|cpu MHz|core id' /proc/cpuinfo").split("\n")
    cpu_core = dict()
    freq_per_cpu = []
    for i in range(0, len(coreid_info), 3):
        # ensure that indices are within the valid range, before accessing the corresponding elements
        if i + 1 < len(coreid_info):
            freq_per_cpu.append(float(coreid_info[i + 1].split(":")[-1]))
        else:
            # handle the case where the index is out of range
            continue
        # ensure that indices are within the valid range, before accessing the corresponding elements
        cpu = int(coreid_info[i].split(":")[-1])
        if i + 2 < len(coreid_info):
            core = int(coreid_info[i + 2].split(":")[-1])
            cpu_core[cpu] = core
        else:
            # handle the case where the index is out of range
            continue

    online_cpu_count = len(cpu_core)
    offline_cpus = [str(cpu) for cpu in range(total_cpu_count) if cpu not in cpu_core]

    # temperatures
    temp_sensors = psutil.sensors_temperatures()
    temp_per_cpu = [float("nan")] * online_cpu_count
    try:
        # the priority for CPU temp is as follows: coretemp sensor -> sensor with CPU in the label -> acpi -> k10temp
        if "coretemp" in temp_sensors:
            # list labels in 'coretemp'
            core_temp_labels = [temp.label for temp in temp_sensors["coretemp"]]
            for i, cpu in enumerate(cpu_core):
                # get correct index in temp_sensors
                core = cpu_core[cpu]
                cpu_temp_index = core_temp_labels.index(f"Core {core}")
                temp_per_cpu[i] = temp_sensors["coretemp"][cpu_temp_index].current
        else:
            # iterate over all sensors
            for sensor in temp_sensors:
                # iterate over all temperatures in the current sensor
                for temp in temp_sensors[sensor]:
                    if 'CPU' in temp.label:
                        if temp.current != 0:
                            temp_per_cpu = [temp.current] * online_cpu_count
                            break
                else:
                    continue
                break
            else:
                for sensor in ["acpitz", "k10temp", "zenpower"]:
                    if sensor in temp_sensors:
                        if temp_sensors[sensor][0].current != 0:
                            temp_per_cpu = [temp_sensors[sensor][0].current] * online_cpu_count
                            break;
    except Exception as e:
        print(repr(e))
        pass

    print("Core\tUsage\tTemperature\tFrequency")
    for (cpu, usage, freq, temp) in zip(cpu_core, usage_per_cpu, freq_per_cpu, temp_per_cpu):
        print(f"CPU{cpu}    {usage:>5.1f}%       {temp:>3.0f} °C     {freq:>5.0f} MHz")

    if offline_cpus:
        print(f"\nDisabled CPUs: {','.join(offline_cpus)}")

    # get average temperature of all cores
    avg_cores_temp = sum(temp_per_cpu)
    global avg_all_core_temp
    avg_all_core_temp = float(avg_cores_temp / online_cpu_count)

    # print current fan speed
    current_fans = list(psutil.sensors_fans())
    for current_fan in current_fans:
        print("\nCPU fan speed:", psutil.sensors_fans()[current_fan][0].current, "RPM")



# read stats func
def read_stats():
    # read stats
    if os.path.isfile(auto_cpufreq_stats_path):
        call(["tail", "-n 50", "-f", str(auto_cpufreq_stats_path)], stderr=DEVNULL)
    footer()


# check if program (argument) is running
def is_running(program, argument):
    # iterate over all processes found by psutil
    # and find the one with name and args passed to the function
    for p in psutil.process_iter():
        try:
            cmd = p.cmdline();
        except:
            continue
        for s in filter(lambda x: program in x, cmd):
            if argument in cmd:
                return True


def daemon_running_msg():
    print("\n" + "-" * 24 + " auto-cpufreq running " + "-" * 30 + "\n")
    print(
        "ERROR: auto-cpufreq is running in daemon mode.\n\nMake sure to stop the daemon before running with --live or --monitor mode"
    )
    footer()

def daemon_not_running_msg():
    print("\n" + "-" * 24 + " auto-cpufreq not running " + "-" * 30 + "\n")
    print(
        "ERROR: auto-cpufreq is not running in daemon mode.\n\nMake sure to run \"sudo auto-cpufreq --install\" first"
    )
    footer()

# check if auto-cpufreq --daemon is running
def running_daemon_check():
    if is_running("auto-cpufreq", "--daemon"):
        daemon_running_msg()
        exit(1)
    elif os.getenv("PKG_MARKER") == "SNAP" and dcheck == "enabled":
        daemon_running_msg()
        exit(1)

# check if auto-cpufreq --daemon is not running
def not_running_daemon_check():
    if not is_running("auto-cpufreq", "--daemon"):
        daemon_not_running_msg()
        exit(1)
    elif os.getenv("PKG_MARKER") == "SNAP" and dcheck == "disabled":
        daemon_not_running_msg()
        exit(1)

