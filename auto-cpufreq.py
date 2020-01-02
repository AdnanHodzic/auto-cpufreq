#!/usr/bin/env python3
# 
# ToDo: add description

import subprocess
import os
import sys
import time
import psutil
#import cpuinfo
import platform
#import distro
#import re
#from subprocess import call
import click

# ToDo:

# - add nice message at the end of deploy + add print for each action
# - add parameter to read logs if daemon is set
# - add option to disable bluetooth (only in daemon mode)
# - add uninstall options for daemon

# - sort out imports
# - make shortcut for platform
# - go thru all other ToDo's

# - fill out every TBU (cli + auto-cpufreq.service file)
# - add readme + list need to install all necessary packages

# global vars
p = psutil
s = subprocess
tool_run = "python3 auto-cpufreq.py"

# get turbo boost state
cur_turbo = s.getoutput("cat /sys/devices/system/cpu/intel_pstate/no_turbo")

# get current scaling governor
get_cur_gov = s.getoutput("cpufreqctl --governor")
gov_state = get_cur_gov.split()[0]

# get battery state
bat_state = p.sensors_battery().power_plugged

# get CPU utilization as a percentage
cpuload = p.cpu_percent(interval=1)

def deploy():

    # deploy cpufreqctl script (if missing)
    if os.path.isfile("/usr/bin/cpufreqctl"):
        pass
    else:
        os.system("cp scripts/cpufreqctl.sh /usr/bin/cpufreqctl")

    # deploy auto-cpufreq binary
    os.system("cp auto-cpufreq.py /usr/bin/auto-cpufreq")

    # deploy auto-cpufreq daemon script
    os.system("cp scripts/auto-cpufreq-daemon.sh /usr/bin/auto-cpufreq-daemon")

    # create auto-cpufreq systemd unit file
    os.system("cp scripts/auto-cpufreq.service /lib/systemd/system/auto-cpufreq.service")

    s.call("/usr/bin/auto-cpufreq-daemon", shell=True)

    # ToDo: disable bluetooth on boot

    # ToDo: add nice message as multiline
    print("auto-cpufreq daemon started and running in background.")
    print("Logs are available in: /var/log/auto-cpufreq.log")
    print("View live logs by running i.e: \ntail -n 50 -f /var/log/auto-cpufreq.log")


def footer(l):
    print("\n" + "-" * l + "\n")

# check for necessary driver
def driver_check():
    driver = s.getoutput("cpufreqctl --driver")
    if driver != "intel_pstate":
        print("\n" + "-" * 32 + " Driver check " + "-" * 33 + "\n")
        sys.exit("ERROR:\n\n\"intel_pstate\" CPU Performance Scaling Driver is not enabled.\n")

# check for necessary scaling governors
def gov_check():
    avail_gov = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"

    governors=['performance','powersave']

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
        sys.exit(f"Must be run as root, i.e: \"sudo {tool_run}\"\n")
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
    print("\nSetting: powersave")
    s.run("cpufreqctl --governor --set=powersave", shell=True)
    
    print("Setting turbo boost: off")
    s.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)

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

    print("\n" + "-" * 5 + "\n")

    # ToDo: duplicate + replace with psutil.getloadavg()? (available in 5.6.2)
    load1m, _, _ = os.getloadavg()

    print("Total CPU usage:", cpuload, "%")
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

    print("\n" + "-" * 5 + "\n")

    # ToDo: duplicate + replace with psutil.getloadavg()? (available in 5.6.2)
    load1m, _, _ = os.getloadavg()

    print("Total CPU usage:", cpuload, "%")
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

    # get info about linux distro
    # ToDo: use or get rid of
    #fdist = distro.linux_distribution()
    fdist = platform.linux_distribution()
    dist = " ".join(x for x in fdist)
    print("Linux distro: " + dist)
    print("Linux kernel: " + platform.release())

    # get cpu architecture
    cpu_arch = platform.processor()

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

    # print cpu max frequency
    max_cpu_freq = p.cpu_freq().max
    print("CPU max frequency: " + "{:.0f}".format(max_cpu_freq) + " MHz")
    print("Cores:", cpu_count)

    print("\n" + "-" * 30 + " Current CPU state " + "-" * 30 + "\n")

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
    current_fans = p.sensors_fans()['thinkpad'][0].current
    print("\nCPU fan speed:", current_fans, "RPM")

# cli
@click.command()
@click.option("--monitor", is_flag=True, help="TBU")
@click.option("--live", is_flag=True, help="TBU")
@click.option("--daemon/--remove", default=True, help="TBU")

def cli(monitor, live, daemon):
    # print --help by default if no argument is provided when auto-cpufreq is run
    if len(sys.argv) == 1:
        print("\n" + "-" * 22 + " auto-cpufreq " + "-" * 23 + "\n")
        print("auto-cpufreq - TBU")
        print("\nExample usage: " + tool_run + "--install user")
        print("\n-----\n")

        s.call(["python3", "auto-cpufreq.py", "--help"])
        print("\n" +  "-" * 59 + "\n")
    else:
        if monitor:
            while True:
                #root_check()
                driver_check()
                gov_check()
                sysinfo()
                mon_autofreq()
                mon_turbo()
                countdown(10)
                subprocess.call("clear")
        elif live:
            while True:
                root_check()
                driver_check()
                gov_check()
                sysinfo()
                set_autofreq()
                countdown(10)
                subprocess.call("clear")
        elif daemon:
            #while True:
                root_check()
                driver_check()
                gov_check()
                deploy()
        else:
            print("remove ...")

if __name__ == '__main__':
    # while True:
        cli()
 