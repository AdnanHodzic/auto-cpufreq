#!/usr/bin/python3

import subprocess
import os
import sys
import time
import psutil
import platform

# ToDo:
# - only run if driver is Intel pstate
# - check if debian based
# - set to install necesasry packages?
# - even when plugged in go back to powersave depending on load
# - sort out imports
# - add option to enable turbo in powersave
# - go thru all other ToDo's

# global var
p = psutil
s = subprocess
tool_run = "python3 auto-cpufreq.py"

def driver_check():
    driver = s.getoutput("cpufreqctl --driver")
    if driver != "intel_pstate":
        sys.exit(f"\nError:\nOnly laptops with enabled \"intel_pstate\" (CPU Performance Scaling Driver) are supported.\n")

        # print distro
        # print chipset
        # print laptop
        

def avail_gov():
    # available governors
    get_avail_gov = s.getoutput("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors")
    # ToDo: make check to fail if powersave and performance are not available

    # check current scaling governor
    #get_gov_state = subprocess.getoutput("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    get_gov_state = s.getoutput("cpufreqctl --governor")

    gov_state = get_gov_state.split()[0]
    print("\nCurrent scaling_governor: " + gov_state)

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
    print("\nSetting: performance")
    s.run("cpufreqctl --governor --set=performance", shell=True)
    # alternative
    # echo performance /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

    # enable turbo boost
    set_turbo()

def set_turbo():
    load1m, _, _ = os.getloadavg()
    cpuload = p.cpu_percent(interval=1)

    print("CPU usage:", cpuload, "%")
    print("Current load:", load1m)
    print("-" * 25)

    if load1m > 2:
        print("High load, turbo: ON")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        
        print("High load:", load1m)
        print("CPU load:", cpuload, "%")
    elif cpuload > 25:
        print("High CPU load, turbo: ON")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
    else:
        print("Load optimal, turbo: OFF")
        s.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)

    #print(psutil.cpu_freq())
    #print(psutil.cpu_count())

# - display cpu/load/sensors(?) info
#def sysload_info():
    # distro
    # kernel
    # number of cores
    # driver?
    # chipset
    # laptop maker/model?
    # sensors?
    
def autofreq():

    driver_check()

    # ToDo: make a function?
    # check battery status
    get_bat_state = s.getoutput("cat /sys/class/power_supply/BAT0/status")
    bat_state = get_bat_state.split()[0]

    # auto cpufreq based on battery state
    if bat_state == "Discharging":
        set_powersave()
    elif bat_state == "Charging" or "Full":
        set_performance()

if __name__ == '__main__':
    while True:
        root_check()

        #load()
        #set_powersave()

        autofreq()
        time.sleep(10)