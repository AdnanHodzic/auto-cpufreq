#!/usr/bin/env python3
import os
from subprocess import check_output

from auto_cpufreq.globals import CONFIG, CONSERVATION_MODE_FILE, POWER_SUPPLY_DIR

def set_battery(value, mode, bat):
    path = f"{POWER_SUPPLY_DIR}{bat}/charge_{mode}_threshold"
    if os.path.exists(path):
        check_output(f"echo {value} | tee {POWER_SUPPLY_DIR}{bat}/charge_{mode}_threshold", shell=True, text=True)
    else: print(f"WARNING: {path} does NOT exist")

def get_threshold_value(mode):
    option = ("battery", f"{mode}_threshold")
    return CONFIG.get_option(*option) if CONFIG.has_option(*option) else (0 if mode == "start" else 100)

def conservation_mode(value):
    try:
        check_output(f"echo {value} | tee {CONSERVATION_MODE_FILE}", shell=True, text=True)
        print(f"conservation_mode is {value}")
    except: print("unable to set conservation mode")
    return

def check_conservation_mode():
    try:
        value = check_output(["cat", CONSERVATION_MODE_FILE], text=True)
        if value == "1": return True
        elif value == "0": return False
        else:
            print("could not get value from conservation mode")
            return None
    except:
        print("could not get the value from conservation mode")
        return False

def ideapad_laptop_setup():
    option = ("battery", "enable_thresholds")
    if not (CONFIG.has_option(*option) and CONFIG.get_option(*option) == "true"): return

    batteries = [name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith("BAT")]

    option = ("battery", "ideapad_laptop_conservation_mode")
    if CONFIG.has_option(*option):
        if CONFIG.get_option(*option) == "true":
            conservation_mode(1)
            return
        if CONFIG.get_option(*option) == "false": conservation_mode(0)

    if not check_conservation_mode():
        for bat in batteries:
            set_battery(get_threshold_value("start"), "start", bat)
            set_battery(get_threshold_value("stop"), "stop", bat)
    else: print("conservation mode is enabled unable to set thresholds")

def ideapad_laptop_print_thresholds():
    if check_conservation_mode():
        print("conservation mode is on")
        return

    batteries = [name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith("BAT")]

    print("\n-------------------------------- Battery Info ---------------------------------\n")
    print(f"battery count = {len(batteries)}")
    for bat in batteries:
        try:
            print(bat, "start threshold =", check_output(["cat", POWER_SUPPLY_DIR+bat+"/charge_start_threshold"]))
            print(bat, "stop threshold =", check_output(["cat", POWER_SUPPLY_DIR+bat+"/charge_stop_threshold"]))
        except Exception as e: print(f"ERROR: failed to read battery {bat} thresholds:", repr(e))
