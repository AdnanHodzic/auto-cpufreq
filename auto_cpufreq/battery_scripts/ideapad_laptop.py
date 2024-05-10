#!/usr/bin/env python3
import os
import subprocess
from auto_cpufreq.utils.config import config


def set_battery(value, mode, bat):
    path = f"/sys/class/power_supply/BAT{bat}/charge_{mode}_threshold"
    if os.path.exists(path):
        subprocess.check_output(
            f"echo {value} | tee /sys/class/power_supply/BAT{bat}/charge_{mode}_threshold", shell=True, text=True)
    else:
        print(f"WARNING: {path} does NOT exist")


def get_threshold_value(mode):

    conf = config.get_config()
    if conf.has_option("battery", f"{mode}_threshold"):
        return conf["battery"][f"{mode}_threshold"]
    else:
        if mode == "start":
            return 0
        else:
            return 100


def conservation_mode(value):
    try:
        subprocess.check_output(
            f"echo {value} | tee /sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode", shell=True, text=True)
        print(f"conservation_mode is {value}")
        return
    except:
        print("unable to set conservation mode")
        return


def check_conservation_mode():
    try:
        value = subprocess.check_output(
            "cat /sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode", shell=True, text=True)
        if value == "1":
            return True
        elif value == "0":
            return False
        else:
            print("could not get value from conservation mode")
            return None
    except:
        print("could not get the value from conservation mode")
        return False


def ideapad_laptop_setup():
    conf = config.get_config()

    if not conf.has_option("battery", "enable_thresholds"):
        return
    if not conf["battery"]["enable_thresholds"] == "true":
        return

    battery_count = len([name for name in os.listdir(
        "/sys/class/power_supply/") if name.startswith('BAT')])

    if conf.has_option("battery", "ideapad_laptop_conservation_mode"):
        if conf["battery"]["ideapad_laptop_conservation_mode"] == "true":
            conservation_mode(1)
            return
        if conf["battery"]["ideapad_laptop_conservation_mode"] == "false":
            conservation_mode(0)

    if check_conservation_mode() is False:
        for bat in range(battery_count):
            set_battery(get_threshold_value("start"), "start", bat)
            set_battery(get_threshold_value("stop"), "stop", bat)
    else:
        print("conservation mode is enabled unable to set thresholds")


def ideapad_laptop_print_thresholds():
    if check_conservation_mode() is True:
        print("conservation mode is on")
        return

    battery_count = len([name for name in os.listdir(
        "/sys/class/power_supply/") if name.startswith('BAT')])
    print("\n-------------------------------- Battery Info ---------------------------------\n")
    print(f"battery count = {battery_count}")
    for b in range(battery_count):
        try:
            with open(f'/sys/class/power_supply/BAT{b}/charge_start_threshold', 'r') as f:
                print(f'battery{b} start threshold = {f.read()}', end="")
                f.close()

            with open(f'/sys/class/power_supply/BAT{b}/charge_stop_threshold', 'r') as f:
                print(f'battery{b} stop threshold = {f.read()}', end="")
                f.close()

        except Exception as e:
            print(f"ERROR: failed to read battery thresholds: {e}")
