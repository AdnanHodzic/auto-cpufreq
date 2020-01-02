#!/usr/bin/env python3
# 
# ToDo: add description

import subprocess
import os
import sys
import time
import psutil
import platform
import click

# ToDo:
# - add potential throttling fix (set max frequency if load too high?)

# - fill out every TBU (cli + auto-cpufreq.service file)
# - add readme + list need to install all necessary packages

# global vars
p = psutil
pl = platform
s = subprocess
tool_run = sys.argv[0]

# get turbo boost state
cur_turbo = s.getoutput("cat /sys/devices/system/cpu/intel_pstate/no_turbo")

# get current scaling governor
get_cur_gov = s.getoutput("cpufreqctl --governor")
gov_state = get_cur_gov.split()[0]

# get battery state
bat_state = p.sensors_battery().power_plugged

# get CPU utilization as a percentage
cpuload = p.cpu_percent(interval=1)

# auto-cpufreq log file
auto_cpufreq_log_file = "/var/log/auto-cpufreq.log"

# deploy auto-cpufreq daemon
def deploy():

    print("\n" + "-" * 21 + " Deploying auto-cpufreq as a daemon " + "-" * 22 + "\n")

    # deploy cpufreqctl script (if missing)
    if os.path.isfile("/usr/bin/cpufreqctl"):
        pass
    else:
        print("* Addding missing \"cpufreqctl\" script")
        os.system("cp scripts/cpufreqctl.sh /usr/bin/cpufreqctl")

    # delete /var/log/auto-cpufreq.log if it exists (make sure file gets updated accordingly)
    if os.path.exists(auto_cpufreq_log_file):
        os.remove(auto_cpufreq_log_file)

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

    print("\n* Deploy auto-cpufreq daemon deploy script")
    os.system("cp scripts/auto-cpufreq-daemon.sh /usr/bin/auto-cpufreq-daemon")

    print("\n* Deploy auto-cpufreq daemon removal script")
    os.system("cp scripts/auto-cpufreq-remove.sh /usr/bin/auto-cpufreq-remove")

    print("\n* Deploy auto-cpufreq systemd unit file")
    os.system("cp scripts/auto-cpufreq.service /lib/systemd/system/auto-cpufreq.service")

    # run auto-cpufreq daemon deploy script
    s.call("/usr/bin/auto-cpufreq-daemon", shell=True)

    print("auto-cpufreq daemon started and will automatically start at boot time.")
    print("\nTo disable and remove auto-cpufreq daemon, run:\nautocpu-freq --remove")

    print("\nTo view live auto-cpufreq daemon logs, run:\nauto-cpufreq --log")
    footer(79)

# deploy auto-cpufreq daemon
def remove():

    print("\n" + "-" * 21 + " Removing auto-cpufreq daemon " + "-" * 22 + "\n")

    # delete /var/log/auto-cpufreq.log if it exists
    os.remove(auto_cpufreq_log_file)

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
        print("\nERROR:\nWas unable to turn off bluetooth on boot")

    print("\n* Remove auto-cpufreq daemon deploy script")
    os.remove("/usr/bin/auto-cpufreq-daemon")

    # run auto-cpufreq daemon deploy script
    s.call("/usr/bin/auto-cpufreq-remove", shell=True)

    if os.path.isfile("/usr/bin/cpufreqctl"):
        print("\n* Remove auto-cpufreq systemd unit file")
        os.remove("/lib/systemd/system/auto-cpufreq.service")

    print("\n* Remove auto-cpufreq binary")
    os.remove("/usr/bin/auto-cpufreq")

    print("\nauto-cpufreq daemon removed")

    footer(79)


def footer(l):
    print("\n" + "-" * l + "\n")

# check for necessary driver
def driver_check():
    driver = s.getoutput("cpufreqctl --driver")
    if driver != "intel_pstate":
        print("\n" + "-" * 32 + " Driver check " + "-" * 33 + "\n")
        print("ERROR:\n\n\"intel_pstate\" CPU Performance Scaling Driver is not enabled.\n")
        footer(79)
        sys.exit()

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
    for remaining in range(s, 0, -1):
        sys.stdout.write("\r")
        sys.stdout.write("\t\t\t\"auto-cpufreq\" refresh in:{:2d}".format(remaining))
        sys.stdout.flush()
        time.sleep(1)

    #sys.stdout.write("\rRefreshing ...                     \n")

# set powersave
def set_powersave():
    print("Setting to use: powersave")
    s.run("cpufreqctl --governor --set=powersave", shell=True)
    
    #print("Setting turbo boost: off")
    #s.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)

    # enable turbo boost
    set_turbo_powersave()

# set performance
def set_performance():
    print("Setting to use \"performance\" governor")
    s.run("cpufreqctl --governor --set=performance", shell=True)

    # enable turbo boost
    set_turbo()

