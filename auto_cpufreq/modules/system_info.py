from dataclasses import dataclass
import os
from pathlib import Path
import platform
from subprocess import getoutput
from typing import List, Optional, Tuple

import distro
import psutil

from auto_cpufreq.config.config import config
from auto_cpufreq.core import (
    get_hwp_dynamic_boost,
    get_power_supply_ignore_list,
)
from auto_cpufreq.globals import (
    AVAILABLE_GOVERNORS_SORTED,
    CPU_TEMP_SENSOR_PRIORITY,
    IS_INSTALLED_WITH_SNAP,
    POWER_SUPPLY_DIR,
)


CPU_SYSFS_ROOT = Path("/sys/devices/system/cpu")
SNAP_HOST_ROOT = "/var/lib/snapd/hostfs"


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
        if self.is_ac_plugged is False:
            return f"discharging {('(' + '{:.2f}'.format(self.power_consumption) + ' W)') if self.power_consumption != None else ''}"
        if self.is_ac_plugged is None:
            return "Unknown"
        return "Not Charging"


@dataclass
class SystemReport:
    """Point-in-time telemetry snapshot for reporting frontends, not control policy."""

    distro_name: str
    distro_ver: str
    arch: str
    processor_model: str
    total_core: int | None
    kernel_version: str
    current_gov: str | None
    current_epp: str | None
    current_epb: str | None
    current_hwp_dynamic_boost: bool | None
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
    cpu_avg_temp: float | None = None
    offline_cpus: tuple[int, ...] = ()


