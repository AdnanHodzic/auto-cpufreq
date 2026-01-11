#!/usr/bin/env python3
import os
from subprocess import CalledProcessError, check_output
import time

from auto_cpufreq.battery_scripts.shared import BatteryDevice
from auto_cpufreq.globals import CONSERVATION_MODE_FILE, POWER_SUPPLY_DIR


class IdeapadBatteryDevice(BatteryDevice):
    def check_conservation_mode(self):
        try:
            value = check_output(["cat", CONSERVATION_MODE_FILE], text=True).rstrip()
            if value == "1":
                return True
            elif value == "0":
                return False
            else:
                print(
                    f"WARNING: could not get value from conservation mode, unexpected value!: {value}"
                )
                return None
        except CalledProcessError as e:
            print(f"WARNING: could not get value from conservation mode: {e.output}")
            return False

    def set_conservation_mode(self, value):
        try:
            check_output(
                f"echo {value} | tee {CONSERVATION_MODE_FILE}", shell=True, text=True
            )
            print(f"conservation_mode is {value}")
        except CalledProcessError as e:
            print(f"WARNING: unable to set conservation mode: {e.output}")
        return

    def setup(self):
        if not (
            self.config.has_option("battery", "enable_thresholds")
            and self.config["battery"]["enable_thresholds"] == "true"
        ):
            print("DEBUG: battery thresholding disabled")
            return

        if self.config.has_option("battery", "ideapad_laptop_conservation_mode"):
            if self.config["battery"]["ideapad_laptop_conservation_mode"] == "true":
                self.conservation_mode(1)
                print("DEBUG: ideapad conversation mode = true, stopping")
                return
            if self.config["battery"]["ideapad_laptop_conservation_mode"] == "false":
                self.conservation_mode(0)

        if self.check_conservation_mode():
            print("WARNING: conservation mode is enabled unable to set thresholds")
            return
        elif not os.path.exists(POWER_SUPPLY_DIR):
            print(f"WARNING: {POWER_SUPPLY_DIR} does NOT exist")
            return
        elif not self.is_config_values_valid():
            print("DEBUG: config is not valid")
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

    def print_thresholds(self):
        if self.check_conservation_mode():
            print("WARNING: conservation mode is on")
            return
        super().print_thresholds()