# set turbo
def set_turbo():

    #print("\n" + "-" * 5 + "\n")

    # ToDo: duplicate + replace with psutil.getloadavg()? (available in 5.6.2)
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    if load1m > 1:
        print("High load, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        footer(79)
    elif cpuload > 20:
        print("High CPU load, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        #print("\n" + "-" * 60 + "\n")
        footer(79)
    else:
        print("Load optimal, setting turbo boost: off")
        s.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        #print("\n" + "-" * 60 + "\n")
        footer(79)

# set turbo when in powersave
def set_turbo_powersave():

    #print("\n" + "-" * 5 + "\n")

    # ToDo: duplicate + replace with psutil.getloadavg()? (available in 5.6.2)
    load1m, _, _ = os.getloadavg()

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    if load1m > 4:
        print("High load, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        footer(79)
    elif cpuload > 50:
        print("High CPU load, setting turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        #print("\n" + "-" * 60 + "\n")
        footer(79)
    else:
        print("Load optimal, setting turbo boost: off")
        s.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        #print("\n" + "-" * 60 + "\n")
        footer(79)

# make turbo suggestions
def mon_turbo():

    print("\n" + "-" * 5 + "\n")

    # ToDo: duplicate + replace with psutil.getloadavg()? (available in 5.6.2)
    load1m, _, _ = os.getloadavg()

    print("Total CPU usage:", cpuload, "%")
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

# set cpufreq
def set_autofreq():
    print("\n" + "-" * 28 + " CPU frequency scaling " + "-" * 28 + "\n")

    # get battery state
    bat_state = p.sensors_battery().power_plugged

    # determine which governor should be used
    if bat_state == True:
        print("Battery is: charging")
        set_performance()
    elif bat_state == False:
        print("Battery is: discharging")
        set_powersave()
    else:
        print("Couldn't detrmine battery status. Please report this issue.")

# make cpufreq suggestions
def mon_autofreq():
    print("\n" + "-" * 28 + " CPU frequency scaling " + "-" * 28 + "\n")

    # get battery state
    bat_state = p.sensors_battery().power_plugged

    # determine which governor should be used
    if bat_state == True:
        print("Battery is: charging")
        print("Suggesting use of \"performance\" governor\nCurrently using:", gov_state)
    elif bat_state == False:
        print("Battery is: discharging")
        print("Suggesting use of \"powersave\" governor\nCurrently using:", gov_state)
    else:
        print("Couldn't detrmine battery status. Please report this issue.")

    
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

    # get cpu architecture
    cpu_arch = pl.processor()

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

    # ToDo: make more generic and not only for thinkpad
    # print current fan speed
    #current_fans = p.sensors_fans()['thinkpad'][0].current
    #print("\nCPU fan speed:", current_fans, "RPM")

def read_log():
    # deploy cpufreqctl script (if missing)
    if os.path.isfile(auto_cpufreq_log_file):
        # read /var/log/auto-cpufreq.log
        s.call(["tail", "-n 50", "-f", auto_cpufreq_log_file])
    else:
        print("\n" + "-" * 30 + " auto-cpufreq log " + "-" * 31 + "\n")
        print("ERROR:\n\nauto-cpufreq log is missing.\n\nMake sure to run: \"python3 auto-cpufreq --daemon\" first")
    footer(79)
        
def log_check():
    if os.path.isfile(auto_cpufreq_log_file):
        print("\n" + "-" * 30 + " auto-cpufreq log " + "-" * 31 + "\n")
        print("ERROR: prevention from running multiple instances.")
        print("\nIt seems like auto-cpufreq daemon is already running in background.\n\nTo view live log run:\nauto-cpufreq --log")
        print("\nTo disable and remove auto-cpufreq daemon, run:\nautocpu-freq --remove")
        footer(79)
        sys.exit()

# cli
@click.command()
@click.option("--monitor", is_flag=True, help="TBU")
@click.option("--live", is_flag=True, help="TBU")
@click.option("--daemon/--remove", default=True, help="TBU")
@click.option("--log", is_flag=True, help="TBU")

def cli(monitor, live, daemon, log):
    # print --help by default if no argument is provided when auto-cpufreq is run
    if len(sys.argv) == 1:
        print("\n" + "-" * 22 + " auto-cpufreq " + "-" * 23 + "\n")
        print("auto-cpufreq - TBU")
        print("\nExample usage: " + tool_run + " --install user")
        print("\n-----\n")

        s.call(["python3", "auto-cpufreq.py", "--help"])
        print("\n" +  "-" * 59 + "\n")
    else:
        if monitor:
            while True:
                log_check()
                #driver_check()
                gov_check()
                sysinfo()
                mon_autofreq()
                mon_turbo()
                countdown(10)
                subprocess.call("clear")
        elif live:
            while True:
                log_check()
                root_check()
                driver_check()
                gov_check()
                sysinfo()
                set_autofreq()
                countdown(10)
                subprocess.call("clear")
        elif log:
                read_log()
        elif daemon:
                log_check()
                root_check()
                driver_check()
                gov_check()
                deploy()
        elif remove:
                root_check()
                remove()

if __name__ == '__main__':
    # while True:
        cli()
 