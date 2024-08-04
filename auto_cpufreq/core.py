#!/usr/bin/env python3
#
# auto-cpufreq - core functionality
import click, distro, os, platform, psutil, sys
from importlib.metadata import metadata, PackageNotFoundError
from math import isclose
from pathlib import Path
from pickle import dump, load
from re import search
from requests import get, exceptions
from shutil import copy
from subprocess import call, check_output, DEVNULL, getoutput, run
from time import sleep
from warnings import filterwarnings

from auto_cpufreq.config.config import config
from auto_cpufreq.globals import (
    ALL_GOVERNORS, AVAILABLE_GOVERNORS, AVAILABLE_GOVERNORS_SORTED, GITHUB, IS_INSTALLED_WITH_AUR, IS_INSTALLED_WITH_SNAP, POWER_SUPPLY_DIR
)
from auto_cpufreq.power_helper import *

filterwarnings("ignore")

# add path to auto-cpufreq executables for GUI
if "PATH" in os.environ:
    os.environ["PATH"] += os.pathsep + "/usr/local/bin"
else:
    os.environ["PATH"] = "/usr/local/bin"

# ToDo:
# - replace get system/CPU load from: psutil.getloadavg() | available in 5.6.2)

SCRIPTS_DIR = Path("/usr/local/share/auto-cpufreq/scripts/")
CPUS = os.cpu_count()



# Note:
# "load1m" & "cpuload" can't be global vars and to in order to show correct data must be
# decraled where their execution takes place

# powersave/performance system load thresholds
performance_load_threshold = (50 * CPUS) / 100
powersave_load_threshold = (75 * CPUS) / 100

# auto-cpufreq stats file path
auto_cpufreq_stats_file = None
auto_cpufreq_stats_path = None

# track governor override
if IS_INSTALLED_WITH_SNAP:
    auto_cpufreq_stats_path = Path("/var/snap/auto-cpufreq/current/auto-cpufreq.stats")
    governor_override_state = Path("/var/snap/auto-cpufreq/current/override.pickle")
else:
    auto_cpufreq_stats_path = Path("/var/run/auto-cpufreq.stats")
    governor_override_state = Path("/opt/auto-cpufreq/override.pickle")

# daemon check
dcheck = getoutput("snapctl get daemon")

def file_stats():
    global auto_cpufreq_stats_file
    auto_cpufreq_stats_file = open(auto_cpufreq_stats_path, "w")
    sys.stdout = auto_cpufreq_stats_file

def get_override():
    if os.path.isfile(governor_override_state):
        with open(governor_override_state, "rb") as store: return load(store)
    else: return "default"

def set_override(override):
    if override in ["powersave", "performance"]:
        with open(governor_override_state, "wb") as store:
            dump(override, store)
        print(f"Set governor override to {override}")
    elif override == "reset":
        if os.path.isfile(governor_override_state):
            os.remove(governor_override_state)
        print("Governor override removed")
    elif override is not None: print("Invalid option.\nUse force=performance, force=powersave, or force=reset")

# get distro name
try: dist_name = distro.id()
except PermissionError:
    # Current work-around for Pop!_OS where symlink causes permission issues
    print("[!] Warning: Cannot get distro name")
    if IS_INSTALLED_WITH_SNAP and os.path.exists("/etc/pop-os/os-release"):
        print("[!] Snap install on PopOS detected, you must manually run the following"
                " commands in another terminal:\n")
        print("[!] Backup the /etc/os-release file:")
        print("sudo mv /etc/os-release /etc/os-release-backup\n")
        print("[!] Create hardlink to /etc/os-release:")
        print("sudo ln /etc/pop-os/os-release /etc/os-release\n")
        print("[!] Aborting. Restart auto-cpufreq when you created the hardlink")
    else:
        print("[!] Check /etc/os-release permissions and make sure it is not a symbolic link")
        print("[!] Aborting...")
    sys.exit(1)

# display running version of auto-cpufreq
def app_version():
    print("auto-cpufreq version: ", end="")

    if IS_INSTALLED_WITH_SNAP: print(getoutput(r"echo \(Snap\) $SNAP_VERSION"))
    elif IS_INSTALLED_WITH_AUR: print(getoutput("pacman -Qi auto-cpufreq | grep Version"))
    else:
        try: print(get_formatted_version())
        except Exception as e: print(repr(e))

