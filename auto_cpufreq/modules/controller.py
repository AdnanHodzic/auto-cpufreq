from configparser import ConfigParser
import logging
import os
from pathlib import Path
from pickle import dump
from subprocess import getoutput, run
from typing import Any, Literal
from auto_cpufreq.config.config import config
from auto_cpufreq.globals import (
    AVAILABLE_GOVERNORS_SORTED,
    CPU_FREQ_MAX_LIMIT,
    CPU_FREQ_MIN_LIMIT,
)
from auto_cpufreq.modules.system_info import SystemInfo
from auto_cpufreq.tools import get_gov_override_path
from auto_cpufreq.types import GovernorOverrideOptions


class SystemController:
    """
    Controls various aspects of the CPU and system power management.

    This class provides static methods to control CPU turbo state, governor settings,
    CPU frequencies, platform profiles, and energy performance bias. These methods
    are used to optimize system performance and power usage based on current conditions.
    """

    @staticmethod
    def set_turbo(on: bool) -> bool:
        """
        Enables or disables CPU turbo boost.

        Detects the appropriate CPU turbo control mechanism for the system
        (Intel p-state, generic cpufreq boost, or AMD p-state) and sets
        the turbo state accordingly.

        :param on: True to enable turbo, False to disable it
        :return: True if successful, False otherwise
        """
        if SystemInfo.turbo_on()[0] == on:
            return True
        p_state = Path("/sys/devices/system/cpu/intel_pstate/no_turbo")
        cpufreq = Path("/sys/devices/system/cpu/cpufreq/boost")
        amd_pstate = Path("/sys/devices/system/cpu/amd_pstate/status")

        if p_state.exists():
            inverse = True
            f: Path = p_state
        elif cpufreq.exists():
            f = cpufreq
            inverse = False
        elif amd_pstate.exists():
            amd_value = amd_pstate.read_text().strip()
            if amd_value == "active":
                logging.warning(
                    "Can't set CPU turbo. it's controlled by amd-pstate-epp driver"
                )
            # Basically, no other value should exist.
            return False
        else:
            logging.warning("CPU turbo is not available")
            return False

        try:
            f.write_text(f"{int(on ^ inverse)}\n")
        except PermissionError:
            logging.warning("Changing CPU turbo is not supported. Skipping.")
            return False
        except Exception as e:
            logging.error("failed to set CPU turbo: %s", e)
            return False
        return True

    @staticmethod
    def set_gov_override(option: GovernorOverrideOptions) -> bool:
        """
        Sets or resets the governor override option.

        This method allows manually overriding the automatic governor selection
        with a specific governor (powersave or performance) or removing the override.

        :param option: The governor override option to set
        :return: True if successful, False otherwise
        """
        try:
            path: Path = get_gov_override_path()
            if option in [
                GovernorOverrideOptions.POWERSAVE,
                GovernorOverrideOptions.PERFORMANCE,
            ]:
                with open(path, "wb") as store:
                    dump(option.value, store)
                return True
            elif option == GovernorOverrideOptions.RESET:
                if os.path.isfile(path):
                    os.remove(path)
                return True
            return False
        except Exception as e:
            logging.error(
                "failed to override governor with option (%s): %s", option.value, e
            )
            return False

    @staticmethod
    def set_frequencies() -> bool:
        """
        Sets CPU minimum and maximum frequencies based on power supply status.

        If options are defined in auto-cpufreq.conf, those values are used.
        Otherwise, default frequencies are set based on the current power state.

        :return: True if successful, False otherwise
        """
        power_supply: Literal["charger"] | Literal["battery"] = (
            "charger" if SystemInfo.battery_info().is_ac_plugged else "battery"
        )

        frequency: dict[str, dict[str, Any]] = {
            "scaling_max_freq": {
                "cmdargs": "--frequency-max",
                "minmax": "maximum",
                "value": None,
            },
            "scaling_min_freq": {
                "cmdargs": "--frequency-min",
                "minmax": "minimum",
                "value": None,
            },
        }

        if CPU_FREQ_MIN_LIMIT is None or CPU_FREQ_MAX_LIMIT is None:
            logging.error("can't set frequency, limit is unknown")
            return False

        conf: ConfigParser = config.get_config()

        for freq_type in frequency.keys():
            try:
                value: int | None = None
                if not conf.has_option(power_supply, freq_type):
                    # fetch and use default frequencies
                    if freq_type == "scaling_max_freq":
                        curr_freq = int(
                            getoutput(f"cpufreqctl.auto-cpufreq --frequency-max")
                        )
                        value = CPU_FREQ_MAX_LIMIT
                    else:
                        curr_freq = int(
                            getoutput(f"cpufreqctl.auto-cpufreq --frequency-min")
                        )
                        value = CPU_FREQ_MIN_LIMIT
                    if curr_freq == value:
                        continue

                try:
                    frequency[freq_type]["value"] = (
                        value if value else int(conf[power_supply][freq_type].strip())
                    )
                except ValueError:
                    logging.error(
                        "Invalid value for '%s': %s",
                        freq_type,
                        conf[power_supply][freq_type],
                    )
                    return False

                if (
                    not CPU_FREQ_MIN_LIMIT
                    <= frequency[freq_type]["value"]
                    <= CPU_FREQ_MAX_LIMIT
                ):
                    logging.error(
                        "Given value for '%s' is not within the allowed frequencies %s-%s kHz",
                        freq_type,
                        CPU_FREQ_MIN_LIMIT,
                        CPU_FREQ_MAX_LIMIT,
                    )
                    return False

                # set the frequency
                run(
                    f"cpufreqctl.auto-cpufreq {frequency[freq_type]['cmdargs']} --set={frequency[freq_type]['value']}",
                    shell=True,
                )
                return True
            except Exception as e:
                logging.error("Error setting %s: %s", freq_type, e)
        return True

    @staticmethod
    def set_platform_profile(conf, profile) -> bool:
        """
        Sets the platform power profile based on configuration.

        Platform profiles control system-wide power/performance behavior on supported
        systems (typically laptops). The profile is set according to the power supply state
        (battery/charger) if the option is configured.

        :param conf: Configuration object containing platform profile settings
        :param profile: The power profile to use ('battery' or 'charger')
        :return: True if successful, False if not supported or an error occurred
        """
        if conf.has_option(profile, "platform_profile"):
            platform_profile_path = Path("/sys/firmware/acpi/platform_profile")
            if not platform_profile_path.exists():
                return False
            else:
                try:
                    pp: str = conf[profile]["platform_profile"]
                    run(f"cpufreqctl.auto-cpufreq --pp --set={pp}", shell=True)
                    return True
                except Exception as e:
                    logging.error("Failed to set platform profile: %s", e)
                    return False
        return False

    @staticmethod
    def set_energy_perf_bias(conf, profile) -> bool:
        """
        Sets the energy performance bias for Intel CPUs.

        This controls the trade-off between energy efficiency and performance.
        On battery, it defaults to 'balance_power'.
        On AC power, it defaults to 'balance_performance'.
        These defaults can be overridden in the configuration.

        :param conf: Configuration object containing energy performance bias settings
        :param profile: The power profile to use ('battery' or 'charger')
        :return: True if successful, False if not supported or an error occurred
        """
        intel_pstate_path = Path("/sys/devices/system/cpu/intel_pstate")
        if not intel_pstate_path.exists():
            return False

        try:
            epb: Literal["balance_performance"] | Literal["balance_power"] = (
                "balance_performance" if profile == "charger" else "balance_power"
            )
            if conf.has_option(profile, "energy_perf_bias"):
                epb = conf[profile]["energy_perf_bias"]

            run(f"cpufreqctl.auto-cpufreq --epb --set={epb}", shell=True)
            return True
        except Exception as e:
            logging.error("Failed to set energy performance bias: %s", e)
            return False

    @staticmethod
    def set_powersave_gov(override: bool = False) -> bool:
        """
        Sets the CPU governor to power-saving mode.

        Uses the governor specified in the configuration for battery mode,
        or falls back to the most power-efficient governor available on the system.
        Does nothing if the governor has been manually overridden.

        :return: True if successful, False otherwise
        """
        try:
            conf: ConfigParser = config.get_config()
            gov: str = (
                conf["battery"]["governor"]
                if conf.has_option("battery", "governor")
                else AVAILABLE_GOVERNORS_SORTED[-1]
            )

            if SystemInfo.gov_override() != "default" and not override:  # type: ignore
                logging.warning(
                    "setting powersave skipped, Governor overwritten using `--force` flag."
                )
                return False

            run(f"cpufreqctl.auto-cpufreq --governor --set={gov}", shell=True)
            return True
        except Exception as e:
            logging.error("setting powersave governor failed: %s", e)
            return False

    @staticmethod
    def set_performance_gov(override: bool = False) -> bool:
        """
        Sets the CPU governor to performance mode.

        Uses the governor specified in the configuration for charger mode,
        or falls back to the highest-performance governor available on the system.
        Does nothing if the governor has been manually overridden.

        :return: True if successful, False otherwise
        """
        try:
            conf: ConfigParser = config.get_config()
            gov: str = (
                conf["battery"]["governor"]
                if conf.has_option("battery", "governor")
                else AVAILABLE_GOVERNORS_SORTED[0]
            )

            if SystemInfo.gov_override() != "default" and not override:  # type: ignore
                logging.warning(
                    "setting performance skipped, Governor overwritten using `--force` flag."
                )
                return False

            run(f"cpufreqctl.auto-cpufreq --governor --set={gov}", shell=True)
            return True
        except Exception as e:
            logging.error("setting powersave governor failed: %s", e)
            return False
