#!/usr/bin/env python3
#
# auto-cpufreq - core functionality

# ToDo: re-order in a single line?
import subprocess
import os
import sys
import time
import psutil
import platform
import click
import power
import signal

# ToDo:
# - re-enable CPU fan speed display and make more generic and not only for thinkpad
# - replace get system/CPU load from: psutil.getloadavg() | available in 5.6.2)

# global vars
p = psutil
pl = platform
s = subprocess
cpus = os.cpu_count()
pw = power

# get turbo boost state
turbo_loc = "/sys/devices/system/cpu/intel_pstate/no_turbo"
cur_turbo = s.getoutput("cat " + turbo_loc)
 
 # govs/script loc
avail_gov_loc = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"
scripts_dir = "/usr/local/share/auto-cpufreq/scripts/"

# get current scaling governor
get_cur_gov = s.getoutput("cpufreqctl --governor")
gov_state = get_cur_gov.split()[0]

# get battery state
bat_state = pw.PowerManagement().get_providing_power_source_type()

# auto-cpufreq log file
auto_cpufreq_log_file = "/var/log/auto-cpufreq.log"
auto_cpufreq_log_file_snap = "/var/snap/auto-cpufreq/current/auto-cpufreq.log"

# daemon check
dcheck = s.getoutput("snapctl get daemon")

# deploy cpufreqctl script
def cpufreqctl():
    # detect if running on a SNAP
    if os.getenv('PKG_MARKER') == "SNAP":
        pass
    else:
        # deploy cpufreqctl script (if missing)
        if os.path.isfile("/usr/bin/cpufreqctl"):
            os.system("cp /usr/bin/cpufreqctl /usr/bin/cpufreqctl.auto-cpufreq.bak")
            os.system("cp " + scripts_dir + "cpufreqctl.sh /usr/bin/cpufreqctl")
        else:
            os.system("cp " + scripts_dir + "cpufreqctl.sh /usr/bin/cpufreqctl")

# restore original cpufreqctl script
def cpufreqctl_restore():
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

# print footer func
def footer(l):
    print("\n" + "-" * l + "\n")

def deploy_complete_msg():
    print("\n" + "-" * 17 + " auto-cpufreq daemon installed and running " + "-" * 17 + "\n")
    print("To view live log, run:\nauto-cpufreq --log")
    print("\nTo disable and remove auto-cpufreq daemon, run:\nsudo auto-cpufreq --remove")
    footer(79)

def remove_complete_msg():
    print("\n" + "-" * 25 + " auto-cpufreq daemon removed " + "-" * 25 + "\n")
    print("auto-cpufreq successfully removed.")
    footer(79)

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

    # create log file
    create_file(auto_cpufreq_log_file)

    print("\n* Deploy auto-cpufreq install script")
    os.system("cp " + scripts_dir + "/auto-cpufreq-install.sh /usr/bin/auto-cpufreq-install")

    print("\n* Deploy auto-cpufreq remove script")
    os.system("cp " + scripts_dir + "/auto-cpufreq-remove.sh /usr/bin/auto-cpufreq-remove")

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

    # remove auto-cpufreq-remove
    os.remove("/usr/bin/auto-cpufreq-remove")

    # delete log file
    delete_file(auto_cpufreq_log_file)

    # restore original cpufrectl script
    cpufreqctl_restore()