def check_for_update():
    # returns True if a new release is available from the GitHub repo

    # Specify the repository and package name
    # IT IS IMPORTANT TO  THAT IF THE REPOSITORY STRUCTURE IS CHANGED, THE FOLLOWING FUNCTION NEEDS TO BE UPDATED ACCORDINGLY
    # Fetch the latest release information from GitHub API
    latest_release_url = GITHUB.replace("github.com", "api.github.com/repos") + "/releases/latest"
    try:
        response = get(latest_release_url)
        if response.status_code == 200: latest_release = response.json()
        else:
            message = response.json().get("message")
            print("Error fetching recent release!")
            if message is not None and message.startswith("API rate limit exceeded"):
                print("GitHub Rate limit exceeded. Please try again later within 1 hour or use different network/VPN.")
            else: print("Unexpected status code:", response.status_code)
            return False
    except (exceptions.ConnectionError, exceptions.Timeout,
            exceptions.RequestException, exceptions.HTTPError):
        print("Error Connecting to server!")
        return False

    latest_version = latest_release.get("tag_name")

    if latest_version is not None:
        # Get the current version of auto-cpufreq
        # Extract version number from the output string
        output = check_output(['auto-cpufreq', '--version']).decode('utf-8')
        try: version_line = next((search(r'\d+\.\d+\.\d+', line).group() for line in output.split('\n') if line.startswith('auto-cpufreq version')), None)
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
    # Handle the case where "tag_name" key doesn't exist
    else: print("Malformed Released data!\nReinstall manually or Open an issue on GitHub for help!")

def new_update(custom_dir):
    os.chdir(custom_dir)
    print(f"Cloning the latest release to {custom_dir}")
    run(["git", "clone", GITHUB+".git"])
    os.chdir("auto-cpufreq")
    print(f"package cloned to directory {custom_dir}")
    run(['./auto-cpufreq-installer'], input='i\n', encoding='utf-8')

def get_literal_version(package_name):
    try:
        package_metadata = metadata(package_name)
        package_name = package_metadata['Name']
        numbered_version, _, git_version = package_metadata['Version'].partition("+")

        return f"{numbered_version}+{git_version}" # Construct the literal version string

    except PackageNotFoundError: return f"Package '{package_name}' not found"

# return formatted version for a better readability
def get_formatted_version():
    splitted_version = get_literal_version("auto-cpufreq").split("+")
    return splitted_version[0] + ("" if len(splitted_version) > 1 else " (git: " + splitted_version[1] + ")")

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
    amd_pstate = Path("/sys/devices/system/cpu/amd_pstate/status")

    if p_state.exists():
        inverse = True
        f = p_state
    elif cpufreq.exists():
        f = cpufreq
        inverse = False
    elif amd_pstate.exists():
        amd_value = amd_pstate.read_text().strip()
        if amd_value == "active":
            print("CPU turbo is controlled by amd-pstate-epp driver")
        # Basically, no other value should exist.
        return False
    else:
        print("Warning: CPU turbo is not available")
        return False

    if value is not None:
        try: f.write_text(f"{int(value ^ inverse)}\n")
        except PermissionError:
            print("Warning: Changing CPU turbo is not supported. Skipping.")
            return False

    return bool(int(f.read_text().strip())) ^ inverse

def get_turbo(): print("Currently turbo boost is:", "on" if turbo() else "off")
def set_turbo(value:bool):
    print("Setting turbo boost:", "on" if value else "off")
    turbo(value)


# ignore these devices under /sys/class/power_supply/
def get_power_supply_ignore_list():

    conf = config.get_config()

    list = []

    if conf.has_section("power_supply_ignore_list"):
        for i in conf["power_supply_ignore_list"]:
            list.append(conf["power_supply_ignore_list"][i])

    # these are hard coded power supplies that will always be ignored
    list.append("hidpp_battery")
    return list


