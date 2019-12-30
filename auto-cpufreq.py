#!/usr/bin/env python3

import subprocess
import os
import sys
import time
import psutil
import cpuinfo
import platform
import distro
import re

# ToDo:
# - check if debian based + first time setup (install necessary packages)
# - add option to run as daemon on boot
# - add revert options
# - sort out imports
# - add option to enable turbo in powersave
# - go thru all other ToDo's
# - copy cpufreqctl script if it doesn't exist
# - clean/refresh screen instead of constant publish

# global var
p = psutil
s = subprocess
tool_run = "python3 auto-cpufreq.py"

# check for necessary driver
def driver_check():
    driver = s.getoutput("cpufreqctl --driver")
    if driver != "intel_pstate":
        print("\n" + "-" * 23 + " Driver check " + "-" * 23 + "\n")
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
                print("\n" + "-" * 9 + " Checking for necessary scaling governors " + "-" * 9 + "\n")
                sys.exit("ERROR:\n\nCouldn't find any of the necessary scaling governors.\n")

# root check func
def root_check():
    if not os.geteuid() == 0:
        sys.exit(f"\nMust be run as root, i.e: \"sudo {tool_run}\"\n")
        exit(1)

# set powersave
def set_powersave():
    print("\nSetting: powersave")
    s.run("cpufreqctl --governor --set=powersave", shell=True)
    
    print("Setting turbo: off")
    s.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)

# set performance
def set_performance():
    print("Using \"performance\" governor\n")
    s.run("cpufreqctl --governor --set=performance", shell=True)

    # enable turbo boost
    set_turbo()

def set_turbo():
    # ToDo: replace with psutil.getloadavg()? (available in 5.6.2)
    load1m, _, _ = os.getloadavg()
    cpuload = p.cpu_percent(interval=1)

    print("Total CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    # ToDo: move load and cpuload to sysinfo
    if load1m > 2:
        print("High load, turbo bost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        
        # print("High load:", load1m)
        # print("CPU load:", cpuload, "%")
    elif cpuload > 25:
        print("High CPU load, turbo boost: on")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
    else:
        print("Load optimal, turbo boost: off")
        s.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
    
def autofreq():

    print("\n" + "-" * 18 + " CPU frequency scaling " + "-" * 19 + "\n")

    # ToDo: make a function and more generic (move to psutil)
    # check battery status
    get_bat_state = s.getoutput("cat /sys/class/power_supply/BAT0/status")
    bat_state = get_bat_state.split()[0]

    # auto cpufreq based on battery state
    if bat_state == "Discharging":
        print("Battery is: discharging")
        set_powersave()
    elif bat_state == "Charging" or "Full":
        print("Battery is: charging")
        set_performance()
    else:
        print("Couldn't detrmine battery status. Please report this issue.")
    
def sysinfo():

    print("\n" + "-" * 20 + " System information " + "-" * 20 + "\n")
    core_usage = p.cpu_freq(percpu=True)
    cpu_brand = cpuinfo.get_cpu_info()['brand']
    cpu_arch = cpuinfo.get_cpu_info()['arch']
    cpu_count = cpuinfo.get_cpu_info()['count']

    fdist = distro.linux_distribution()
    dist = " ".join(x for x in fdist)
    print("Linux distro: " + dist)
    print("Linux kernel: " + platform.release())
    print("Architecture:", cpu_arch)

    print("Processor:", cpu_brand)
    print("Cores:", cpu_count)

    print("\n" + "-" * 20 + " Current CPU state " + "-" * 21 + "\n")
    print("CPU frequency for each core:\n")
    core_num = 0
    while core_num < cpu_count:
        print("CPU" + str(core_num) + ": {:.0f}".format(core_usage[core_num].current) + " MHz")
        core_num += 1

    # ToDo: make more generic and not only for thinkpad
    #print(psutil.sensors_fans())
    current_fans = p.sensors_fans()['thinkpad'][0].current
    print("\nCPU fan speed:", current_fans), "RPM"

    # ToDo: add CPU temperature for each core
    # issue: https://github.com/giampaolo/psutil/issues/1650
    #print(psutil.sensors_temperatures()['coretemp'][1].current)

if __name__ == '__main__':
    while True:
        root_check()
        driver_check()
        gov_check()
        sysinfo()
        autofreq()
        time.sleep(10)