# check for necessary scaling governors
def gov_check():
    avail_gov = avail_gov_loc

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
        print("ERROR:\n\nMust be run root for this functionality to work, i.e: \nsudo auto-cpufreq")
        footer(79)
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
    print("Setting to use: \"powersave\" governor")
    s.run("cpufreqctl --governor --set=powersave", shell=True)
    if (os.path.exists("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference")):
        s.run("cpufreqctl --epp --set=balance_power", shell=True)
        print("Setting to use: \"balance_power\" EPP") 

    # get system/CPU load
    load1m, _, _ = os.getloadavg()
    # get CPU utilization as a percentage
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    # conditions for setting turbo in powersave
    if load1m > cpus / 7:
        print("High load, setting turbo boost: on")
        s.run("echo 0 > " + turbo_loc, shell=True)
        footer(79)
    elif cpuload > 25:
        print("High CPU load, setting turbo boost: on")
        s.run("echo 0 > " + turbo_loc, shell=True)
        footer(79)
    else:
        print("Load optimal, setting turbo boost: off")
        s.run("echo 1 > " + turbo_loc, shell=True)
        footer(79)

# make turbo suggestions in powersave
def mon_powersave():

    # get system/CPU load
    load1m, _, _ = os.getloadavg()
    # get CPU utilization as a percentage
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    if load1m > cpus / 7:
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
    print("Setting to use \"performance\" governor")
    s.run("cpufreqctl --governor --set=performance", shell=True)
    if (os.path.exists("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference")):
        s.run("cpufreqctl --epp --set=balance_performance", shell=True)
        print("Setting to use: \"balance_performance\" EPP")


    # get system/CPU load
    load1m, _, _ = os.getloadavg()
    # get CPU utilization as a percentage
    cpuload = p.cpu_percent(interval=1)

    print("\nTotal CPU usage:", cpuload, "%")
    print("Total system load:", load1m, "\n")

    # conditions for setting turbo in performance
    if load1m >= cpus / 5:
        print("High load, setting turbo boost: on")
        s.run("echo 0 > " + turbo_loc, shell=True)
        footer(79)
    elif cpuload > 20:
        print("High CPU load, setting turbo boost: on")
        s.run("echo 0 > " + turbo_loc, shell=True)
        footer(79)
    else:
        print("Load optimal, setting turbo boost: off")
        s.run("echo 1 > "  + turbo_loc, shell=True)
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
        print("Suggesting use of \"performance\" governor\nCurrently using:", gov_state)
        mon_performance()
    elif bat_state == pw.POWER_TYPE_BATTERY:
        print("Battery is: discharging")
        print("Suggesting use of \"powersave\" governor\nCurrently using:", gov_state)
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

    # get distro information in snap env.
    if os.getenv("PKG_MARKER") == "SNAP":
        searchfile = open("/var/lib/snapd/hostfs/etc/os-release", "r")
        for line in searchfile:
            if line.startswith('NAME='):
                distro = line[5:line.find('$')].strip("\"")
                continue
            elif line.startswith('VERSION='):
                version = line[8:line.find('$')].strip("\"")
                continue

            dist = distro + " " + version
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

# create file func
def create_file(file):
    open(file, 'a').close()

# delete file func
def delete_file(file):
    if os.path.exists(file):
        os.remove(file)

# read log func
def read_log():
    if os.getenv("PKG_MARKER") == "SNAP":
         s.call(["tail", "-n 50", "-f", auto_cpufreq_log_file_snap])
    elif os.path.isfile(auto_cpufreq_log_file):
        s.call(["tail", "-n 50", "-f", auto_cpufreq_log_file])
    else:
        print("\n" + "-" * 30 + " auto-cpufreq log " + "-" * 31 + "\n")
        print("ERROR: auto-cpufreq log is missing.\n\nMake sure to run: \"auto-cpufreq --install\" first")
    footer(79)

# check if program (argument) is running
def is_running(program, argument):
    # iterate over all process id's found by psutil
    for pid in psutil.pids():
        try:
            # requests the process information corresponding to each process id
            p = psutil.Process(pid)
            # check if value of program-variable that was used to call the function matches the name field of the plutil.Process(pid) output 
            if program in p.name():
                # check output of p.name(), output name of program
                # p.cmdline() - echo the exact command line via which p was called.
                for arg in p.cmdline():
                    if argument in str(arg):  
                        return True
                    else:
                        pass
            else:
                pass
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
