#!/usr/bin/env python3

import os
from pathlib import Path
from typing import Any
from auto_cpufreq.battery_scripts.shared import BatteryDevice

class IdeapadBatteryDevice(BatteryDevice):
    # Support for most lenovo ideapad/legion/thinkpad conservation mode file.
    # The function finds the conservation_mode file in common paths.
    # This is mandatory because ideapad and legion handle different paths
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conservation_mode_path = self._find_conservation_mode_path()

    def _find_conservation_mode_path(self) -> str | None:
        search_paths = [
            "/sys/bus/platform/drivers/ideapad_acpi",
            "/sys/devices/platform/ideapad_acpi"
        ]
        
        for base in search_paths:
            base_path = Path(base)
            if not base_path.exists():
                continue
                
            direct_file = base_path / "conservation_mode"
            if direct_file.exists():
                return str(direct_file)
            
            try:
                for match in base_path.glob("*/conservation_mode"):
                    if match.exists():
                        return str(match)
            except PermissionError:
                continue
                
        return None

    def is_conservation_mode(self) -> bool:
        if not self.conservation_mode_path:
            return False
            
        val = self._read_value_from_file(self.conservation_mode_path)
        if val not in ("0", "1"):
            if val is not None:
                print(f"WARNING: unexpected value from conservation mode: {val}")
            return False
        return val == "1"

    def set_conservation_mode(self, value: int) -> bool:
        if not self.conservation_mode_path:
            print("ERROR: conservation_mode file path not found")
            return False
            
        if not self._write_value_to_file(self.conservation_mode_path, value):
            print(f"WARNING: unable to set conservation mode at {self.conservation_mode_path}")
            return False
        return True

    def _parse_threshold_values(
        self, start: None | str, stop: None | str
    ) -> tuple[int, int]:
        # Ideapad laptops don't use start/stop thresholds.
        # They only use conservation mode, which is either on or off. So we return dummy values here.
        return 0, 100

    def _parse_ideapad_conservation_mode(self, param: None | str) -> None | bool:
        if param is None:
            return None
        param = str(param).lower().strip()
        if param == "true":
            return True
        elif param == "false":
            return False
        else:
            raise ValueError(f"Invalid value for ideapad_conservation_mode: {param}")

    def apply_threshold_settings_to_bat(self, bat: str, config: dict[str, Any]):
        mode = config.get("ideapad_conservation_mode")
        if mode is None:
            # If conservation mode is not explicitly set, we don't change it
            return True
        return self.set_conservation_mode(1 if mode else 0)

    def print_battery_info(self, bat: str):
        if not self.conservation_mode_path:
            print(f"{bat}: conservation mode not supported (file not found)")
            return

        if self.is_conservation_mode():
            print(f"{bat} conservation mode is on")
        else:
            print(f"{bat} conservation mode is off")