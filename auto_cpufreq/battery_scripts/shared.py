#!/usr/bin/env python3
import os
from subprocess import check_output, CalledProcessError
import time

from auto_cpufreq.config.config import config
from auto_cpufreq.globals import POWER_SUPPLY_DIR


class BatteryDevice:
    def __init__(self):
        self.config = config.get_config()
        if os.path.isdir(POWER_SUPPLY_DIR):
            self.batteries = [
                name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith("BAT")
            ]
        else:
            print(f"WARNING: POWER_SUPPLY_DIR '{POWER_SUPPLY_DIR}' does not exist.")
            self.batteries = []
        self.start_paths = {
            bat: [os.path.join(POWER_SUPPLY_DIR, bat, "charge_start_threshold")]
            for bat in self.batteries
        }
        self.stop_paths = {
            bat: [os.path.join(POWER_SUPPLY_DIR, bat, "charge_stop_threshold")]
            for bat in self.batteries
        }

        self.start_config_value = self.get_threshold_config_value("start")
        self.stop_config_value = self.get_threshold_config_value("stop")

    def get_threshold_config_value(self, mode):
        return (
            self.config["battery"][f"{mode}_threshold"]
            if self.config.has_option("battery", f"{mode}_threshold")
            else None
        )

    def is_config_values_valid(self) -> bool:
        if (self.start_config_value is None or self.stop_config_value is None):
            print(f'WARNING: Charge both start AND stop value need to be configured for battery thresholding to work')
            return False
        elif not (0 <= self.start_config_value <= 100):
            print(f'WARNING: Charge start value "{self.start_config_value}" is invalid')
            return False
        elif not (0 <= self.stop_config_value <= 100):
            print(f'WARNING: Charge stop value "{self.stop_config_value}" is invalid')
            return False
        elif self.start_config_value > self.stop_config_value:
            print(
                f'WARNING: Charge start value "{self.start_config_value}" is higher than the stop value "{self.stop_config_value}"!'
            )
            return False
        else:
            return True

    def get_battery_paths(self, bat, mode):
        paths = None
        if mode == "start":
            paths = self.start_paths[bat]
        else:
            paths = self.stop_paths[bat]
        return paths

    def set_battery(self, bat, mode, value) -> bool:
        """
        Return true/false depending on if command is executed and fails (or succeeds)
        """
        paths = self.get_battery_paths(bat, mode)

        for p in paths:
            if os.path.isfile(p):
                try:
                    check_output(f"echo {value} | tee {p}", shell=True, text=True)
                    return True
                except CalledProcessError as e:
                    print(
                        f"WARNING: Could not write battery threshold {value} to {p}: {e.output}"
                    )
                    return False
            else:
                print(f"WARNING: {p} does NOT exist")
        return True

    def get_current_threshold(self, bat, mode):
        paths = self.get_battery_paths(bat, mode)
        for p in paths:
            if os.path.isfile(p):
                try:
                    return check_output(
                        ["cat", POWER_SUPPLY_DIR + bat + f"/charge_{mode}_threshold"]
                    )
                except CalledProcessError as e:
                    print(
                        f"ERROR: failed to read battery {bat} {mode} threshold in file: {p}: {e.output}"
                    )
        raise OSError(f"ERROR: failed to get any battery threshold for {bat}, {mode}!")

    def print_thresholds(self):
        print(
            "\n-------------------------------- Battery Info ---------------------------------\n"
        )
        print(f"battery count = {len(self.batteries)}")
        for bat in self.batteries:
            try:
                print(
                    bat, "start threshold =", self.get_current_threshold(bat, "start")
                )
                print(bat, "stop threshold =", self.get_current_threshold(bat, "stop"))
            except Exception as e:
                print(f"ERROR: failed to read battery {bat} thresholds:", repr(e))

    def setup(self):
        if not (
            self.config.has_option("battery", "enable_thresholds")
            and self.config["battery"]["enable_thresholds"] == "true"
        ):
            return
        elif not os.path.exists(POWER_SUPPLY_DIR):
            print(f"WARNING: {POWER_SUPPLY_DIR} does NOT exist")
            return
        elif not self.is_config_values_valid():
            return

        batteries = [
            name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith("BAT")
        ]

        for bat in batteries:
            # First set 0 for start and 100 for stop, sometimes we can have conflicting values otherwise which will result in an 'invalid argument' upon writing.
            self.set_battery(bat, "start", 0)
            self.set_battery(bat, "stop", 100)
            time.sleep(0.1)
            self.set_battery(bat, "start", self.start_config_value)
            self.set_battery(bat, "stop", self.stop_config_value)