def charging():
    """
    get charge state: is battery charging or discharging
    """
    # sort it so AC is 'always' first
    power_supplies = sorted(os.listdir(Path(POWER_SUPPLY_DIR)))
    POWER_SUPPLY_IGNORELIST = get_power_supply_ignore_list()

    # check if we found power supplies. on a desktop these are not found and we assume we are on a powercable.
    if len(power_supplies) == 0: return True # nothing found, so nothing to check

    # we found some power supplies, lets check their state
    for supply in power_supplies:
        # Check if supply is in ignore list, if found in ignore list, skip it.
        if any(item in supply for item in POWER_SUPPLY_IGNORELIST): continue

        power_supply_type_path = Path(POWER_SUPPLY_DIR + supply + "/type")
        if not power_supply_type_path.exists(): continue
        with open(power_supply_type_path) as f: supply_type = f.read()[:-1]

        if supply_type == "Mains":
            # we found an AC
            power_supply_online_path = Path(POWER_SUPPLY_DIR + supply + "/online")
            if not power_supply_online_path.exists(): continue
            with open(power_supply_online_path) as f:
                if int(f.read()[:-1]) == 1: return True # we are definitely charging
        elif supply_type == "Battery":
            # we found a battery, check if its being discharged
            power_supply_status_path = Path(POWER_SUPPLY_DIR + supply + "/status")
            if not power_supply_status_path.exists(): continue
            with open(power_supply_status_path) as f:
                # we found a discharging battery
                if str(f.read()[:-1]) == "Discharging": return False

    return True # we cannot determine discharging state, assume we are on powercable

def get_current_gov():
    return print(
        "Currently using:",
        getoutput("cpufreqctl.auto-cpufreq --governor").strip().split(" ")[0],
        "governor",
    )

def cpufreqctl():
    """
    deploy cpufreqctl.auto-cpufreq script
    """
    if not (IS_INSTALLED_WITH_SNAP or os.path.isfile("/usr/local/bin/cpufreqctl.auto-cpufreq")):
        copy(SCRIPTS_DIR / "cpufreqctl.sh", "/usr/local/bin/cpufreqctl.auto-cpufreq")

def cpufreqctl_restore():
    """
    remove cpufreqctl.auto-cpufreq script
    """
    if not IS_INSTALLED_WITH_SNAP and os.path.isfile("/usr/local/bin/cpufreqctl.auto-cpufreq"):
        os.remove("/usr/local/bin/cpufreqctl.auto-cpufreq")

def footer(l=79): print("\n" + "-" * l + "\n")

def deploy_complete_msg():
    print("\n" + "-" * 17 + " auto-cpufreq daemon installed and running " + "-" * 17 + "\n")
    print("To view live stats, run:\nauto-cpufreq --stats")
    print("\nTo disable and remove auto-cpufreq daemon, run:\nsudo auto-cpufreq --remove")
    footer()

def remove_complete_msg():
    print("\n" + "-" * 25 + " auto-cpufreq daemon removed " + "-" * 25 + "\n")
    print("auto-cpufreq successfully removed.")
    footer()

def deploy_daemon():
    print("\n" + "-" * 21 + " Deploying auto-cpufreq as a daemon " + "-" * 22 + "\n")

    cpufreqctl() # deploy cpufreqctl script func call

    bluetooth_disable() # turn off bluetooth on boot

    auto_cpufreq_stats_path.touch(exist_ok=True)

    print("\n* Deploy auto-cpufreq install script")
    copy(SCRIPTS_DIR / "auto-cpufreq-install.sh", "/usr/local/bin/auto-cpufreq-install")

    print("\n* Deploy auto-cpufreq remove script")
    copy(SCRIPTS_DIR / "auto-cpufreq-remove.sh", "/usr/local/bin/auto-cpufreq-remove")

    # output warning if gnome power profile is running
    gnome_power_detect_install()
    gnome_power_svc_disable()

    tlp_service_detect() # output warning if TLP service is detected

    call("/usr/local/bin/auto-cpufreq-install", shell=True)

def deploy_daemon_performance():
    print("\n" + "-" * 21 + " Deploying auto-cpufreq as a daemon (performance) " + "-" * 22 + "\n")

    # check that performance is in scaling_available_governors
    if "performance" not in AVAILABLE_GOVERNORS_SORTED:
        print("\"performance\" governor is unavailable on this system, run:\n"
            "sudo sudo auto-cpufreq --install\n\n"
            "to install auto-cpufreq using default \"balanced\" governor.\n")

    cpufreqctl() # deploy cpufreqctl script func call

    bluetooth_disable() # turn off bluetooth on boot

    auto_cpufreq_stats_path.touch(exist_ok=True)

    print("\n* Deploy auto-cpufreq install script")
    copy(SCRIPTS_DIR / "auto-cpufreq-install.sh", "/usr/local/bin/auto-cpufreq-install")

    print("\n* Deploy auto-cpufreq remove script")
    copy(SCRIPTS_DIR / "auto-cpufreq-remove.sh", "/usr/local/bin/auto-cpufreq-remove")

    # output warning if gnome power profile is running
    gnome_power_detect_install()
    #"gnome_power_svc_disable_performance" is not defined
    #gnome_power_svc_disable_performance()
   
    tlp_service_detect() # output warning if TLP service is detected

    call("/usr/local/bin/auto-cpufreq-install", shell=True)

