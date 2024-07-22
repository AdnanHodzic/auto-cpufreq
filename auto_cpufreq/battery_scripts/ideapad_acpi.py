#!/usr/bin/env python3
import os
from subprocess import check_output

from auto_cpufreq.globals import CONFIG, POWER_SUPPLY_DIR

def set_battery(value, mode, bat):
    path = f"{POWER_SUPPLY_DIR}{bat}/charge_{mode}_threshold"
    if os.path.isfile(path): check_output(f"echo {value} | tee {path}", shell=True, text=True)
    else: print(f"WARNING: {path} does NOT exist")

def get_threshold_value(mode):
    option = ("battery", f"{mode}_threshold")
    return CONFIG.get_option(*option) if CONFIG.has_option(*option) else (0 if mode == "start" else 100)

def ideapad_acpi_setup():
    option = ("battery", "enable_thresholds")
    if not (CONFIG.has_option(*option) and CONFIG.get_option(*option) == "true"): return

    if os.path.exists(POWER_SUPPLY_DIR):
        batteries = [name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith('BAT')]
        
        for bat in batteries:
            set_battery(get_threshold_value("start"), "start", bat)
            set_battery(get_threshold_value("stop"), "stop", bat)
    else: print("WARNING: could NOT access", POWER_SUPPLY_DIR)

def ideapad_acpi_print_thresholds():
    batteries = [name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith('BAT')]
    print("\n-------------------------------- Battery Info ---------------------------------\n")
    print(f"battery count = {len(batteries)}")
    for bat in batteries:
        try:
            print(bat, "start threshold =", check_output(["cat", POWER_SUPPLY_DIR+bat+"/charge_start_threshold"]))
            print(bat, "stop threshold =", check_output(["cat", POWER_SUPPLY_DIR+bat+"/charge_stop_threshold"]))
        except Exception as e: print(f"ERROR: failed to read battery {bat} thresholds:", repr(e))
