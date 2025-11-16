#!/usr/bin/env python3
import os

from auto_cpufreq.battery_scripts.shared import BatteryDevice
from auto_cpufreq.config.config import config
from auto_cpufreq.globals import POWER_SUPPLY_DIR


class AsusBatteryDevice(BatteryDevice):
    def __init__(self):
        super().__init__()
        self.start_paths = {
            bat: [
                os.path.join(POWER_SUPPLY_DIR, bat, "charge_start_threshold"),
                os.path.join(
                    POWER_SUPPLY_DIR, bat, "charge_control_start_threshold"
                ),  # Fallback
            ]
            for bat in self.batteries
        }
        self.stop_paths = {
            bat: [
                os.path.join(POWER_SUPPLY_DIR, bat, "charge_stop_threshold"),
                os.path.join(
                    POWER_SUPPLY_DIR, bat, "charge_control_end_threshold"
                ),  # Fallback
            ]
            for bat in self.batteries
        }
