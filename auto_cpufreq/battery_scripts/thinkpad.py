#!/usr/bin/env python3
import os
from subprocess import check_output, CalledProcessError

from auto_cpufreq.config.config import config
from auto_cpufreq.globals import POWER_SUPPLY_DIR

def set_battery(value, mode, bat) -> bool:
    """
    Return false only if command fails
    """
    path = f"{POWER_SUPPLY_DIR}{bat}/charge_{mode}_threshold"
    if os.path.isfile(path): 
        try:
            check_output(f"echo {value} | tee {path}", shell=True, text=True)
        except CalledProcessError as e:
          print(f"WARNING: Could not write battery threshold {value} to {path}")
          return False
    else: 
        print(f"WARNING: {path} does NOT exist")
    return True

def get_threshold_value(mode):
    conf = config.get_config()
    return conf["battery"][f"{mode}_threshold"] if conf.has_option("battery", f"{mode}_threshold") else (0 if mode == "start" else 100)

def thinkpad_setup():
    conf = config.get_config()

    if not (conf.has_option("battery", "enable_thresholds") and conf["battery"]["enable_thresholds"] == "true"): return

    if os.path.exists(POWER_SUPPLY_DIR):
        batteries = [name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith('BAT')]

        for bat in batteries:
            could_set_start = set_battery(get_threshold_value("start"), "start", bat)
            could_set_stop = set_battery(get_threshold_value("stop"), "stop", bat)
            if not could_set_start or not could_set_stop:
                # Maybe the values don't line up properly with the currently set ones, try in reverse order
                # E.g. start is high that the initial stop
                could_set_stop = set_battery(get_threshold_value("stop"), "stop", bat)
                could_set_start = set_battery(get_threshold_value("start"), "start", bat)
            if not could_set_start or not could_set_stop:
                raise OSError(f"Could not set battery thresholds for {bat}!")
    else: print(f"WARNING {POWER_SUPPLY_DIR} does NOT esixt")


def thinkpad_print_thresholds():
    batteries = [name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith('BAT')]
    print("\n-------------------------------- Battery Info ---------------------------------\n")
    print(f"battery count = {len(batteries)}")
    for bat in batteries:
        try:
            print(bat, "start threshold =", check_output(["cat", POWER_SUPPLY_DIR+bat+"/charge_start_threshold"]))
            print(bat, "stop threshold =", check_output(["cat", POWER_SUPPLY_DIR+bat+"/charge_stop_threshold"]))
        except Exception as e: print(f"ERROR: failed to read battery {bat} thresholds:", repr(e))