def remove_daemon():
    # check if auto-cpufreq is installed
    if not os.path.exists("/usr/local/bin/auto-cpufreq-remove"):
        print("\nauto-cpufreq daemon is not installed.\n")
        sys.exit(1)

    print("\n" + "-" * 21 + " Removing auto-cpufreq daemon " + "-" * 22 + "\n")

    bluetooth_enable() # turn on bluetooth on boot

    # output warning if gnome power profile is stopped
    gnome_power_rm_reminder()
    gnome_power_svc_enable()

    # run auto-cpufreq daemon remove script
    call("/usr/local/bin/auto-cpufreq-remove", shell=True)

    # remove auto-cpufreq-remove
    os.remove("/usr/local/bin/auto-cpufreq-remove")

    # delete override pickle if it exists
    if os.path.exists(governor_override_state):  os.remove(governor_override_state)

    # delete stats file
    if auto_cpufreq_stats_path.exists():
        if auto_cpufreq_stats_file is not None: auto_cpufreq_stats_file.close()
        auto_cpufreq_stats_path.unlink()

    cpufreqctl_restore() # restore original cpufrectl script

def gov_check():
    for gov in AVAILABLE_GOVERNORS:
        if gov not in ALL_GOVERNORS:
            print("\n" + "-" * 18 + " Checking for necessary scaling governors " + "-" * 19 + "\n")
            sys.exit("ERROR:\n\nCouldn't find any of the necessary scaling governors.\n")

def root_check():
    if not os.geteuid() == 0:
        print("\n" + "-" * 33 + " Root check " + "-" * 34 + "\n")
        print("ERROR:\n\nMust be run root for this functionality to work, i.e: \nsudo " + app_name)
        footer()
        exit(1)

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
        if remaining <= 3 and remaining >= 0: print(".", end="", flush=True)
        sleep(s/3)

    print("\n\t\tExecuted on:", getoutput('date'))

# get cpu usage + system load for (last minute)
def get_load():    
    cpuload = psutil.cpu_percent(interval=1) # get CPU utilization as a percentage
    load1m, _, _ = os.getloadavg() # get system/CPU load

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load: {:.2f}".format(load1m))
    print("Average temp. of all cores: {:.2f} °C \n".format(avg_all_core_temp))

    return cpuload, load1m

def display_system_load_avg(): print(" (load average: {:.2f}, {:.2f}, {:.2f})".format(*os.getloadavg()))

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
    ): return
    else: set_frequencies.prev_power_supply = power_supply

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

    conf = config.get_config()

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
            if curr_freq == value: continue

        try: frequency[freq_type]["value"] = value if value else int(conf[power_supply][freq_type].strip())
        except ValueError:
            print(f"Invalid value for '{freq_type}': {frequency[freq_type]['value']}")
            exit(1)

        if not set_frequencies.min_limit <= frequency[freq_type]["value"] <= set_frequencies.max_limit:
            print(
                f"Given value for '{freq_type}' is not within the allowed frequencies {set_frequencies.min_limit}-{set_frequencies.max_limit} kHz"
            )
            exit(1)

        print(f'Setting {frequency[freq_type]["minmax"]} CPU frequency to {round(frequency[freq_type]["value"]/1000)} Mhz')
        # set the frequency
        run(f"cpufreqctl.auto-cpufreq {frequency[freq_type]['cmdargs']} --set={frequency[freq_type]['value']}", shell=True)

def set_platform_profile(conf, profile):
    if conf.has_option(profile, "platform_profile"):
        if not Path("/sys/firmware/acpi/platform_profile").exists():
            print('Not setting Platform Profile (not supported by system)')
        else:
            pp = conf[profile]["platform_profile"]
            print(f'Setting to use: "{pp}" Platform Profile')
            run(f"cpufreqctl.auto-cpufreq --pp --set={pp}", shell=True)

