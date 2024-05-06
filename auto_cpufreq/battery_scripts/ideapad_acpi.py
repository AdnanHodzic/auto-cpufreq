#!/usr/bin/env python3
import os
import subprocess
from auto_cpufreq.core import get_config


def set_battery(value, mode, bat):
    path = f"/sys/class/power_supply/BAT{bat}/charge_{mode}_threshold"
    if os.path.isfile(path):
        subprocess.check_output(
            f"echo {value} | tee {path}", shell=True, text=True)
    else:
        print(f"WARNING: {path} does NOT exist")


def get_threshold_value(mode):

    config = get_config()
    if config.has_option("battery", f"{mode}_threshold"):
        return config["battery"][f"{mode}_threshold"]
    else:
        if mode == "start":

            return 0
        else:
            return 100


def ideapad_acpi_setup():
    config = get_config()

    if not config.has_option("battery", "enable_thresholds"):
        return
    if not config["battery"]["enable_thresholds"] == "true":
        return

    if os.path.exists("/sys/class/power_supply/"):
        battery_count = len([name for name in os.listdir(
            "/sys/class/power_supply/") if name.startswith('BAT')])

        for bat in range(battery_count):
            set_battery(get_threshold_value("start"), "start", bat)
            set_battery(get_threshold_value("stop"), "stop", bat)
    else:
        print("WARNING: could NOT access /sys/class/power_supply")


def ideapad_acpi_print_thresholds():
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

        except Exception:
            print(f"ERROR: failed to read battery {b} thresholds")
