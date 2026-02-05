#!/usr/bin/env python3
import os
import time
from typing import Any

from auto_cpufreq.config.config import config
from auto_cpufreq.globals import POWER_SUPPLY_DIR

# The charge_control_{start,end}_threshold files
# are officially documented and preferred,
# but some models or older kernels may only have charge_{start,stop}_threshold files
CHARGE_START_THRESHOLD_FILES = [
    "charge_control_start_threshold",
    "charge_start_threshold",
]
CHARGE_STOP_THRESHOLD_FILES = [
    "charge_control_end_threshold",
    "charge_stop_threshold",
]


class BatteryDevice:
    def __init__(self):
        self.batteries = self._get_batteries()
        self.start_paths = {
            bat: path
            for bat in self.batteries
            if (path := self._choose_threshold_file(bat, CHARGE_START_THRESHOLD_FILES))
            is not None
        }
        self.stop_paths = {
            bat: path
            for bat in self.batteries
            if (path := self._choose_threshold_file(bat, CHARGE_STOP_THRESHOLD_FILES))
            is not None
        }

    def _get_batteries(self) -> list[str]:
        """
        Get list of battery names from POWER_SUPPLY_DIR
        Return list of battery names (e.g., ['BAT0', 'BAT1'])
        """
        if not os.path.isdir(POWER_SUPPLY_DIR):
            print(f"WARNING: {POWER_SUPPLY_DIR} does NOT exist")
            return []
        return [name for name in os.listdir(POWER_SUPPLY_DIR) if name.startswith("BAT")]

    def _choose_threshold_file(self, bat: str, files: list[str]) -> str | None:
        """
        Get the charge threshold file path for given battery
        Return the first found file path from files list, or None if not found
        """

        for filename in files:
            path = os.path.join(POWER_SUPPLY_DIR, bat, filename)
            # File must exist and be writable
            if os.path.isfile(path) and os.access(path, os.W_OK):
                return path
        return None

    def _get_config(self) -> dict[str, str]:
        conf = config.get_config()
        return dict(conf.items("battery"))

    def get_parsed_config(self) -> dict[str, int | bool]:
        """
        Parse battery configuration from config file
        Return validated and parsed config as dictionary
        If invalid, thresholds_enabled will always be False
        So see valid values and more info about different devices,
        the TLP documentation is a good reference:
        https://linrunner.de/tlp/settings/bc-vendors.html
        """
        config = self._get_config()

        parsed_config = {
            "thresholds_enabled": False,
            "start_threshold": 99,
            "stop_threshold": 100,
            "ideapad_conservation_mode": False,
        }

        if config.get("enable_thresholds") != "true":
            print("DEBUG: battery thresholding disabled")
            # Return early without further validation
            return parsed_config

        try:
            start_val, stop_val = self._parse_threshold_values(
                config.get("start_threshold"), config.get("stop_threshold")
            )
            parsed_config["start_threshold"] = start_val
            parsed_config["stop_threshold"] = stop_val

            parsed_config["ideapad_conservation_mode"] = (
                self._parse_ideapad_conservation_mode(
                    "ideapad_laptop_conservation_mode"
                )
            )

            parsed_config["thresholds_enabled"] = True
        except ValueError as e:
            # Thresholds will not be enabled if config is invalid
            print(f"ERROR: {e}")
        return parsed_config

    def _parse_threshold_values(
        self, start: None | str, stop: None | str
    ) -> tuple[int, int]:
        """
        Parse and validate start and stop threshold values
        This method should is overridden in subclasses if needed
        Return tuple of (start, stop) as integers if valid
        Raise ValueError if invalid
        """
        if start is None or stop is None:
            raise ValueError("Start and stop thresholds must be set")
        if not start.isdigit() or not stop.isdigit():
            raise ValueError("Start and stop thresholds must be integers")
        start_val = int(start)
        stop_val = int(stop)
        if not (0 <= start_val <= 99):
            raise ValueError("Start threshold must be between 0 and 99")
        if not (1 <= stop_val <= 100):
            raise ValueError("Stop threshold must be between 1 and 100")
        if start_val >= stop_val:
            raise ValueError("Start threshold must be less than stop threshold")
        return start_val, stop_val

    def _parse_ideapad_conservation_mode(self, _: None | str) -> bool:
        """
        Parse ideapad conservation mode value from config
        This method is overridden in IdeapadBatteryDevice subclass
        """
        return False

    def set_battery_thresholds(self, bat, start: int, stop: int) -> bool:
        """
        Set battery thresholds for given battery
        Return true/false depending on if command is executed and fails (or succeeds)
        """

        if bat not in self.start_paths or bat not in self.stop_paths:
            print(f"WARNING: battery {bat} has no threshold attributes")
            return False

        # First set stop to 100 to avoid potential 'invalid argument'
        # errors when start >= stop
        self._write_value_to_file(self.stop_paths[bat], 100)
        time.sleep(0.1)

        if not self._write_value_to_file(self.start_paths[bat], start):
            return False
        if not self._write_value_to_file(self.stop_paths[bat], stop):
            return False

        return True

    def _write_value_to_file(self, path: str, value: str | int) -> bool:
        try:
            with open(path, "w") as f:
                f.write(str(value))
            return True
        except Exception as e:
            print(f"ERROR: Could not write value {value} to {path}: {e}")
            return False

    def _read_value_from_file(self, path: str, default: str = "") -> str:
        try:
            with open(path, "r") as f:
                output = f.read()
            return output.strip()
        except Exception as e:
            print(f"ERROR: Could not read value from {path}: {e}")
            return default

    def get_current_threshold(self, bat: str) -> tuple[int | None, int | None]:

        if bat not in self.start_paths or bat not in self.stop_paths:
            print(f"WARNING: battery {bat} has no threshold attributes")
            return None, None

        start = self._read_value_from_file(self.start_paths[bat])
        stop = self._read_value_from_file(self.stop_paths[bat])
        start = int(start) if start.isdigit() else None
        stop = int(stop) if stop.isdigit() else None
        return start, stop

    def print_thresholds(self):
        print(
            "\n-------------------------------- Battery Info ---------------------------------\n"
        )
        print(f"battery count = {len(self.batteries)}")
        for bat in self.batteries:
            self.print_battery_info(bat)

    def print_battery_info(self, bat: str):
        start_value, stop_value = self.get_current_threshold(bat)
        if start_value is None or stop_value is None:
            print(f"ERROR: failed to read battery {bat} thresholds")
        else:
            print(f"{bat} start threshold = {start_value}")
            print(f"{bat} stop threshold = {stop_value}")

    def apply_threshold_settings_to_bat(self, bat: str, config: dict[str, Any]):
        print(
            f"DEBUG: applying battery settings to: {bat}, "
            f'Start={config["start_threshold"]}, '
            f'Stop={config["stop_threshold"]}'
        )
        return self.set_battery_thresholds(
            bat,
            config["start_threshold"],
            config["stop_threshold"],
        )

    def setup(self):
        parsed_config = self.get_parsed_config()
        if not parsed_config["thresholds_enabled"]:
            return
        if not self.batteries:
            print("WARNING: no batteries found to set thresholds for")
            return

        print("DEBUG: applying battery settings")
        for bat in self.batteries:
            if not self.apply_threshold_settings_to_bat(bat, parsed_config):
                print(f"ERROR: failed to set thresholds for battery {bat}")
