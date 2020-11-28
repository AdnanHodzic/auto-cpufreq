#!/usr/bin/env python3
#
# auto-cpufreq - core functionality

import os
import platform as pl
import re
import shutil
import sys
import time
import warnings
from math import isclose
from pathlib import Path
from pprint import pformat
from subprocess import getoutput, call, run, check_output

import psutil
import distro
import click

warnings.filterwarnings("ignore")

# ToDo:
# - re-enable CPU fan speed display and make more generic and not only for thinkpad
# - replace get system/CPU load from: psutil.getloadavg() | available in 5.6.2)

SCRIPTS_DIR = Path("/usr/local/share/auto-cpufreq/scripts/")

# from the highest performance to the lowest
ALL_GOVERNORS = ("performance", "ondemand", "conservative", "schedutil", "userspace", "powersave")
CPUS = os.cpu_count()

# Note: 
# "load1m" & "cpuload" can't be global vars and to in order to show correct data must be
# decraled where their execution takes place

# powersave/performance system load thresholds
powersave_load_threshold = (75*CPUS)/100
performance_load_threshold = (50*CPUS)/100

# auto-cpufreq log file
auto_cpufreq_log_file = Path("/var/log/auto-cpufreq.log")
auto_cpufreq_log_file_snap = Path("/var/snap/auto-cpufreq/current/auto-cpufreq.log")

# daemon check
dcheck = getoutput("snapctl get daemon")

# ToDo: read version from snap/snapcraft.yaml and write to $SNAP/version for use with snap installs
# also come up with same kind of solution for AUR
def app_version():
    try:
        print("Build git commit:", check_output(["git", "describe", "--always"]).strip().decode())
    except:
        pass

def app_res_use():
    p = psutil.Process()
    print("auto-cpufreq system resource consumption:")
    print("cpu usage:", p.cpu_percent(), "%")
    print("memory use:", round(p.memory_percent(),2), "%")

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
    power_dir = "/sys/class/power_supply/"

    # AC adapter states: 0, 1, unknown
    ac_info = getoutput(f"grep . {power_dir}A*/online").splitlines()
    # if there's one ac-adapter on-line, ac_state is True
    ac_state = any(['1' in ac.split(':')[-1] for ac in ac_info])

    # Possible values: Charging, Discharging, Unknown
    battery_info = getoutput(f"grep . {power_dir}BAT*/status")

    # need to explicitly check for each state in this order
    # considering multiple batteries
    if "Discharging" in battery_info:
        battery_state = False
    elif "Charging" in battery_info:
        battery_state = True
    else:
        battery_state = None

    # if both ac-adapter and battery states are unknown default to not charging
    return ac_state or battery_state


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
    return print("Currently using:", getoutput("cpufreqctl --governor").strip().split(" ")[0], "governor")

def cpufreqctl():
    """
    deploy cpufreqctl script
    """

    # detect if running on a SNAP
    if os.getenv('PKG_MARKER') == "SNAP":
        pass
    else:
        # deploy cpufreqctl script (if missing)
        if os.path.isfile("/usr/bin/cpufreqctl"):
            shutil.copy("/usr/bin/cpufreqctl", "/usr/bin/cpufreqctl.auto-cpufreq.bak")
            shutil.copy(SCRIPTS_DIR / "cpufreqctl.sh", "/usr/bin/cpufreqctl")
        else:
            shutil.copy(SCRIPTS_DIR / "cpufreqctl.sh", "/usr/bin/cpufreqctl")


def cpufreqctl_restore():
    """
    restore original cpufreqctl script
    """
    # detect if running on a SNAP
    if os.getenv('PKG_MARKER') == "SNAP":
        pass
    else:
        # restore original cpufreqctl script
        if os.path.isfile("/usr/bin/cpufreqctl.auto-cpufreq.bak"):
            os.system("cp /usr/bin/cpufreqctl.auto-cpufreq.bak /usr/bin/cpufreqctl")
            os.remove("/usr/bin/cpufreqctl.auto-cpufreq.bak")
        # ToDo: implement mechanism to make sure cpufreqctl (auto-cpufreq) file is
        # restored if overwritten by system. But during tool removal to also remove it
        # in def cpufreqctl


def footer(l=79):
    print("\n" + "-" * l + "\n")


def daemon_not_found():
    print("\n" + "-" * 32 + " Daemon check " + "-" * 33 + "\n")
    print("ERROR:\n\nDaemon not enabled, must run install first, i.e: \nsudo auto-cpufreq --install")
    footer()