def set_powersave():
    conf = config.get_config()
    gov = conf["battery"]["governor"] if conf.has_option("battery", "governor") else AVAILABLE_GOVERNORS_SORTED[-1]
    print(f'Setting to use: "{gov}" governor')
    if get_override() != "default": print("Warning: governor overwritten using `--force` flag.")
    run(f"cpufreqctl.auto-cpufreq --governor --set={gov}", shell=True)

    if Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference").exists() is False:
        print('Not setting EPP (not supported by system)')
    else:
        dynboost_enabled = Path("/sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost").exists()

        if dynboost_enabled:
            dynboost_enabled = bool(int(
                os.popen("cat /sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost").read()
            ))

        if dynboost_enabled: print('Not setting EPP (dynamic boosting is enabled)')
        else:
            if conf.has_option("battery", "energy_performance_preference"):
                epp = conf["battery"]["energy_performance_preference"]
                run(f"cpufreqctl.auto-cpufreq --epp --set={epp}", shell=True)
                print(f'Setting to use: "{epp}" EPP')
            else:
                run("cpufreqctl.auto-cpufreq --epp --set=balance_power", shell=True)
                print('Setting to use: "balance_power" EPP')

    set_platform_profile(conf, "battery")
    set_frequencies()

    cpuload, load1m= get_load()

    auto = conf["battery"]["turbo"] if conf.has_option("battery", "turbo") else "auto"

    if auto == "always":
        print("Configuration file enforces turbo boost")
        set_turbo(True)
    elif auto == "never":
        print("Configuration file disables turbo boost")
        set_turbo(False)
    else:
        if psutil.cpu_percent(percpu=False, interval=0.01) >= 30.0 or isclose(
            max(psutil.cpu_percent(percpu=True, interval=0.01)), 100
        ): print("High CPU load", end="")
        elif load1m > powersave_load_threshold: print("High system load", end="")
        else: print("Load optimal", end="")
        display_system_load_avg()

        if cpuload >= 20: set_turbo(True) # high cpu usage trigger
        else: # set turbo state based on average of all core temperatures
            print(f"Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C")
            set_turbo(False)

    footer()

def mon_powersave():
    cpuload, load1m = get_load()

    if psutil.cpu_percent(percpu=False, interval=0.01) >= 30.0 or isclose(
        max(psutil.cpu_percent(percpu=True, interval=0.01)), 100
    ): print("High CPU load", end="")
    elif load1m > powersave_load_threshold: print("High system load", end="")
    else: print("Load optimal", end="")
    display_system_load_avg()

    if cpuload >= 20: print("suggesting to set turbo boost: on") # high cpu usage trigger
    else: # set turbo state based on average of all core temperatures
        print(f"Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C")
        print("suggesting to set turbo boost: off")
    get_turbo()

    footer()

