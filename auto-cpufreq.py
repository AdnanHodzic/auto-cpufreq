#!/usr/bin/python3

import subprocess
import os
import sys
import time
import psutil

# ToDo:
# - only run if driver is Intel pstate
# - display cpu/load/sensors(?) info
# - check if debian based
# - set to install necesasry packages?
# - even when plugged in go back to powersave depending on load
# - sort out imports
# go thru all other ToDo's

p = psutil
s = subprocess
tool_run = "python3 auto-cpufreq.py"

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
    s.run("sudo cpufreqctl --governor --set=powersave", shell=True)
    
    print("Setting turbo: off")
    s.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)

# set performance
def set_performance():
    print("\nSetting: performance")
    s.run("sudo cpufreqctl --governor --set=performance", shell=True)
    # alternative
    # sudo echo performance /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

    # enable turbo boost
    set_turbo()

def set_turbo():
    load1m, _, _ = os.getloadavg()

    print("-" * 20)
    print("CPU usage:", p.cpu_percent(interval=1), "%")
    print("Current load:", load1m)

    if load1m > 2:
        print("Load too high, turbo: ON")
        s.run("echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)
        
        print("High CPU:", p.cpu_percent(interval=1), "%")
        print("High load:", load1m)
    else:
        print("Load optimal, turbo: OFF")
        s.run("echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo", shell=True)

    #print(psutil.cpu_freq())
    #print(psutil.cpu_count())
    
def autofreq():
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