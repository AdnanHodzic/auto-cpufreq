#!/usr/bin/env python3
import os
import subprocess
from auto_cpufreq.utils.config import config

POWER_SUPPLY_DIR = "/sys/class/power_supply/"

def set_battery(value, mode, bat):
    path = f"{POWER_SUPPLY_DIR}BAT{bat}/charge_{mode}_threshold"
    if os.path.isfile(path): subprocess.check_output(f"echo {value} | tee {path}", shell=True, text=True)
    else: print(f"WARNING: {path} does NOT exist")

def get_threshold_value(mode):
    conf = config.get_config()
    return conf["battery"][f"{mode}_threshold"] if conf.has_option("battery", f"{mode}_threshold") else (0 if mode == "start" else 100)

def ideapad_acpi_setup():
    conf = config.get_config()

    if not (conf.has_option("battery", "enable_thresholds") and conf["battery"]["enable_thresholds"] == "true"): return

    if os.path.exists(POWER_SUPPLY_DIR):
        battery_count = len([name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith('BAT')])

        for bat in range(battery_count):
            set_battery(get_threshold_value("start"), "start", bat)
            set_battery(get_threshold_value("stop"), "stop", bat)
    else: print(f"WARNING: could NOT access {POWER_SUPPLY_DIR}")

def ideapad_acpi_print_thresholds():
    battery_count = len([name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith('BAT')])
    print("\n-------------------------------- Battery Info ---------------------------------\n")
    print(f"battery count = {battery_count}")
    for b in range(battery_count):
        try:
            with open(f'{POWER_SUPPLY_DIR}BAT{b}/charge_start_threshold', 'r') as f:
                print(f'battery{b} start threshold = {f.read()}', end="")

            with open(f'{POWER_SUPPLY_DIR}BAT{b}/charge_stop_threshold', 'r') as f:
                print(f'battery{b} stop threshold = {f.read()}', end="")

        except Exception: print(f"ERROR: failed to read battery {b} thresholds")