def deploy_complete_msg():
    print("\n" + "-" * 17 + " auto-cpufreq daemon installed and running " + "-" * 17 + "\n")
    print("To view live log, run:\nauto-cpufreq --log")
    print("\nTo disable and remove auto-cpufreq daemon, run:\nsudo auto-cpufreq --remove")
    footer()


def remove_complete_msg():
    print("\n" + "-" * 25 + " auto-cpufreq daemon removed " + "-" * 25 + "\n")
    print("auto-cpufreq successfully removed.")
    footer()


def deploy_daemon():
    print("\n" + "-" * 21 + " Deploying auto-cpufreq as a daemon " + "-" * 22 + "\n")

    # deploy cpufreqctl script func call
    cpufreqctl()

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
    except:
        print("\nERROR:\nWas unable to turn off bluetooth on boot")

    auto_cpufreq_log_file.touch(exist_ok=True)

    print("\n* Deploy auto-cpufreq install script")
    shutil.copy(SCRIPTS_DIR / "auto-cpufreq-install.sh", "/usr/bin/auto-cpufreq-install")

    print("\n* Deploy auto-cpufreq remove script")
    shutil.copy(SCRIPTS_DIR / "auto-cpufreq-remove.sh", "/usr/bin/auto-cpufreq-remove")

    call("/usr/bin/auto-cpufreq-install", shell=True)


# remove auto-cpufreq daemon
def remove():

    # check if auto-cpufreq is installed
    if not os.path.exists("/usr/bin/auto-cpufreq-remove"):
        print("\nauto-cpufreq daemon is not installed.\n")
        sys.exit(1)
        
    print("\n" + "-" * 21 + " Removing auto-cpufreq daemon " + "-" * 22 + "\n")

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
    except:
        print("\nERROR:\nWas unable to turn on bluetooth on boot")

    # run auto-cpufreq daemon install script
    call("/usr/bin/auto-cpufreq-remove", shell=True)

    # remove auto-cpufreq-remove
    os.remove("/usr/bin/auto-cpufreq-remove")

    # delete log file
    if auto_cpufreq_log_file.exists():
        auto_cpufreq_log_file.unlink()

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
        print("ERROR:\n\nMust be run root for this functionality to work, i.e: \nsudo auto-cpufreq")
        footer()
        exit(1)


# refresh countdown
def countdown(s):
    # Fix for wrong log output and "TERM environment variable not set"
    os.environ['TERM'] = 'xterm'

    for remaining in range(s, 0, -1):
        sys.stdout.write("\r")
        sys.stdout.write("\t\t\t\"auto-cpufreq\" refresh in:{:2d}".format(remaining))
        sys.stdout.flush()
        time.sleep(1)

# get cpu usage + system load for (last minute)
def display_load():

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

# set powersave and enable turbo
def set_powersave():
    print(f"Setting to use: \"{get_avail_powersave()}\" governor")
    run(f"cpufreqctl --governor --set={get_avail_powersave()}", shell=True)
    if Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference").exists():
        run("cpufreqctl --epp --set=balance_power", shell=True)
        print("Setting to use: \"balance_power\" EPP")

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    # conditions for setting turbo in powersave
    if psutil.cpu_percent(percpu=False, interval=0.01) >= 30.0 or isclose(max(psutil.cpu_percent(percpu=True, interval=0.01)), 100):
        print("High CPU load, setting turbo boost: on")
        turbo(True)
    elif load1m > powersave_load_threshold:
        print("High system load, setting turbo boost: on")
        turbo(True)
    else:
        print("Load optimal, setting turbo boost: off")
        turbo(False)

    footer()


# make turbo suggestions in powersave
def mon_powersave():

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    if psutil.cpu_percent(percpu=False, interval=0.01) >= 30.0 or isclose(max(psutil.cpu_percent(percpu=True, interval=0.01)), 100):
        print("High CPU load, suggesting to set turbo boost: on")
        get_turbo()
        footer()
    elif load1m > powersave_load_threshold:
        print("High system load, suggesting to set turbo boost: on")
        get_turbo()
        footer()
    else:
        print("Load optimal, suggesting to set turbo boost: off")
        get_turbo()
        footer()