class SystemInfo:
    """
    Provides system information related to CPU, distribution, and performance metrics.
    """

    def __init__(self):
        if IS_INSTALLED_WITH_SNAP:
            try:
                host_distro = distro.LinuxDistribution(root_dir=SNAP_HOST_ROOT)
                self.distro_name = host_distro.name(pretty=False) or "UNKNOWN"
                self.distro_version = host_distro.version() or "UNKNOWN"
            except (OSError, UnicodeError, ValueError):
                self.distro_name = "UNKNOWN"
                self.distro_version = "UNKNOWN"
        else:
            self.distro_name = distro.name(pretty=False)
            self.distro_version = distro.version()

        self.architecture: str = platform.machine()
        self.processor_model: str = (
            getoutput("grep -E 'model name' /proc/cpuinfo -m 1").split(":")[-1].strip()
        )
        self.cpu_driver: str = getoutput(
            "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver"
        ).strip()
        self.kernel_version: str = platform.release()

    @staticmethod
    def cpu_frequencies():
        try:
            return psutil.cpu_freq(percpu=True) or []
        except (AttributeError, NotImplementedError, OSError):
            return []

    @staticmethod
    def cpu_min_freq(freqs=None) -> float | None:
        cpu_freqs = freqs if freqs is not None else SystemInfo.cpu_frequencies()
        values = (
            float(getattr(freq, "min", 0.0) or 0.0)
            for freq in cpu_freqs
        )
        return min((value for value in values if value > 0), default=None)

    @staticmethod
    def cpu_max_freq(freqs=None) -> float | None:
        cpu_freqs = freqs if freqs is not None else SystemInfo.cpu_frequencies()
        values = (
            float(getattr(freq, "max", 0.0) or 0.0)
            for freq in cpu_freqs
        )
        return max((value for value in values if value > 0), default=None)

    @staticmethod
    def cpu_current_frequency(cpu_id: int) -> float | None:
        cpufreq_path = CPU_SYSFS_ROOT / f"cpu{cpu_id}" / "cpufreq"
        for name in ("cpuinfo_cur_freq", "scaling_cur_freq"):
            value = SystemInfo.read_file(str(cpufreq_path / name))
            if value is None:
                continue

            try:
                frequency = float(value) / 1000
            except ValueError:
                continue

            if frequency > 0:
                return frequency

        return None

    @staticmethod
    def _parse_cpu_list(value: str) -> list[int]:
        cpus = []
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue

            if "-" in part:
                start, end = part.split("-", 1)
                start_cpu = int(start)
                end_cpu = int(end)
                if end_cpu < start_cpu:
                    raise ValueError("invalid CPU range")
                cpus.extend(range(start_cpu, end_cpu + 1))
            else:
                cpus.append(int(part))

        return cpus

    @staticmethod
    def cpu_ids(mask: str) -> list[int]:
        value = SystemInfo.read_file(str(CPU_SYSFS_ROOT / mask))
        if not value:
            return []

        try:
            return SystemInfo._parse_cpu_list(value)
        except ValueError:
            return []

    @staticmethod
    def offline_cpu_ids() -> list[int]:
        present = set(SystemInfo.cpu_ids("present"))
        online = set(SystemInfo.cpu_ids("online"))
        if not present or not online:
            return []
        return sorted(present - online)

    @staticmethod
    def _cpu_core_id(cpu_id: int) -> int | None:
        value = SystemInfo.read_file(
            str(CPU_SYSFS_ROOT / f"cpu{cpu_id}" / "topology" / "core_id")
        )
        if value is None:
            return None

        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def cpu_temperature_snapshot(
        cpu_ids: list[int] | None = None,
    ) -> tuple[dict[int, float], float | None]:
        try:
            temps = psutil.sensors_temperatures()
        except (AttributeError, NotImplementedError, OSError):
            return {}, None

        ids = cpu_ids if cpu_ids is not None else SystemInfo.cpu_ids("online")

        def snapshot_from_entries(entries):
            readings = []
            for entry in entries:
                try:
                    current = float(entry.current)
                except (AttributeError, TypeError, ValueError):
                    continue
                if current > 0:
                    readings.append(current)

            if not readings:
                return None

            average = sum(readings) / len(readings)

            if not ids:
                return {
                    cpu_id: temperature
                    for cpu_id, temperature in enumerate(readings)
                }, average

            if len(readings) == len(ids):
                return dict(zip(ids, readings)), average

            return {cpu_id: average for cpu_id in ids}, average

        coretemp_entries = temps.get("coretemp", [])
        if coretemp_entries:
            if ids:
                temperatures_by_core = {}
                duplicate_core_id = False
                for entry in coretemp_entries:
                    label = str(getattr(entry, "label", "") or "")
                    if not label.startswith("Core "):
                        continue

                    try:
                        core_id = int(label.removeprefix("Core ").strip())
                        current = float(entry.current)
                    except (AttributeError, TypeError, ValueError):
                        continue

                    if current <= 0:
                        continue
                    if core_id in temperatures_by_core:
                        duplicate_core_id = True
                        break
                    temperatures_by_core[core_id] = current

                if temperatures_by_core and not duplicate_core_id:
                    by_cpu = {}
                    matched_core_ids = set()
                    for cpu_id in ids:
                        core_id = SystemInfo._cpu_core_id(cpu_id)
                        if core_id in temperatures_by_core:
                            by_cpu[cpu_id] = temperatures_by_core[core_id]
                            matched_core_ids.add(core_id)

                    if by_cpu:
                        average = sum(
                            temperatures_by_core[core_id]
                            for core_id in matched_core_ids
                        ) / len(matched_core_ids)
                        return by_cpu, average

            snapshot = snapshot_from_entries(coretemp_entries)
            if snapshot is not None:
                return snapshot

        # Preserve the legacy fallback for hwmon drivers that expose
        # CPU temperature under a device-specific sensor group.
        for entries in temps.values():
            for entry in entries:
                label = str(getattr(entry, "label", "") or "")
                if "CPU" not in label and "Tctl" not in label:
                    continue

                try:
                    current = float(entry.current)
                except (AttributeError, TypeError, ValueError):
                    continue

                if current <= 0:
                    continue

                if not ids:
                    return {0: current}, current

                return {
                    cpu_id: current
                    for cpu_id in ids
                }, current

        for sensor in CPU_TEMP_SENSOR_PRIORITY:
            if sensor == "coretemp":
                continue

            snapshot = snapshot_from_entries(
                temps.get(sensor, [])
            )
            if snapshot is not None:
                return snapshot

        return {}, None

    @staticmethod
    def cpu_temperatures() -> List[float]:
        temperatures, _ = SystemInfo.cpu_temperature_snapshot()
        return [
            temperatures[cpu_id]
            for cpu_id in sorted(temperatures)
        ]

    @staticmethod
    def cpu_usage_snapshot(
        online_cpus: list[int] | None = None,
    ) -> tuple[float, list[float]]:
        try:
            per_cpu = psutil.cpu_percent(interval=0.5, percpu=True)
        except (AttributeError, OSError):
            return 0.0, []

        if not per_cpu:
            return 0.0, []

        online = list(online_cpus) if online_cpus else []
        if not online:
            sampled = per_cpu
        elif len(per_cpu) == len(online):
            sampled = per_cpu
        else:
            sampled = [
                per_cpu[cpu_id]
                for cpu_id in online
                if cpu_id < len(per_cpu)
            ]

        if not sampled:
            return 0.0, per_cpu

        return sum(sampled) / len(sampled), per_cpu

    @staticmethod
    def get_cpu_info(
        cpu_freqs=None,
        core_temps=None,
        online_cpus=None,
        cpu_usage=None,
    ) -> List[CoreInfo]:
        """Returns detailed CPU information for each online logical CPU."""
        # Keep the existing argument for callers, but do not map its positional
        # entries to CPU IDs: psutil may return one entry per CPUFreq policy.
        if cpu_usage is None:
            try:
                cpu_usage = psutil.cpu_percent(interval=0.5, percpu=True)
            except (AttributeError, OSError):
                cpu_usage = []

        online = (
            list(online_cpus)
            if online_cpus
            else list(range(len(cpu_usage)))
        )
        temperatures = (
            core_temps
            if core_temps is not None
            else SystemInfo.cpu_temperature_snapshot(online)[0]
        )
        valid_temperatures = [
            temperature
            for temperature in temperatures.values()
            if temperature > 0
        ]
        avg_temp = (
            sum(valid_temperatures) / len(valid_temperatures)
            if valid_temperatures
            else 0.0
        )

        def value_for_cpu(values, cpu_id, position):
            if len(values) == len(online):
                return values[position]
            if cpu_id < len(values):
                return values[cpu_id]
            return None

        cores = []
        for position, cpu_id in enumerate(online):
            usage = value_for_cpu(cpu_usage, cpu_id, position)
            frequency = SystemInfo.cpu_current_frequency(cpu_id) or 0.0
            temperature = temperatures.get(cpu_id, avg_temp)

            cores.append(
                CoreInfo(
                    id=cpu_id,
                    usage=float(usage or 0.0),
                    temperature=temperature if temperature > 0 else avg_temp,
                    frequency=frequency,
                )
            )

        return cores

    @staticmethod
    def cpu_fan_speed() -> int | None:
        try:
            fans = psutil.sensors_fans()
        except (AttributeError, NotImplementedError, OSError):
            return None

        for entries in fans.values():
            for fan in entries:
                try:
                    current = float(fan.current)
                except (AttributeError, TypeError, ValueError):
                    continue
                if current > 0:
                    return int(current)
        return None

    @staticmethod
    def current_gov() -> str | None:
        try:
            with open(
                "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "r"
            ) as f:
                return f.read().strip()
        except OSError:
            return None

    @staticmethod
    def current_epp(_is_ac_plugged: bool | None = None) -> str | None:
        paths = list(Path("/sys/devices/system/cpu").glob(
            "cpu[0-9]*/cpufreq/energy_performance_preference"
        ))
        if not paths:
            return None

        values = set()
        for path in paths:
            value = SystemInfo.read_file(str(path))
            if value is None:
                return None
            values.add(value)

        if len(values) > 1:
            return "mixed"
        return values.pop()

    @staticmethod
    def current_epb(_is_ac_plugged: bool | None = None) -> str | None:
        epb_names = {
            "0": "performance",
            "4": "balance_performance",
            "6": "default",
            "8": "balance_power",
            "15": "power",
        }
        paths = list(Path("/sys/devices/system/cpu").glob(
            "cpu[0-9]*/power/energy_perf_bias"
        ))
        if not paths:
            return None

        values = set()
        for path in paths:
            value = SystemInfo.read_file(str(path))
            if value is None:
                return None
            values.add(epb_names.get(value, value))

        if len(values) > 1:
            return "mixed"
        return values.pop()

    @staticmethod
    def cpu_usage() -> float:
        try:
            return psutil.cpu_percent(interval=0.5)
        except (AttributeError, OSError):
            return 0.0

    @staticmethod
    def system_load() -> float:
        return os.getloadavg()[0]

    @staticmethod
    def avg_load() -> Tuple[float, float, float]:
        return os.getloadavg()

    @staticmethod
    def avg_temp() -> int:
        _, average = SystemInfo.cpu_temperature_snapshot()
        return int(average) if average is not None else 0

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
            try:
                amd_status = amd_pstate.read_text().strip()
            except OSError:
                return None, None
            if amd_status == "active":
                return None, True
            return None, False
        else:
            return None, None

        try:
            current_value = int(control_file.read_text().strip())
            return bool(current_value) ^ inverse_logic, False
        except (OSError, ValueError):
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
            ignore_list = get_power_supply_ignore_list()
            batteries = []
            for entry in sorted(os.listdir(POWER_SUPPLY_DIR)):
                if any(item in entry for item in ignore_list):
                    continue

                path = os.path.join(POWER_SUPPLY_DIR, entry)
                type_path = os.path.join(path, "type")
                if not os.path.isfile(type_path):
                    continue

                content = SystemInfo.read_file(type_path)
                if not content or content.lower() != "battery":
                    continue

                scope = SystemInfo.read_file(os.path.join(path, "scope"))
                if scope and scope.lower() == "device":
                    continue

                priority = 0 if scope and scope.lower() == "system" else 1
                batteries.append((priority, entry, path))

            if batteries:
                return min(batteries)[2]
        except OSError:
            return None
        return None

    @staticmethod
    def external_power_state(
        battery_path: Optional[str] = None,
    ) -> bool | None:
        """Return external-power state without collecting battery telemetry."""
        if battery_path is None:
            battery_path = SystemInfo.get_battery_path()

        # Preserve the historical desktop fallback: without a usable system
        # battery, assume the system is externally powered.
        if not battery_path:
            return True

        external_power_states = []
        ignore_list = get_power_supply_ignore_list()

        try:
            for supply in sorted(os.listdir(POWER_SUPPLY_DIR)):
                if any(item in supply for item in ignore_list):
                    continue

                supply_path = os.path.join(POWER_SUPPLY_DIR, supply)
                supply_type = SystemInfo.read_file(
                    os.path.join(supply_path, "type")
                )
                if not supply_type or supply_type.lower() == "battery":
                    continue

                scope = SystemInfo.read_file(
                    os.path.join(supply_path, "scope")
                )
                if scope and scope.lower() == "device":
                    continue

                online = SystemInfo.read_file(
                    os.path.join(supply_path, "online")
                )
                if online in ("0", "1", "2"):
                    external_power_states.append(online != "0")
        except OSError:
            external_power_states = []

        if external_power_states:
            return any(external_power_states)

        battery_status = SystemInfo.read_file(
            os.path.join(battery_path, "status")
        )
        if not battery_status:
            return None

        battery_status = battery_status.lower()
        if battery_status == "discharging":
            return False
        if battery_status in ("charging", "not charging", "full"):
            return True

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

        # Reading battery information
        battery_status = SystemInfo.read_file(os.path.join(battery_path, "status"))
        battery_capacity = SystemInfo.read_file(os.path.join(battery_path, "capacity"))

        is_ac_plugged = SystemInfo.external_power_state(battery_path)

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
    def turbo_on_suggestion(report: SystemReport | None = None) -> bool:
        usage = report.cpu_usage if report is not None else SystemInfo.cpu_usage()

        if report is not None:
            if report.cpu_avg_temp is not None:
                avg_temp = report.cpu_avg_temp
            else:
                temperatures = [
                    core.temperature
                    for core in report.cores_info
                    if core.temperature > 0
                ]
                avg_temp = (
                    sum(temperatures) / len(temperatures)
                    if temperatures
                    else 0.0
                )
        else:
            avg_temp = SystemInfo.avg_temp()

        if usage >= 20.0:
            return True
        elif usage <= 25 and avg_temp >= 70:
            return False
        return False

    @staticmethod
    def governor_suggestion(report: SystemReport | None = None) -> str:
        battery_info = (
            report.battery_info
            if report is not None
            else SystemInfo.battery_info()
        )
        if battery_info.is_ac_plugged is not False:
            return AVAILABLE_GOVERNORS_SORTED[0]
        return AVAILABLE_GOVERNORS_SORTED[-1]

    def generate_system_report(self) -> SystemReport:
        """Collect one reporting snapshot without changing system state."""
        battery_info = self.battery_info()
        cpu_freqs = self.cpu_frequencies()
        online_cpus = self.cpu_ids("online")
        total_cores = (
            len(online_cpus)
            if online_cpus
            else psutil.cpu_count(logical=True)
        )
        core_temps, avg_temp = self.cpu_temperature_snapshot(online_cpus)
        total_usage, per_cpu_usage = self.cpu_usage_snapshot(online_cpus)
        load_average = self.avg_load()

        return SystemReport(
            distro_name=self.distro_name,
            distro_ver=self.distro_version,
            arch=self.architecture,
            processor_model=self.processor_model,
            total_core=total_cores,
            cpu_driver=self.cpu_driver,
            kernel_version=self.kernel_version,
            current_gov=self.current_gov(),
            current_epp=self.current_epp(battery_info.is_ac_plugged),
            current_epb=self.current_epb(battery_info.is_ac_plugged),
            current_hwp_dynamic_boost=get_hwp_dynamic_boost(),
            cpu_fan_speed=self.cpu_fan_speed(),
            cpu_usage=total_usage,
            cpu_max_freq=self.cpu_max_freq(cpu_freqs),
            cpu_min_freq=self.cpu_min_freq(cpu_freqs),
            load=load_average[0],
            avg_load=load_average,
            cores_info=self.get_cpu_info(
                cpu_freqs,
                core_temps,
                online_cpus,
                per_cpu_usage,
            ),
            is_turbo_on=self.turbo_on(),
            battery_info=battery_info,
            cpu_avg_temp=avg_temp,
            offline_cpus=tuple(self.offline_cpu_ids()),
        )


