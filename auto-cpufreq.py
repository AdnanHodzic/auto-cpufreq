#!/usr/bin/env python3
#
# auto-cpufreq - Automatic CPU speed & power optimizer for Linux
#
# Blog post: http://foolcontrol.org/?p=3124

import subprocess
import os
import sys
import time
import psutil
import platform
import click
import power

# ToDo:
# - re-enable CPU fan speed display and make more generic and not only for thinkpad
# - replace get system/CPU load from: psutil.getloadavg() | available in 5.6.2)

# global vars
p = psutil
pl = platform
s = subprocess
tool_run = sys.argv[0]
cpus = os.cpu_count()

# get turbo boost state
cur_turbo = s.getoutput("cat /sys/devices/system/cpu/intel_pstate/no_turbo")

# get current scaling governor
get_cur_gov = s.getoutput("cpufreqctl --governor")
gov_state = get_cur_gov.split()[0]

# get battery state
bat_state = power.PowerManagement().get_providing_power_source_type()

# auto-cpufreq log file
auto_cpufreq_log_file = "/var/log/auto-cpufreq.log"

# deploy cpufreqctl script
def cpufreqctl():
    # deploy cpufreqctl script (if missing)
    if os.path.isfile("/usr/bin/cpufreqctl"):
        pass
    else:
        os.system("cp scripts/cpufreqctl.sh /usr/bin/cpufreqctl")

def footer(l):
    print("\n" + "-" * l + "\n")

# deploy auto-cpufreq daemon
def deploy():

    print("\n" + "-" * 21 + " Deploying auto-cpufreq as a daemon " + "-" * 22 + "\n")

    # deploy cpufreqctl script func call
    cpufreqctl()

    print("* Turn off bluetooth on boot")
    btconf="/etc/bluetooth/main.conf"
    try:
        orig_set = "AutoEnable=true"
        change_set = "AutoEnable=false"
        with open(btconf, "r+") as f:
            content = f.read()
            f.seek(0)
            f.truncate()
            f.write(content.replace(orig_set, change_set))
    except:
        print("\nERROR:\nWas unable to turn off bluetooth on boot")

    print("\n* Deploy auto-cpufreq as system wide accessible binary")
    os.system("cp auto-cpufreq.py /usr/bin/auto-cpufreq")

    print("\n* Deploy auto-cpufreq install script")
    os.system("cp scripts/auto-cpufreq-install.sh /usr/bin/auto-cpufreq-install")

    print("\n* Deploy auto-cpufreq remove script")
    os.system("cp scripts/auto-cpufreq-remove.sh /usr/bin/auto-cpufreq-remove")

    # run auto-cpufreq daemon deploy script
    s.call("/usr/bin/auto-cpufreq-install", shell=True)

# remove auto-cpufreq daemon
def remove():

    print("\n" + "-" * 21 + " Removing auto-cpufreq daemon " + "-" * 22 + "\n")

    print("* Turn on bluetooth on boot")
    btconf="/etc/bluetooth/main.conf"
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

# check for necessary scaling governors
def gov_check():
    avail_gov = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"

    governors=["performance","powersave"]

    for line in open(avail_gov):
        for keyword in governors:
            if keyword in line:
                pass
            else:
                print("\n" + "-" * 18 + " Checking for necessary scaling governors " + "-" * 19 + "\n")
                sys.exit("ERROR:\n\nCouldn't find any of the necessary scaling governors.\n")

