#!/usr/bin/env python3
import os
import subprocess
from auto_cpufreq.core import get_config


def set_battery(value, mode, bat):
    try:
        subprocess.check_output(
            f"echo {value} | tee /sys/class/power_supply/BAT{bat}/charge_{mode}_threshold", shell=True, text=True)
    except Exception as e:
        print(f"Error writing to file_path: {e}")


def get_threshold_value(mode):

    config = get_config()
    if config.has_option("battery", f"{mode}_threshold"):
        return config["battery"][f"{mode}_threshold"]
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
    config = get_config()

    if not config.has_option("battery", "enable_thresholds"):
        return
    if not config["battery"]["enable_thresholds"] == "true":
        return

    battery_count = len([name for name in os.listdir(
        "/sys/class/power_supply/") if name.startswith('BAT')])

    if config.has_option("battery", "ideapad_laptop_conservation_mode"):
        if config["battery"]["ideapad_laptop_conservation_mode"] == "true":
            conservation_mode(1)
            return
        if config["battery"]["ideapad_laptop_conservation_mode"] == "false":
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
    print(f"number of batteries = {battery_count}")
    for b in range(battery_count):
        try:
            with open(f'/sys/class/power_supply/BAT{b}/charge_start_threshold', 'r') as f:
                print(f'battery{b} start threshold is set to {f.read()}')
                f.close()

            with open(f'/sys/class/power_supply/BAT{b}/charge_stop_threshold', 'r') as f:
                print(f'battery{b} stop threshold is set to {f.read()}')
                f.close()

        except Exception as e:
            print(f"Error reading battery thresholds: {e}")
