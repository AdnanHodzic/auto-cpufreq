#!/usr/bin/env python3
#
# auto-cpufreq - core functionality

import os
import platform as pl
import shutil
import subprocess as s
import sys
import time
from pathlib import Path

import power as pw
import psutil as p

# ToDo:
# - re-enable CPU fan speed display and make more generic and not only for thinkpad
# - replace get system/CPU load from: psutil.getloadavg() | available in 5.6.2)

SCRIPTS_DIR = Path("/usr/local/share/auto-cpufreq/scripts/")

# from the highest performance to the lowest
ALL_GOVERNORS = ("performance", "ondemand", "conservative", "schedutil", "userspace", "powersave")
CPUS = os.cpu_count()


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
        print("Error: cpu boost is not available")
        return None

    if value is not None:
        value = value and inverse
        f.write_text(str(int(value)) + "\n")

    value = bool(int(f.read_text().strip())) and inverse

    return value


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
    return s.getoutput("cpufreqctl --governor").strip().split(" ")[0]


def get_bat_state():
    return pw.PowerManagement().get_providing_power_source_type()


# auto-cpufreq log file
auto_cpufreq_log_file = Path("/var/log/auto-cpufreq.log")
auto_cpufreq_log_file_snap = Path("/var/snap/auto-cpufreq/current/auto-cpufreq.log")

# daemon check
dcheck = s.getoutput("snapctl get daemon")


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

    s.call("/usr/bin/auto-cpufreq-install", shell=True)


# remove auto-cpufreq daemon
def remove():
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
    s.call("/usr/bin/auto-cpufreq-remove", shell=True)

    # remove auto-cpufreq-remove
    os.remove("/usr/bin/auto-cpufreq-remove")

    # delete log file
    auto_cpufreq_log_file.unlink(missing_ok=True)

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


# set powersave and enable turbo
def set_powersave():
    print(f"Setting to use: \"{get_avail_powersave()}\" governor")
    s.run(f"cpufreqctl --governor --set={get_avail_powersave()}", shell=True)
    if Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference").exists():
        s.run("cpufreqctl --epp --set=balance_power", shell=True)
        print("Setting to use: \"balance_power\" EPP")

        # get system/CPU load
    load1m, _, _ = os.getloadavg()
    # get CPU utilization as a percentage
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    # conditions for setting turbo in powersave
    if load1m > CPUS / 7:
        print("High load, setting turbo boost: on")
        turbo(True)
    elif cpuload > 25:
        print("High CPU load, setting turbo boost: on")
        turbo(True)
    else:
        print("Load optimal, setting turbo boost: off")
        turbo(False)

    footer()


# make turbo suggestions in powersave
def mon_powersave():
    # get system/CPU load
    load1m, _, _ = os.getloadavg()
    # get CPU utilization as a percentage
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    if load1m > CPUS / 7:
        print("High load, suggesting to set turbo boost: on")
        if turbo():
            print("Currently turbo boost is: on")
        else:
            print("Currently turbo boost is: off")
        footer()

    elif cpuload > 25:
        print("High CPU load, suggesting to set turbo boost: on")
        if turbo():
            print("Currently turbo boost is: on")
        else:
            print("Currently turbo boost is: off")
        footer()
    else:
        print("Load optimal, suggesting to set turbo boost: off")
        if turbo():
            print("Currently turbo boost is: on")
        else:
            print("Currently turbo boost is: off")
        footer()


# set performance and enable turbo
def set_performance():
    print(f"Setting to use: \"{get_avail_performance()}\" governor")
    s.run(f"cpufreqctl --governor --set={get_avail_performance()}", shell=True)
    if os.path.exists("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"):
        s.run("cpufreqctl --epp --set=balance_performance", shell=True)
        print("Setting to use: \"balance_performance\" EPP")

    load1m, _, _ = os.getloadavg()
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    if load1m >= CPUS / 5:
        print("High load, setting turbo boost: on")
        turbo("0")
    elif cpuload > 20:
        print("High CPU load, setting turbo boost: on")
        turbo("0")
    else:
        print("Load optimal, setting turbo boost: off")
        turbo("1")

    footer()


# make turbo suggestions in performance
def mon_performance():
    # get system/CPU load
    load1m, _, _ = os.getloadavg()
    # get CPU utilization as a percentage
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    if turbo() == "0":
        print("Currently turbo boost is: on")
        print("Suggesting to set turbo boost: on")
    else:
        print("Currently turbo boost is: off")
        print("Suggesting to set turbo boost: on")

    footer()