# root check func
def root_check():
    if not os.geteuid() == 0:
        print("\n" + "-" * 33 + " Root check " + "-" * 34 + "\n")
        sys.exit("ERROR:\n\nMust be run root for this functionality to work, i.e: \nsudo " + tool_run + "\n")
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
    # get system/CPU load
    load1m, _, _ = os.getloadavg()
    # get CPU utilization as a percentage
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    # conditions for setting turbo in powersave
    if load1m > cpus and load1m < cpus * 2:
        print("Setting to use: \"powersave\" governor")
        s.run("cpufreqctl --governor --set=powersave", shell=True)

        print("Medium load, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        footer(79)
    elif load1m >= cpus * 2:
        print("Setting to use: \"performance\" governor")
        s.run("cpufreqctl --governor --set=performance", shell=True)

        print("High load, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        footer(79)
    elif cpuload > 40 and cpuload <= 70:
        print("Setting to use: \"powersave\" governor")
        s.run("cpufreqctl --governor --set=powersave", shell=True)

        print("High CPU load, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        #print("\n" + "-" * 60 + "\n")
        footer(79)
    elif cpuload > 70:
        print("Setting to use: \"performance\" governor")
        s.run("cpufreqctl --governor --set=performance", shell=True)

        print("Very high CPU load, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        #print("\n" + "-" * 60 + "\n")
        footer(79)
    else:
        print("Setting to use: \"powersave\" governor")
        s.run("cpufreqctl --governor --set=powersave", shell=True)

        print("Load optimal, setting turbo boost: off")
        s.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        #print("\n" + "-" * 60 + "\n")
        footer(79)

# make turbo suggestions in powersave
def mon_powersave():
    # get system/CPU load
    load1m, _, _ = os.getloadavg()
    # get CPU utilization as a percentage
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    if load1m > 2:
        print("High load, suggesting to set turbo boost: on")
        if cur_turbo == "0":
            print("Currently turbo boost is: on")
        else:
            print("Currently turbo boost is: off")
        footer(79)
        
    elif cpuload > 25:
        print("High CPU load, suggesting to set turbo boost: on")
        if cur_turbo == "0":
            print("Currently turbo boost is: on")
        else:
            print("Currently turbo boost is: off")
        footer(79)
    else:
        print("Load optimal, suggesting to set turbo boost: off")
        if cur_turbo == "0":
            print("Currently turbo boost is: on")
        else:
            print("Currently turbo boost is: off")
        footer(79)

# set performance and enable turbo
def set_performance():
    # get system/CPU load
    load1m, _, _ = os.getloadavg()
    # get CPU utilization as a percentage
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    # conditions for setting turbo in performance for future using
    if load1m >= 0.70:
        print("Setting to use \"performance\" governor")
        s.run("cpufreqctl --governor --set=performance", shell=True)
        
        print("High load, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        footer(79)
    elif cpuload > 20:
        print("Setting to use \"performance\" governor")
        s.run("cpufreqctl --governor --set=performance", shell=True)

        print("High CPU load, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        #print("\n" + "-" * 60 + "\n")
        footer(79)
    else:
        print("Setting to use: \"powersave\" governor")
        s.run("cpufreqctl --governor --set=powersave", shell=True)

        print("Load optimal, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        #print("\n" + "-" * 60 + "\n")
        footer(79)

# make turbo suggestions in performance
def mon_performance():

    # get system/CPU load
    load1m, _, _ = os.getloadavg()
    # get CPU utilization as a percentage
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    if cur_turbo == "0":
        print("Currently turbo boost is: on")
        print("Suggesting to set turbo boost: on")
    else:
        print("Currently turbo boost is: off")
        print("Suggesting to set turbo boost: on")

    footer(79)

# set cpufreq based if device is charging
def set_autofreq():
    print("\n" + "-" * 28 + " CPU frequency scaling " + "-" * 28 + "\n")

    # get battery state
    bat_state = power.PowerManagement().get_providing_power_source_type()

    # determine which governor should be used
    if bat_state == power.POWER_TYPE_AC:
        print("Battery is: charging")
        set_performance()
    elif bat_state == power.POWER_TYPE_BATTERY:
        print("Battery is: discharging")
        set_powersave()
    else: 
        print("Couldn't determine battery status. Please report this issue.")

# make cpufreq suggestions
def mon_autofreq():
    print("\n" + "-" * 28 + " CPU frequency scaling " + "-" * 28 + "\n")

    # get battery state
    bat_state = power.PowerManagement().get_providing_power_source_type()

    # determine which governor should be used
    if bat_state == power.POWER_TYPE_AC:
        print("Battery is: charging")
        print("Suggesting use of \"performance\" governor\nCurrently using:", gov_state)
        mon_performance()
    elif bat_state == power.POWER_TYPE_BATTERY:
        print("Battery is: discharging")
        print("Suggesting use of \"powersave\" governor\nCurrently using:", gov_state)
        mon_powersave()
    else:
        print("Couldn't determine battery status. Please report this issue.")
    
# get system information
def sysinfo():
    
    # added as a temp fix for issue: https://github.com/giampaolo/psutil/issues/1650
    import warnings
    warnings.filterwarnings("ignore")

    print("\n" + "-" * 29 + " System information " + "-" * 30 + "\n")

    import distro
    # get info about linux distro
    fdist = distro.linux_distribution()
    dist = " ".join(x for x in fdist)
    print("Linux distro: " + dist)
    print("Linux kernel: " + pl.release())

    # driver check
    driver = s.getoutput("cpufreqctl --driver")
    print("Driver: " + driver)

    # get cpu architecture
    cpu_arch = pl.machine()

    # get number of cores/logical CPU's
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

    # print cpu max frequency
    max_cpu_freq = p.cpu_freq().max
    print("CPU max frequency: " + "\n{:.0f}".format(max_cpu_freq) + " MHz\n")

    # get current cpu frequency per core
    core_usage = p.cpu_freq(percpu=True)

    # print current cpu frequency per core
    print("CPU frequency for each core:\n")
    core_num = 0
    while core_num < cpu_count:
        print("CPU" + str(core_num) + ": {:.0f}".format(core_usage[core_num].current) + " MHz")
        core_num += 1

    # get number of core temp sensors
    core_temp_num = p.cpu_count(logical=False)
    # get hardware temperatures
    core_temp = p.sensors_temperatures()

    # print temperature for each physical core
    print("\nTemperature for each physical core:\n")
    core_num = 0
    while core_num < core_temp_num:
        print("CPU" + str(core_num) + " temp: {:.0f}".format(core_temp['coretemp'][core_num].current) + "°C")
        core_num += 1

    # print current fan speed | temporarily commented
    #current_fans = p.sensors_fans()['thinkpad'][0].current
    #print("\nCPU fan speed:", current_fans, "RPM")

# read log func
def read_log():
    if os.path.isfile(auto_cpufreq_log_file):
        # read /var/log/auto-cpufreq.log
        s.call(["tail", "-n 50", "-f", auto_cpufreq_log_file])
    else:
        print("\n" + "-" * 30 + " auto-cpufreq log " + "-" * 31 + "\n")
        print("ERROR: auto-cpufreq log is missing.\n\nMake sure to run: \"python3 auto-cpufreq.py --install\" first")
    footer(79)

def running_check():
    daemon_marker = False
    for proc in p.process_iter():
        try:
            pinfo = proc.as_dict(attrs=['pid', 'name', 'cmdline'])
        except p.NoSuchProcess:
            pass
        else:
            if pinfo['name'] == 'python3' and \
            '/usr/bin/auto-cpufreq' in pinfo['cmdline'] and '--daemon' in pinfo['cmdline']:
                daemon_marker = True

    if daemon_marker:
        print("\n" + "-" * 25 + " detected auto-cpufreq daemon" + "-" * 25 + "\n")
        print("ERROR: prevention from running multiple instances")
        print("\nIt seems like auto-cpufreq daemon is already running.\n")
        print("----")
        print("\nTo view live log run:\n\tauto-cpufreq --log")
        footer(79)
        sys.exit()

# cli
@click.command()
@click.option("--monitor", is_flag=True, help="Monitor and suggest CPU optimizations")
@click.option("--live", is_flag=True, help="Monitor and make suggested CPU optimizations")
@click.option("--install/--remove", default=True, help="Install/remove daemon for automatic CPU optimizations")
@click.option("--log", is_flag=True, help="View live CPU optimization log made by daemon")
@click.option("--daemon", is_flag=True, hidden=True)

def cli(monitor, live, daemon, install, log):
    # print --help by default if no argument is provided when auto-cpufreq is run
    if len(sys.argv) == 1:
        print("\n" + "-" * 22 + " auto-cpufreq " + "-" * 23 + "\n")
        print("Automatic CPU speed & power optimizer for Linux")
        print("\nExample usage:\npython3 " + tool_run + " --monitor")
        print("\n-----\n")

        s.call(["python3", "auto-cpufreq.py", "--help"])
        print("\n" +  "-" * 59 + "\n")
    else:
        if daemon:
            while True:
                root_check()
                gov_check()
                cpufreqctl()
                sysinfo()
                set_autofreq()
                countdown(5)
                subprocess.call("clear")
        elif monitor:
            while True:
                running_check()
                root_check()
                gov_check()
                cpufreqctl()
                sysinfo()
                mon_autofreq()
                countdown(5)
                subprocess.call("clear")
        elif live:
            while True:
                running_check()
                root_check()
                gov_check()
                cpufreqctl()
                sysinfo()
                set_autofreq()
                countdown(5)
                subprocess.call("clear")
        elif log:
                read_log()
        elif install:
                running_check()
                root_check()
                gov_check()
                deploy()
        elif remove:
                root_check()
                remove()

if __name__ == '__main__':
    # while True:
        cli()