system_info = SystemInfo()


def format_system_report(
    report: SystemReport,
    include_distro: bool = True,
    include_config: bool = True,
) -> str:
    """Format one SystemReport using the legacy textual status layout."""
    lines = []

    if include_distro:
        distro_name = f"{report.distro_name} {report.distro_ver}".strip()
        lines.extend(
            [
                f"Linux distro: {distro_name}",
                f"Linux kernel: {report.kernel_version}",
            ]
        )

    total_core = (
        str(report.total_core)
        if report.total_core is not None
        else "Unknown"
    )
    lines.extend(
        [
            f"Processor: {report.processor_model}",
            f"Cores: {total_core}",
            f"Architecture: {report.arch}",
            f"Driver: {report.cpu_driver}",
        ]
    )

    if include_config:
        config_path = config.path
        if config_path and os.path.isfile(config_path):
            lines.extend(["", f"Using settings defined in {config_path}"])

    max_freq = (
        f"{report.cpu_max_freq:.0f} MHz"
        if report.cpu_max_freq is not None
        else "Unknown"
    )
    min_freq = (
        f"{report.cpu_min_freq:.0f} MHz"
        if report.cpu_min_freq is not None
        else "Unknown"
    )

    lines.extend(
        [
            "",
            "-" * 30 + " Current CPU stats " + "-" * 30,
            "",
            f"CPU max frequency: {max_freq}",
            f"CPU min frequency: {min_freq}",
            "",
            "Core\tUsage\tTemperature\tFrequency",
        ]
    )

    for core in report.cores_info:
        temperature = (
            f"{core.temperature:>3.0f} °C"
            if core.temperature > 0
            else "  —"
        )
        frequency = (
            f"{core.frequency:>5.0f} MHz"
            if core.frequency > 0
            else "    —"
        )
        lines.append(
            f"CPU{core.id}    {core.usage:>5.1f}%       "
            f"{temperature}     {frequency}"
        )

    if report.offline_cpus:
        lines.extend(
            [
                "",
                "Disabled CPUs: "
                + ",".join(str(cpu) for cpu in report.offline_cpus),
            ]
        )

    if report.cpu_fan_speed:
        lines.extend(["", f"CPU fan speed: {report.cpu_fan_speed} RPM"])

    return "\n".join(lines)


def print_system_report(
    report: SystemReport | None = None,
    output=None,
    include_distro: bool = True,
    include_config: bool = True,
):
    """Print a structured snapshot without collecting the same status twice."""
    if report is None:
        report = system_info.generate_system_report()

    print(
        format_system_report(
            report,
            include_distro=include_distro,
            include_config=include_config,
        ),
        file=output,
    )