# set performance and enable turbo
def set_performance():

    # access/import necessary variables from get_temp_data func
    avg_cores_temp, avg_all_core_temp=sysinfo()

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print(f"Setting to use: \"{get_avail_performance()}\" governor")
    run(f"cpufreqctl --governor --set={get_avail_performance()}", shell=True)
    if os.path.exists("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"):
        run("cpufreqctl --epp --set=balance_performance", shell=True)
        print("Setting to use: \"balance_performance\" EPP")

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m)
    print("Average temp. of all cores:", avg_all_core_temp, "°C")

    if psutil.cpu_percent(percpu=False, interval=0.01) >= 20.0 or max(psutil.cpu_percent(percpu=True, interval=0.01)) >= 75:
        print("\nHigh CPU load")

        # high cpu usage trigger
        if cpuload > 25:
            print("setting turbo boost: on")
            turbo(True)

        # set turbo state based on average of all core temperatures
        elif cpuload < 25 and avg_all_core_temp >= 70:
            print("Optimal total CPU usage:", cpuload, "%, high average core temp:", avg_all_core_temp, "°C")
            print("setting turbo boost: off")
            turbo(False)
        else:
            print("setting turbo boost: on")
            turbo(True)

    elif load1m >= performance_load_threshold:
        print("\nHigh system load")

        # high cpu usage trigger
        if cpuload > 25:
            print("setting turbo boost: on")
            turbo(True)

        # set turbo state based on average of all core temperatures
        elif cpuload < 25 and avg_all_core_temp >= 65:
            print("Optimal total CPU usage:", cpuload, "%, high average core temp:", avg_all_core_temp, "°C")
            print("setting turbo boost: off")
            turbo(False)
        else:
            print("setting turbo boost: on")
            turbo(True)

    else:
        print("\nLoad optimal")

        # high cpu usage trigger
        if cpuload > 25:
            print("setting turbo boost: on")
            turbo(True)

        # set turbo state based on average of all core temperatures
        elif cpuload < 25 and avg_all_core_temp >= 60:
            print("Optimal total CPU usage:", cpuload, "%, high average core temp:", avg_all_core_temp, "°C")
            print("setting turbo boost: off")
            turbo(False)
        else:
            print("setting turbo boost: on")
            turbo(True)

    footer()


# make turbo suggestions in performance
def mon_performance():
    
    # access/import necessary variables from get_temp_data func
    avg_cores_temp, avg_all_core_temp=sysinfo()

    # get CPU utilization as a percentage
    cpuload = psutil.cpu_percent(interval=1)

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m)
    print("Average temp. of all cores:", avg_all_core_temp, "°C")

    # get system/CPU load
    load1m, _, _ = os.getloadavg()

    if psutil.cpu_percent(percpu=False, interval=0.01) >= 20.0 or max(psutil.cpu_percent(percpu=True, interval=0.01)) >= 75:
        print("High CPU load")

        # high cpu usage trigger
        if cpuload > 25:
            print("suggesting to set turbo boost: on")
            get_turbo()

        # set turbo state based on average of all core temperatures
        elif cpuload < 25 and avg_all_core_temp >= 70:
            print("Optimal total CPU usage:", cpuload, "%, high average core temp:", avg_all_core_temp, "°C")
            print("suggesting to set turbo boost: off")
            get_turbo()
        else:
            print("suggesting to set turbo boost: on")
            get_turbo()

    elif load1m > performance_load_threshold:
        print("High system load")

        # high cpu usage trigger
        if cpuload > 25:
            print("suggesting to set turbo boost: on")
            get_turbo()

        # set turbo state based on average of all core temperatures
        elif cpuload < 25 and avg_all_core_temp >= 65:
            print("Optimal total CPU usage:", cpuload, "%, high average core temp:", avg_all_core_temp, "°C")
            print("suggesting to set turbo boost: off")
            get_turbo()
        else:
            print("suggesting to set turbo boost: on")
            get_turbo()

        footer()
    else:
        print("\nLoad optimal")

        # high cpu usage trigger
        if cpuload > 25:
            print("suggesting to set turbo boost: on")
            get_turbo()

        # set turbo state based on average of all core temperatures
        elif cpuload < 25 and avg_all_core_temp >= 60:
            print("Optimal total CPU usage:", cpuload, "%, high average core temp:", avg_all_core_temp, "°C")
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
        print(f"Suggesting use of \"{get_avail_performance()}\" governor")
        mon_performance()
    else:
        print("Battery is: discharging\n")
        get_current_gov()
        print(f"Suggesting use of \"{get_avail_powersave()}\" governor")
        mon_powersave()

def python_info():
    print("Python:", pl.python_version())
    print("psutil package:", psutil.__version__)
    print("platform package:", pl.__version__)
    print("click package:", click.__version__)
    # workaround: Module 'distro' has no '__version__' member () (https://github.com/nir0s/distro/issues/265)
    #print("distro:", distro.__version__)
    run("echo \"distro package\" $(pip3 show distro | sed -n -e 's/^.*Version: //p')", shell=True)


