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


def thinkpad_setup():
    config = get_config()

    if not config.has_option("battery", "enable_thresholds"):
        return
    if not config["battery"]["enable_thresholds"] == "true":
        return

    battery_count = len([name for name in os.listdir(
        "/sys/class/power_supply/") if name.startswith('BAT')])

    for bat in range(battery_count):
        set_battery(get_threshold_value("start"), "start", bat)
        set_battery(get_threshold_value("stop"), "stop", bat)


def thinkpad_print_thresholds():
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
