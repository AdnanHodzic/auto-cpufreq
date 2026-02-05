#!/usr/bin/env python3

from typing import Any
from auto_cpufreq.battery_scripts.shared import BatteryDevice

CONSERVATION_MODE_FILE = "/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"

class IdeapadBatteryDevice(BatteryDevice):
    def is_conservation_mode(self) -> bool:
        val = self._read_value_from_file(CONSERVATION_MODE_FILE)
        if val not in ("0", "1"):
            print(
                f"WARNING: could not get value from conservation mode, unexpected value!: {val}"
            )
            return False
        return val == "1"

    def set_conservation_mode(self, value: int) -> bool:
        if not self._write_value_to_file(CONSERVATION_MODE_FILE, value):
            print("WARNING: unable to set conservation mode")
            return False
        return True

    def apply_threshold_settings_to_bat(self, bat: str, config: dict[str, Any]):
        if config["ideapad_conservation_mode"]:
            print("DEBUG: ideapad conservation mode enabled")
            return self.set_conservation_mode(1)
        else:
            print("DEBUG: ideapad conservation mode disabled")
            return self.set_conservation_mode(0)

    def print_battery_info(self, bat: str):
        if self.is_conservation_mode():
            print(f"{bat} conservation mode is on")
        else:
            print(f"{bat} conservation mode is off")
