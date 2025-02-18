from configparser import ConfigParser
from dataclasses import dataclass
import os
from pathlib import Path
import platform
import re
from subprocess import getoutput
from typing import Tuple, List
import psutil
import distro

from auto_cpufreq.config.config import config
from auto_cpufreq.globals import AVAILABLE_GOVERNORS_SORTED, IS_INSTALLED_WITH_SNAP


@dataclass
class CoreInfo:
    id: int
    usage: float
    temperature: float
    frequency: float


@dataclass
class BatteryInfo:
    is_charging: bool | None
    is_ac_plugged: bool | None
    charging_start_threshold: int | None
    charging_stop_threshold: int | None
    battery_level: int | None
    power_consumption: float | None

    def __repr__(self) -> str:
        if self.is_charging:
            return "charging"
        elif not self.is_ac_plugged:
            return f"discharging {('(' + '{:.2f}'.format(self.power_consumption) + ' W)') if self.power_consumption != None else ''}"
        return "Not Charging"


@dataclass
class SystemReport:
    distro_name: str
    distro_ver: str
    arch: str
    processor_model: str
    total_core: int | None
    kernel_version: str
    current_gov: str | None
    current_epp: str | None
    current_epb: str | None
    cpu_driver: str
    cpu_fan_speed: int | None
    cpu_usage: float
    cpu_max_freq: float | None
    cpu_min_freq: float | None
    load: float
    avg_load: Tuple[float, float, float] | None
    cores_info: list[CoreInfo]
    battery_info: BatteryInfo
    is_turbo_on: bool | None


