"""Import annotated modules on Python 3.9 without reading host telemetry."""

import importlib
import platform
import subprocess
import sys
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def module(module_name, **attributes):
    result = types.ModuleType(module_name)
    for key, value in attributes.items():
        setattr(result, key, value)
    return result


class Python39AnnotationImportTests(unittest.TestCase):
    def test_hardware_modules_import_with_synthetic_host_stubs(self):
        config = types.SimpleNamespace(
            has_config=lambda: False,
            get_config=lambda: None,
            path="",
        )
        psutil = module(
            "psutil",
            cpu_count=lambda logical=True: 1,
            cpu_freq=lambda percpu=True: [],
            cpu_percent=lambda interval=None, percpu=False: [],
            sensors_fans=lambda: {},
            sensors_temperatures=lambda: {},
        )
        distro = module(
            "distro",
            name=lambda pretty=False: "synthetic-linux",
            version=lambda: "0",
        )
        config_module = module("auto_cpufreq.config.config", config=config)
        core_module = module(
            "auto_cpufreq.core",
            get_hwp_dynamic_boost=lambda: None,
            get_power_supply_ignore_list=lambda: [],
        )
        globals_module = module(
            "auto_cpufreq.globals",
            AVAILABLE_GOVERNORS_SORTED=(),
            CPU_TEMP_SENSOR_PRIORITY=(),
            IS_INSTALLED_WITH_SNAP=False,
            POWER_SUPPLY_DIR="synthetic-power-supply",
        )
        urwid = module("urwid")
        command_calls = []

        def synthetic_command(_command):
            command_calls.append("stubbed")
            return "synthetic"

        def forbidden_command(*_args, **_kwargs):
            raise AssertionError("an external command was not stubbed")

        stubs = {
            "distro": distro,
            "psutil": psutil,
            "urwid": urwid,
            "auto_cpufreq.config.config": config_module,
            "auto_cpufreq.core": core_module,
            "auto_cpufreq.globals": globals_module,
        }
        module_names = (
            "auto_cpufreq.modules.platform_profile",
            "auto_cpufreq.modules.system_info",
            "auto_cpufreq.battery_scripts.shared",
            "auto_cpufreq.battery_scripts.ideapad_laptop",
            "auto_cpufreq.modules.system_monitor",
        )

        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, stubs))
            stack.enter_context(
                patch.object(
                    subprocess,
                    "getoutput",
                    side_effect=synthetic_command,
                )
            )
            for function in ("run", "call", "Popen"):
                stack.enter_context(
                    patch.object(
                        subprocess,
                        function,
                        side_effect=forbidden_command,
                    )
                )
            stack.enter_context(
                patch.object(
                    platform,
                    "machine",
                    return_value="synthetic-arch",
                )
            )
            stack.enter_context(
                patch.object(
                    platform,
                    "release",
                    return_value="synthetic-kernel",
                )
            )

            imported = {
                name: importlib.import_module(name)
                for name in module_names
            }

        self.assertEqual(len(command_calls), 2)
        self.assertEqual(
            imported["auto_cpufreq.modules.system_info"].system_info.processor_model,
            "synthetic",
        )


if __name__ == "__main__":
    unittest.main()