def distro_info():
    dist = "UNKNOWN distro"
    version = "UNKNOWN version"

    # get distro information in snap env.
    if os.getenv("PKG_MARKER") == "SNAP":
        try:
            with open("/var/lib/snapd/hostfs/etc/os-release", "r") as searchfile:
                for line in searchfile:
                    if line.startswith('NAME='):
                        dist = line[5:line.find('$')].strip("\"")
                        continue
                    elif line.startswith('VERSION='):
                        version = line[8:line.find('$')].strip("\"")
                        continue
        except PermissionError:
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
    print(f"Procesor:{model_name}")

    # get core count
    total_cpu_count = int(getoutput("nproc --all"))
    print("Cores:", total_cpu_count)

    # get architecture
    cpu_arch = pl.machine()
    print("Architecture:", cpu_arch)

    # get driver
    driver = getoutput("cpufreqctl --driver")
    print("Driver: " + driver)

    # get usage and freq info of cpus
    usage_per_cpu = psutil.cpu_percent(interval=1, percpu=True)
    # psutil current freq not used, gives wrong values with offline cpu's
    minmax_freq_per_cpu = psutil.cpu_freq(percpu=True)

    # max and min freqs, psutil reports wrong max/min freqs whith offline cores with percpu=False
    max_freq = max([freq.max for freq in minmax_freq_per_cpu])
    min_freq = min([freq.min for freq in minmax_freq_per_cpu])
    print("\n" + "-" * 30 + " Current CPU states " + "-" * 30 + "\n")
    print(f"CPU max frequency: {max_freq:.0f} MHz")
    print(f"CPU min frequency: {min_freq:.0f} MHz\n")

    # get coreid's and frequencies of online cpus by parsing /proc/cpuinfo
    coreid_info = getoutput("egrep 'processor|cpu MHz|core id' /proc/cpuinfo").split("\n")
    cpu_core = dict()
    freq_per_cpu = []
    for i in range(0, len(coreid_info), 3):
        freq_per_cpu.append(float(coreid_info[i + 1].split(':')[-1]))
        cpu = int(coreid_info[i].split(':')[-1])
        core = int(coreid_info[i + 2].split(':')[-1])
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
        elif "acpitz" in core_temp:
            temp_per_cpu = [core_temp["acpitz"][0].current] * online_cpu_count
    except:
        pass

    print("\t Usage  Temperature  Frequency")
    for (cpu, usage, freq, temp) in zip(cpu_core, usage_per_cpu, freq_per_cpu, temp_per_cpu):
        print(f"CPU{cpu}:\t{usage:>5.1f}%    {temp:>3.0f} °C    {freq:>5.0f} MHz")

    if offline_cpus:
        print(f"\nDisabled CPUs: {','.join(offline_cpus)}")

    # get average temperature of all cores
    avg_cores_temp = sum(temp_per_cpu)
    avg_all_core_temp = float(avg_cores_temp/online_cpu_count)

    # export/make these variables accessible in other functions
    return avg_cores_temp, avg_all_core_temp

    # print current fan speed | temporarily commented
    # current_fans = psutil.sensors_fans()['thinkpad'][0].current
    # print("\nCPU fan speed:", current_fans, "RPM")


def no_log_msg():
    print("\n" + "-" * 30 + " auto-cpufreq log " + "-" * 31 + "\n")
    print("ERROR: auto-cpufreq log is missing.\n\nMake sure to run: \"auto-cpufreq --install\" first")

# read log func
def read_log():

    # read log (snap)
    if os.getenv("PKG_MARKER") == "SNAP":
        if os.path.isfile(auto_cpufreq_log_file_snap):
            call(["tail", "-n 50", "-f", str(auto_cpufreq_log_file_snap)])
        else:
            no_log_msg()
    # read log (non snap)
    elif os.path.isfile(auto_cpufreq_log_file):
        call(["tail", "-n 50", "-f", str(auto_cpufreq_log_file)])
    else:
        no_log_msg()
    footer()


# check if program (argument) is running
def is_running(program, argument):
    # iterate over all process id's found by psutil
    for pid in psutil.pids():
        try:
            # requests the process information corresponding to each process id
            proc = psutil.Process(pid)
            # check if value of program-variable that was used to call the function
            # matches the name field of the plutil.Process(pid) output
            if program in proc.name():
                # check output of p.name(), output name of program
                # p.cmdline() - echo the exact command line via which p was called.
                for arg in proc.cmdline():
                    if argument in str(arg):
                        return True
        except:
            continue


# check if auto-cpufreq --daemon is running
def running_daemon():
    if is_running('auto-cpufreq', '--daemon'):
        deploy_complete_msg()
        exit(1)
    elif os.getenv("PKG_MARKER") == "SNAP" and dcheck == "enabled":
        deploy_complete_msg()
        exit(1)