# set cpufreq based if device is charging
def set_autofreq():
    print("\n" + "-" * 28 + " CPU frequency scaling " + "-" * 28 + "\n")

    # get battery state
    bat_state = pw.PowerManagement().get_providing_power_source_type()

    # determine which governor should be used
    if bat_state == pw.POWER_TYPE_AC:
        print("Battery is: charging")
        set_performance()
    elif bat_state == pw.POWER_TYPE_BATTERY:
        print("Battery is: discharging")
        set_powersave()
    else:
        print("Couldn't determine the battery status. Please report this issue.")


# make cpufreq suggestions
def mon_autofreq():
    print("\n" + "-" * 28 + " CPU frequency scaling " + "-" * 28 + "\n")

    # get battery state
    bat_state = pw.PowerManagement().get_providing_power_source_type()

    # determine which governor should be used
    if bat_state == pw.POWER_TYPE_AC:
        print("Battery is: charging")
        print(f"Suggesting use of \"{get_avail_performance()}\" governor\nCurrently using:", get_current_gov())
        mon_performance()
    elif bat_state == pw.POWER_TYPE_BATTERY:
        print("Battery is: discharging")
        print(f"Suggesting use of \"{get_avail_powersave()}\" governor\nCurrently using:", get_current_gov())
        mon_powersave()
    else:
        print("Couldn't determine the battery status. Please report this issue.")


# get system information
def sysinfo():
    # added as a temp fix for issue: https://github.com/giampaolo/psutil/issues/1650
    import warnings
    warnings.filterwarnings("ignore")

    print("\n" + "-" * 29 + " System information " + "-" * 30 + "\n")

    import distro

    dist = "UNKNOWN"
    # get distro information in snap env.
    if os.getenv("PKG_MARKER") == "SNAP":
        searchfile = open("/var/lib/snapd/hostfs/etc/os-release", "r")
        version = ""
        for line in searchfile:
            if line.startswith('NAME='):
                distro = line[5:line.find('$')].strip("\"")
                continue
            elif line.startswith('VERSION='):
                version = line[8:line.find('$')].strip("\"")
                continue

            dist = f"{distro} {version}"
        searchfile.close()
    else:
        # get distro information
        fdist = distro.linux_distribution()
        dist = " ".join(x for x in fdist)

    print("Linux distro: " + dist)
    print("Linux kernel: " + pl.release())

    # driver check
    driver = s.getoutput("cpufreqctl --driver")
    print("Driver: " + driver)

    cpu_arch = pl.machine()
    cpu_count = p.cpu_count()

    print("Architecture:", cpu_arch)

    # get processor
    with open("/proc/cpuinfo", "r")  as f:
        line = f.readline()
        while line:
            if "model name" in line:
                print("Processor:" + line.split(':')[1].rstrip())
                break
            line = f.readline()

    print("Cores:", cpu_count)

    print("\n" + "-" * 30 + " Current CPU states " + "-" * 30 + "\n")
    print(f"CPU max frequency: {p.cpu_freq().max:.0f}MHz")
    print(f"CPU min frequency: {p.cpu_freq().min:.0f}MHz")

    core_usage = p.cpu_freq(percpu=True)

    print("CPU frequency for each core:\n")
    core_num = 0
    while core_num < cpu_count:
        print(f"CPU{core_num}: {core_usage[core_num].current:.0f} MHz")
        core_num += 1

    # get number of core temp sensors
    core_temp_num = p.cpu_count(logical=False)
    # get hardware temperatures
    core_temp = p.sensors_temperatures()

    print("\nTemperature for each physical core:\n")
    core_num = 0
    while core_num < core_temp_num:
        if "coretemp" in core_temp:
            temp = core_temp['coretemp'][core_num].current
        else:
            temp = core_temp['acpitz'][0].current

        print(f"CPU{core_num} temp: {temp:.0f}°C")
        core_num += 1

    # print current fan speed | temporarily commented
    # current_fans = p.sensors_fans()['thinkpad'][0].current
    # print("\nCPU fan speed:", current_fans, "RPM")


# read log func
def read_log():
    if os.getenv("PKG_MARKER") == "SNAP":
        s.call(["tail", "-n 50", "-f", str(auto_cpufreq_log_file_snap)])
    elif os.path.isfile(auto_cpufreq_log_file):
        s.call(["tail", "-n 50", "-f", str(auto_cpufreq_log_file)])
    else:
        print("\n" + "-" * 30 + " auto-cpufreq log " + "-" * 31 + "\n")
        print("ERROR: auto-cpufreq log is missing.\n\nMake sure to run: \"auto-cpufreq --install\" first")
    footer()


# check if program (argument) is running
def is_running(program, argument):
    # iterate over all process id's found by psutil
    for pid in p.pids():
        try:
            # requests the process information corresponding to each process id
            proc = p.Process(pid)
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