def set_performance():
    conf = config.get_config()
    gov = conf["charger"]["governor"] if conf.has_option("charger", "governor") else AVAILABLE_GOVERNORS_SORTED[0]

    print(f'Setting to use: "{gov}" governor')
    if get_override() != "default": print("Warning: governor overwritten using `--force` flag.")
    run("cpufreqctl.auto-cpufreq --governor --set="+gov, shell=True)

    if not Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference").exists():
        print('Not setting EPP (not supported by system)')
    else:
        if Path("/sys/devices/system/cpu/intel_pstate").exists():
            dynboost_enabled = Path("/sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost").exists()

            if dynboost_enabled:
                dynboost_enabled = bool(int(
                    os.popen("cat /sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost").read()
                ))

            if dynboost_enabled: print('Not setting EPP (dynamic boosting is enabled)')
            else:
                intel_pstate_status_path = "/sys/devices/system/cpu/intel_pstate/status"

                if conf.has_option("charger", "energy_performance_preference"):
                    epp = conf["charger"]["energy_performance_preference"]

                    if Path(intel_pstate_status_path).exists() and open(intel_pstate_status_path, 'r').read().strip() == "active" and epp != "performance" and gov == "performance":
                        print(f'Warning "{epp}" EPP cannot be used in performance governor')
                        print('Overriding EPP to "performance"')
                        epp = "performance"

                    run(f"cpufreqctl.auto-cpufreq --epp --set={epp}", shell=True)
                    print(f'Setting to use: "{epp}" EPP')
                else:
                    if Path(intel_pstate_status_path).exists() and open(intel_pstate_status_path, 'r').read().strip() == "active":
                        run("cpufreqctl.auto-cpufreq --epp --set=performance", shell=True)
                        print('Setting to use: "performance" EPP')
                    else:
                        run("cpufreqctl.auto-cpufreq --epp --set=balance_performance", shell=True)
                        print('Setting to use: "balance_performance" EPP')
        elif Path("/sys/devices/system/cpu/amd_pstate").exists():
            amd_pstate_status_path = "/sys/devices/system/cpu/amd_pstate/status"

            if conf.has_option("charger", "energy_performance_preference"):
                epp = conf["charger"]["energy_performance_preference"]

                if Path(amd_pstate_status_path).exists() and open(amd_pstate_status_path, 'r').read().strip() == "active" and epp != "performance" and gov == "performance":
                    print(f'Warning "{epp} EPP cannot be used in performance governor')
                    print('Overriding EPP to "performance"')
                    epp = "performance"

                run(f"cpufreqctl.auto-cpufreq --epp --set={epp}", shell=True)
                print(f'Setting to use: "{epp}" EPP')
            else:
                if Path(amd_pstate_status_path).exists() and open(amd_pstate_status_path, 'r').read().strip() == "active":
                    run("cpufreqctl.auto-cpufreq --epp --set=performance", shell=True)
                    print('Setting to use: "performance" EPP')
                else:
                    run("cpufreqctl.auto-cpufreq --epp --set=balance_performance", shell=True)
                    print('Setting to use: "balance_performance" EPP')

    set_platform_profile(conf, "charger")
    set_frequencies()

    cpuload, load1m = get_load()
    auto = conf["charger"]["turbo"] if conf.has_option("charger", "turbo") else "auto"

    if auto == "always":
        print("Configuration file enforces turbo boost")
        set_turbo(True)
    elif auto == "never":
        print("Configuration file disables turbo boost")
        set_turbo(False)
    else:
        if (
            psutil.cpu_percent(percpu=False, interval=0.01) >= 20.0
            or max(psutil.cpu_percent(percpu=True, interval=0.01)) >= 75
        ):
            print("High CPU load", end=""), display_system_load_avg()
            if cpuload >= 20: set_turbo(True) # high cpu usage trigger
            elif avg_all_core_temp >= 70: # set turbo state based on average of all core temperatures
                print(f"Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C")
                set_turbo(False)
            else: set_turbo(True)
        elif load1m >= performance_load_threshold:
            print("High system load", end=""), display_system_load_avg()
            if cpuload >= 20: set_turbo(True) # high cpu usage trigger
            elif avg_all_core_temp >= 65: # set turbo state based on average of all core temperatures
                print(f"Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C")
                set_turbo(False)
            else: set_turbo(True)
        else:
            print("Load optimal", end=""), display_system_load_avg()
            if cpuload >= 20: set_turbo(True) # high cpu usage trigger
            else: # set turbo state based on average of all core temperatures
                print(f"Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C")
                set_turbo(False)
    footer()

def mon_performance():
    cpuload, load1m = get_load()

    if (
        psutil.cpu_percent(percpu=False, interval=0.01) >= 20.0
        or max(psutil.cpu_percent(percpu=True, interval=0.01)) >= 75
    ):
        print("High CPU load", end=""), display_system_load_avg()
        if cpuload >= 20: # high cpu usage trigger
            print("suggesting to set turbo boost: on")
            get_turbo()
        # set turbo state based on average of all core temperatures
        elif cpuload <= 25 and avg_all_core_temp >= 70:
            print(f"Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C")
            print("suggesting to set turbo boost: off")
            get_turbo()
        else:
            print("suggesting to set turbo boost: on")
            get_turbo()
    elif load1m > performance_load_threshold:
        print("High system load", end=""), display_system_load_avg()
        if cpuload >= 20: # high cpu usage trigger
            print("suggesting to set turbo boost: on")
            get_turbo()
        elif cpuload <= 25 and avg_all_core_temp >= 65: # set turbo state based on average of all core temperatures
            print(f"Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C")
            print("suggesting to set turbo boost: off")
            get_turbo()
        else:
            print("suggesting to set turbo boost: on")
            get_turbo()
    else:
        print("Load optimal", end=""), display_system_load_avg()
        if cpuload >= 20: # high cpu usage trigger
            print("suggesting to set turbo boost: on")
            get_turbo()
        elif cpuload <= 25 and avg_all_core_temp >= 60: # set turbo state based on average of all core temperatures
            print(f"Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C")
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
    if override == "powersave": set_powersave()
    elif override == "performance": set_performance()
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
        print(f'Suggesting use of "{AVAILABLE_GOVERNORS_SORTED[0]}" governor')
        mon_performance()
    else:
        print("Battery is: discharging\n")
        get_current_gov()
        print(f'Suggesting use of "{AVAILABLE_GOVERNORS_SORTED[-1]}" governor')
        mon_powersave()