class SystemInfo:
    """
    Provides system information related to CPU, distribution, and performance metrics.
    """

    def __init__(self):
        self.distro_name: str = (
            distro.name(pretty=True) if not IS_INSTALLED_WITH_SNAP else "UNKNOWN"
        )
        self.distro_version: str = (
            distro.version() if not IS_INSTALLED_WITH_SNAP else "UNKNOWN"
        )
        self.architecture: str = platform.machine()
        self.processor_model: str = (
            getoutput("grep -E 'model name' /proc/cpuinfo -m 1").split(":")[-1].strip()
        )
        self.total_cores: int | None = psutil.cpu_count(logical=True)
        self.cpu_driver: str = getoutput(
            "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver"
        ).strip()
        self.kernel_version: str = platform.release()

    @staticmethod
    def cpu_min_freq() -> float | None:
        freqs = psutil.cpu_freq(percpu=True)
        return min((freq.min for freq in freqs), default=None)

    @staticmethod
    def cpu_max_freq() -> float | None:
        freqs = psutil.cpu_freq(percpu=True)
        return max((freq.max for freq in freqs), default=None)

    @staticmethod
    def get_cpu_info() -> List[CoreInfo]:
        """Returns detailed CPU information for each core."""
        cpu_usage = psutil.cpu_percent(percpu=True)
        cpu_freqs = psutil.cpu_freq(percpu=True)

        try:
            temps = psutil.sensors_temperatures()
            core_temps = [temp.current for temp in temps.get("coretemp", [])]
        except AttributeError:
            core_temps = []

        avg_temp = sum(core_temps) / len(core_temps) if core_temps else 0.0

        return [
            CoreInfo(
                id=i,
                usage=cpu_usage[i],
                temperature=core_temps[i] if i < len(core_temps) else avg_temp,
                frequency=cpu_freqs[i].current,
            )
            for i in range(len(cpu_usage))
        ]

    @staticmethod
    def cpu_fan_speed() -> int | None:
        fans = psutil.sensors_fans()
        return next((fan[0].current for fan in fans.values() if fan), None)

    @staticmethod
    def current_gov() -> str | None:
        try:
            with open(
                "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "r"
            ) as f:
                return f.read().strip()
        except:
            return None

    @staticmethod
    def current_epp() -> str | None:
        epp_path = "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"
        if not Path(epp_path).exists():
            return None
        return config.get_config().get(
            "battery", "energy_performance_preference", fallback="balance_power"
        )

    @staticmethod
    def current_epb() -> str | None:
        epb_path = "/sys/devices/system/cpu/intel_pstate"
        if not Path(epb_path).exists():
            return None
        return config.get_config().get(
            "battery", "energy_perf_bias", fallback="balance_power"
        )

    @staticmethod
    def cpu_usage() -> float:
        return psutil.cpu_percent(
            interval=0.5
        )  # Reduced interval for better responsiveness

    @staticmethod
    def system_load() -> float:
        return os.getloadavg()[0]

    @staticmethod
    def avg_load() -> Tuple[float, float, float]:
        return os.getloadavg()

    @staticmethod
    def avg_temp() -> int:
        temps: List[float] = [i.temperature for i in SystemInfo.get_cpu_info()]
        return int(sum(temps) / len(temps))

    @staticmethod
    def turbo_on() -> bool | None:
        turbo_path = "/sys/devices/system/cpu/intel_pstate/no_turbo"
        if Path(turbo_path).exists():
            with open(turbo_path) as f:
                return f.read().strip() == "0"
        return None

    @staticmethod
    def battery_info() -> BatteryInfo:

        def read_file(path: str) -> str | None:
            try:
                with open(path, "r") as f:
                    return f.read().strip()
            except FileNotFoundError:
                return None

        output = getoutput(
            "upower -i /org/freedesktop/UPower/devices/battery_BAT0", encoding="utf-8"
        )
        state_match: re.Match[str] | None = re.search(r"state:\s+(\w+)", output)
        rate_match: re.Match[str] | None = re.search(
            r"energy-rate:\s+([\d.]+) W", output
        )
        precentage_match: re.Match[str] | None = re.search(
            r"percentage:\s+(\w+)", output
        )

        ac_plugged: bool | None = (
            value == "1"
            if (value := read_file("/sys/class/power_supply/AC/online")) != None
            else None
        )
        is_charging: bool | None = (
            value == "charging"
            if (value := state_match.group(1) if state_match else None) != None
            else None
        )
        chargeing_start_threshold: int | None = (
            int(value)
            if (
                value := read_file(
                    "/sys/class/power_supply/BAT0/charge_start_threshold"
                )
            )
            != None
            else None
        )
        chargeing_stop_threshold: int | None = (
            int(value)
            if (
                value := read_file("/sys/class/power_supply/BAT0/charge_stop_threshold")
            )
            != None
            else None
        )

        return BatteryInfo(
            is_charging=is_charging,  # type: ignore
            is_ac_plugged=ac_plugged,  # type: ignore
            charging_start_threshold=chargeing_start_threshold,
            charging_stop_threshold=chargeing_stop_threshold,
            battery_level=(
                int(precentage_match.group(1)) if precentage_match != None else None
            ),
            power_consumption=(
                float(rate_match.group(1)) if rate_match != None else None
            ),
        )

    @staticmethod
    def turbo_on_suggestion() -> bool:
        usage = SystemInfo.cpu_usage()
        if usage >= 20.0:
            return True
        elif usage <= 25 and SystemInfo.avg_temp() >= 70:
            return False
        return False

    @staticmethod
    def governor_suggestion() -> str:
        if SystemInfo.battery_info().is_ac_plugged:
            return AVAILABLE_GOVERNORS_SORTED[0]
        return AVAILABLE_GOVERNORS_SORTED[-1]

    def generate_system_report(self) -> SystemReport:
        return SystemReport(
            distro_name=self.distro_name,
            distro_ver=self.distro_version,
            arch=self.architecture,
            processor_model=self.processor_model,
            total_core=self.total_cores,
            cpu_driver=self.cpu_driver,
            kernel_version=self.kernel_version,
            current_gov=self.current_gov(),
            current_epp=self.current_epp(),
            current_epb=self.current_epb(),
            cpu_fan_speed=self.cpu_fan_speed(),
            cpu_usage=self.cpu_usage(),
            cpu_max_freq=self.cpu_max_freq(),
            cpu_min_freq=self.cpu_min_freq(),
            load=self.system_load(),
            avg_load=self.avg_load(),
            cores_info=self.get_cpu_info(),
            is_turbo_on=self.turbo_on(),
            battery_info=self.battery_info(),
        )


system_info = SystemInfo()
