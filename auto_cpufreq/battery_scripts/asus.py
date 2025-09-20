#!/usr/bin/env python3
import os
from subprocess import check_output

from auto_cpufreq.config.config import config
from auto_cpufreq.globals import POWER_SUPPLY_DIR


def set_battery(value, mode, bat):
    path = f"{POWER_SUPPLY_DIR}{bat}/charge_{mode}_threshold"

    # Add fallbacks
    fallback_mode = "start" if mode == "start" else "end"
    fallback_path = f"{POWER_SUPPLY_DIR}{bat}/charge_control_{fallback_mode}_threshold"

    if os.path.isfile(path):
        check_output(f"echo {value} | tee {path}", shell=True, text=True)
    elif os.path.isfile(fallback_path):
        check_output(f"echo {value} | tee {fallback_path}", shell=True, text=True)
    else:
        print(f"WARNING: {path} does NOT exist")


def get_threshold_value(mode):
    conf = config.get_config()
    return (
        conf["battery"][f"{mode}_threshold"]
        if conf.has_option("battery", f"{mode}_threshold")
        else (0 if mode == "start" else 100)
    )


def asus_setup():
    conf = config.get_config()

    if not (
        conf.has_option("battery", "enable_thresholds")
        and conf["battery"]["enable_thresholds"] == "true"
    ):
        return

    if os.path.exists(POWER_SUPPLY_DIR):
        batteries = [
            name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith("BAT")
        ]

        for bat in batteries:
            set_battery(get_threshold_value("start"), "start", bat)
            set_battery(get_threshold_value("stop"), "stop", bat)
    else:
        print(f"WARNING {POWER_SUPPLY_DIR} does NOT esixt")


def asus_print_thresholds():
    batteries = [
        name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith("BAT")
    ]
    print(
        "\n-------------------------------- Battery Info ---------------------------------\n"
    )
    print(f"battery count = {len(batteries)}")
    for bat in batteries:
        try:
            primary_start = f"{POWER_SUPPLY_DIR}{bat}/charge_start_threshold"
            primary_stop = f"{POWER_SUPPLY_DIR}{bat}/charge_stop_threshold"

            fallback_start = f"{POWER_SUPPLY_DIR}{bat}/charge_control_start_threshold"
            fallback_stop = f"{POWER_SUPPLY_DIR}{bat}/charge_control_end_threshold"

            if os.path.isfile(primary_start):
                print(bat, "start threshold =", check_output(["cat", primary_start]))
            elif os.path.isfile(fallback_start):
                print(bat, "start threshold =", check_output(["cat", fallback_start]))
            else:
                print(f"{bat} start threshold: file not found")

            if os.path.isfile(primary_stop):
                print(bat, "stop threshold =", check_output(["cat", primary_stop]))
            elif os.path.isfile(fallback_stop):
                print(bat, "stop threshold =", check_output(["cat", fallback_stop]))
            else:
                print(f"{bat} stop threshold: file not found")

        except Exception as e:
            print(f"ERROR: failed to read battery {bat} thresholds:", repr(e))