def python_info():
    print("Python:", platform.python_version())
    print("psutil package:", psutil.__version__)
    print("platform package:", platform.__version__)
    print("click package:", click.__version__)
    print("distro package:", distro.__version__)

def device_info(): print("Computer type:", getoutput("dmidecode --string chassis-type"))

def distro_info():
    dist = "UNKNOWN distro"
    version = "UNKNOWN version"
    if IS_INSTALLED_WITH_SNAP:
        try:
            with open("/var/lib/snapd/hostfs/etc/os-release", "r") as searchfile:
                for line in searchfile:
                    if line.startswith("NAME="):
                        dist = line[5 : line.find("$")].strip('"')
                        continue
                    elif line.startswith("VERSION="):
                        version = line[8 : line.find("$")].strip('"')
                        continue
        except PermissionError as e: print(repr(e))
        dist = f"{dist} {version}"
    else: # get distro information
        fdist = distro.linux_distribution()
        dist = " ".join(x for x in fdist)

    print("Linux distro: " + dist)
    print("Linux kernel: " + platform.release())

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
    cpu_arch = platform.machine()
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
        if i + 1 < len(coreid_info): freq_per_cpu.append(float(coreid_info[i + 1].split(":")[-1]))
        else: continue # handle the case where the index is out of range
        # ensure that indices are within the valid range, before accessing the corresponding elements
        cpu = int(coreid_info[i].split(":")[-1])
        if i + 2 < len(coreid_info):
            core = int(coreid_info[i + 2].split(":")[-1])
            cpu_core[cpu] = core
        else: continue # handle the case where the index is out of range

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
                    if 'CPU' in temp.label and temp.current != 0:
                        temp_per_cpu = [temp.current] * online_cpu_count
                        break
                else: continue
                break
            else:
                for sensor in ["acpitz", "k10temp", "zenpower"]:
                    if sensor in temp_sensors and temp_sensors[sensor][0].current != 0:
                        temp_per_cpu = [temp_sensors[sensor][0].current] * online_cpu_count
                        break
    except Exception as e: print(repr(e))

    print("Core\tUsage\tTemperature\tFrequency")
    for (cpu, usage, freq, temp) in zip(cpu_core, usage_per_cpu, freq_per_cpu, temp_per_cpu):
        print(f"CPU{cpu}    {usage:>5.1f}%       {temp:>3.0f} °C     {freq:>5.0f} MHz")

    if offline_cpus: print(f"\nDisabled CPUs: {','.join(offline_cpus)}")

    # get average temperature of all cores
    avg_cores_temp = sum(temp_per_cpu)
    global avg_all_core_temp
    avg_all_core_temp = float(avg_cores_temp / online_cpu_count)

    # print current fan speed
    current_fans = list(psutil.sensors_fans())
    for current_fan in current_fans: print("\nCPU fan speed:", psutil.sensors_fans()[current_fan][0].current, "RPM")

def read_stats():
    if os.path.isfile(auto_cpufreq_stats_path): call(["tail", "-n 50", "-f", str(auto_cpufreq_stats_path)], stderr=DEVNULL)
    footer()

# check if program (argument) is running
def is_running(program, argument):
    # iterate over all processes found by psutil
    # and find the one with name and args passed to the function
    for p in psutil.process_iter():
        try: cmd = p.cmdline()
        except: continue
        for s in filter(lambda x: program in x, cmd):
            if argument in cmd: return True

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
    elif IS_INSTALLED_WITH_SNAP and dcheck == "enabled":
        daemon_running_msg()
        exit(1)

# check if auto-cpufreq --daemon is not running
def not_running_daemon_check():
    if not is_running("auto-cpufreq", "--daemon"):
        daemon_not_running_msg()
        exit(1)
    elif IS_INSTALLED_WITH_SNAP and dcheck == "disabled":
        daemon_not_running_msg()
        exit(1)
