from dataclasses import dataclass
import os
from pathlib import Path
import platform
from subprocess import getoutput
from typing import Tuple, List
import psutil
import distro
from pathlib import Path
from auto_cpufreq.config.config import config
from auto_cpufreq.core import get_power_supply_ignore_list
from auto_cpufreq.globals import (
    AVAILABLE_GOVERNORS_SORTED,
    CPU_TEMP_SENSOR_PRIORITY,
    IS_INSTALLED_WITH_SNAP,
    POWER_SUPPLY_DIR,
)
from typing import Optional


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
    is_turbo_on: Tuple[bool | None, bool | None]


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
            temp_sensor = []
            for sensor in CPU_TEMP_SENSOR_PRIORITY:
                temp_sensor = temps.get(sensor, [])
                if temp_sensor != []:
                    break

            core_temps = [temp.current for temp in temp_sensor]
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
    def current_epp(is_ac_plugged: bool) -> str | None:
        epp_path = "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"
        if not Path(epp_path).exists():
            return None
            
        return config.get_config().get( 
            "charger" if is_ac_plugged else "battery", "energy_performance_preference", fallback="balance_power"
        )

    @staticmethod
    def current_epb(is_ac_plugged: bool) -> str | None:
        epb_path = "/sys/devices/system/cpu/intel_pstate"
        if not Path(epb_path).exists():
            return None

        return config.get_config().get(
            "charger" if is_ac_plugged else "battery", "energy_perf_bias", fallback="balance_power"
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
    def turbo_on() -> Tuple[bool | None, bool | None]:
        """Get CPU turbo mode status.

        Returns: Tuple[bool | None, bool | None]:

        The first value indicates whether turbo mode is enabled, None if unknown

        The second value indicates whether auto mode is enabled (amd_pstate only), None if unknown
        """
        intel_pstate = Path("/sys/devices/system/cpu/intel_pstate/no_turbo")
        cpu_freq = Path("/sys/devices/system/cpu/cpufreq/boost")
        amd_pstate = Path("/sys/devices/system/cpu/amd_pstate/status")

        if intel_pstate.exists():
            control_file: Path = intel_pstate
            inverse_logic = True
        elif cpu_freq.exists():
            control_file = cpu_freq
            inverse_logic = False
        elif amd_pstate.exists():
            amd_status: str = amd_pstate.read_text().strip()
            if amd_status == "active":
                return None, True
            return None, False
        else:
            return None, None

        try:
            current_value = int(control_file.read_text().strip())
            return bool(current_value) ^ inverse_logic, False
        except Exception as e:
            return None, None

    @staticmethod
    def read_file(path: str) -> Optional[str]:

        try:
            with open(path, "r") as f:
                return f.read().strip()
        except (FileNotFoundError, OSError):
            return None

    @staticmethod
    def get_battery_path() -> Optional[str]:

        # Check if user has specified a custom battery device in config
        if config.has_config():
            conf = config.get_config()
            if conf.has_option("battery", "battery_device"):
                battery_device = conf.get("battery", "battery_device").strip()
                if battery_device:
                    custom_path = os.path.join(POWER_SUPPLY_DIR, battery_device)
                    type_path = os.path.join(custom_path, "type")
                    # Validate that the specified device exists and is a battery
                    if os.path.isfile(type_path):
                        content = SystemInfo.read_file(type_path)
                        if content and content.lower() == "battery":
                            return custom_path

        # Fall back to auto-detection if no custom device specified or if it's invalid
        try:
            for entry in os.listdir(POWER_SUPPLY_DIR):
                path = os.path.join(POWER_SUPPLY_DIR, entry)
                type_path = os.path.join(path, "type")
                if os.path.isfile(type_path):
                    content = SystemInfo.read_file(type_path)
                    if content and content.lower() == "battery":
                        return path
        except Exception:
            return None
        return None

    @staticmethod
    def battery_info() -> BatteryInfo:

        battery_path = SystemInfo.get_battery_path()

        # By default, AC is considered connected if no battery is detected
        is_ac_plugged = True
        is_charging = None
        battery_level = None
        power_consumption = None
        charging_start_threshold = None
        charging_stop_threshold = None

        if not battery_path:

            # No battery detected
            return BatteryInfo(
                is_charging=None,
                is_ac_plugged=is_ac_plugged,
                charging_start_threshold=None,
                charging_stop_threshold=None,
                battery_level=None,
                power_consumption=None,
            )

        # Reading AC info (Hands)
        for supply in os.listdir(POWER_SUPPLY_DIR):
            supply_path = os.path.join(POWER_SUPPLY_DIR, supply)
            supply_type = SystemInfo.read_file(os.path.join(supply_path, "type"))
            if supply_type == "Mains":
                online = SystemInfo.read_file(os.path.join(supply_path, "online"))
                is_ac_plugged = online == "1"

        # Reading battery information
        battery_status = SystemInfo.read_file(os.path.join(battery_path, "status"))
        battery_capacity = SystemInfo.read_file(os.path.join(battery_path, "capacity"))

        # first check for wattage in power_now
        # this is not found on all laptops
        energy_rate = (
            SystemInfo.read_file(os.path.join(battery_path, "power_now"))
        )

        # if power_now wasn't found, try calculating wattage using current and voltage
        if energy_rate is None:
            current = SystemInfo.read_file(os.path.join(battery_path, "current_now"))
            voltage = SystemInfo.read_file(os.path.join(battery_path, "voltage_now"))

            if (current and current.isdigit()) and (voltage and voltage.isdigit()):
                energy_rate = (int(current) * int(voltage)) / 1_000_000
 


        charge_start_threshold = (
            SystemInfo.read_file(os.path.join(battery_path, "charge_start_threshold"))
            or SystemInfo.read_file(os.path.join(battery_path, "charge_control_start_threshold"))
        )
        charge_stop_threshold = (
            SystemInfo.read_file(os.path.join(battery_path, "charge_stop_threshold"))
            or SystemInfo.read_file(os.path.join(battery_path, "charge_control_end_threshold"))
        )
        is_charging = battery_status.lower() == "charging" if battery_status else None
        battery_level = int(battery_capacity) if battery_capacity and battery_capacity.isdigit() else None
        power_consumption = float(energy_rate) / 1_000_000 if energy_rate \
            and str(energy_rate).replace('.', '', 1).isdigit() else None
        charging_start_threshold = int(charge_start_threshold) if charge_start_threshold \
            and charge_start_threshold.isdigit() else None
        charging_stop_threshold = int(charge_stop_threshold) if charge_stop_threshold \
            and charge_stop_threshold.isdigit() else None

        return BatteryInfo(
            is_charging=is_charging,
            is_ac_plugged=is_ac_plugged,
            charging_start_threshold=charging_start_threshold,
            charging_stop_threshold=charging_stop_threshold,
            battery_level=battery_level,
            power_consumption=power_consumption,
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
        battery_info = self.battery_info()

        return SystemReport(
            distro_name=self.distro_name,
            distro_ver=self.distro_version,
            arch=self.architecture,
            processor_model=self.processor_model,
            total_core=self.total_cores,
            cpu_driver=self.cpu_driver,
            kernel_version=self.kernel_version,
            current_gov=self.current_gov(),
            current_epp=self.current_epp(battery_info.is_ac_plugged),
            current_epb=self.current_epb(battery_info.is_ac_plugged),
            cpu_fan_speed=self.cpu_fan_speed(),
            cpu_usage=self.cpu_usage(),
            cpu_max_freq=self.cpu_max_freq(),
            cpu_min_freq=self.cpu_min_freq(),
            load=self.system_load(),
            avg_load=self.avg_load(),
            cores_info=self.get_cpu_info(),
            is_turbo_on=self.turbo_on(),
            battery_info=battery_info,
        )


system_info = SystemInfo()
