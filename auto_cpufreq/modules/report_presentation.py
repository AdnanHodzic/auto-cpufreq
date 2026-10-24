"""Toolkit-neutral interpretation of observed SystemReport values.

This module never samples hardware and never applies a CPU/power policy.
GTK, Urwid and text frontends own layout and labels, but availability and
the meaning of observed values must come from the shared presentation rules.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Availability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    DRIVER_MANAGED = "driver-managed"


@dataclass(frozen=True)
class DisplayValue:
    value: Any
    availability: Availability
    text: str

    @property
    def is_available(self):
        return self.availability is Availability.AVAILABLE


@dataclass(frozen=True)
class BatteryPresentation:
    status: DisplayValue
    level: DisplayValue
    ac: DisplayValue
    charge_start: DisplayValue
    charge_stop: DisplayValue
    power_watts: DisplayValue


@dataclass(frozen=True)
class ReportPresentation:
    governor: DisplayValue
    turbo: DisplayValue
    epp: DisplayValue
    epb: DisplayValue
    hwp_dynamic_boost: DisplayValue
    battery: BatteryPresentation
    average_temperature: DisplayValue


@dataclass(frozen=True)
class PlatformProfilePresentation:
    """Semantics shared by GTK rows and the terminal profile summary."""

    interface: str
    current: str
    available_label: str
    available: str
    provider_label: str
    provider: str
    provider_visible: bool
    detected: bool
    status_text: str = "Unknown"


def present_platform_profile(snapshot):
    """Interpret platform profile and provider states without I/O.

    Preserve the historical status categories for the legacy text report.
    GTK and Stats intentionally show the more compact interface/control state.
    """
    status_text = {
        "available": "Available",
        "partial": "Partially available",
        "read-only": "Read-only",
        "unavailable": "No interface detected",
    }.get(snapshot.status, "Unknown")

    if snapshot.interface == "none":
        return PlatformProfilePresentation(
            interface="Not detected", current="Unknown",
            available_label="Available profiles", available="Could not be determined",
            provider_label="Provider", provider="", provider_visible=False,
            detected=False, status_text=status_text,
        )

    interface = {
        "modern": "Modern",
        "legacy": "Legacy",
    }.get(snapshot.interface, "Unknown")
    control = "Available" if snapshot.control_available else "Unavailable"

    if snapshot.choices_known:
        choices_label = f"Available profiles ({len(snapshot.available_profiles)})"
        choices_text = (
            ", ".join(snapshot.available_profiles)
            if snapshot.available_profiles else "None available"
        )
    else:
        choices_label = "Available profiles"
        choices_text = "Could not be determined"

    providers = snapshot.provider_states
    if len(providers) > 1:
        provider_label = "Providers"
        provider_text = "; ".join(
            f"{name}: {profile or 'Unknown'}"
            for name, profile in providers
        )
    elif providers:
        provider_label = "Provider"
        provider_text = providers[0][0]
    else:
        provider_label = "Provider"
        provider_text = ""

    return PlatformProfilePresentation(
        interface=f"{interface} · Control: {control}",
        current=snapshot.current or "Unknown",
        available_label=choices_label,
        available=choices_text,
        provider_label=provider_label,
        provider=provider_text,
        provider_visible=bool(providers),
        detected=True, status_text=status_text,
    )


def configuration_file_text(path, exists):
    """Return the same config-file label for terminal and GTK."""
    if not path:
        return "Configuration file: Not selected"
    if exists:
        return f"Configuration file: {path}"
    return f"Configuration file (not found): {path}"


def frequency_limit_text(value):
    """Present CPU frequency limits consistently in GTK and terminal Stats."""
    if value is None:
        return "Unavailable"
    return f"{value:.0f} MHz"


def offline_cpus_text(cpu_ids):
    """Show disabled CPUs only when the snapshot actually reports them."""
    if not cpu_ids:
        return None
    return "Disabled CPUs: " + ",".join(str(cpu) for cpu in cpu_ids)


def _known_text(value, *, unavailable="Unavailable"):
    if value is None or value == "":
        return DisplayValue(None, Availability.UNAVAILABLE, unavailable)
    return DisplayValue(value, Availability.AVAILABLE, str(value))


def _flag(value):
    if value is None:
        return DisplayValue(None, Availability.UNAVAILABLE, "Unavailable")
    return DisplayValue(value, Availability.AVAILABLE, "On" if value else "Off")


def interpret_turbo(state):
    """Preserve driver-managed versus disabled versus unknown distinctions."""
    enabled, driver_managed = state
    if enabled is not None:
        return _flag(enabled)
    if driver_managed is True:
        return DisplayValue(None, Availability.DRIVER_MANAGED, "Driver managed")
    return DisplayValue(None, Availability.UNAVAILABLE, "Unavailable")


def battery_present(battery):
    """Whether a battery was detected, independently of AC power state.

    Legacy BatteryInfo-like values without is_present remain valid.
    A missing battery may still have is_ac_plugged=True for policy purposes.
    """
    return battery is not None and getattr(battery, "is_present", True) is not False


def interpret_battery(battery):
    if not battery_present(battery):
        missing = DisplayValue(None, Availability.UNAVAILABLE, "Unavailable")
        return BatteryPresentation(
            status=DisplayValue(
                None, Availability.UNAVAILABLE, "No battery detected"
            ),
            level=missing, ac=missing,
            charge_start=missing, charge_stop=missing, power_watts=missing,
        )

    if battery.is_charging is True:
        status = DisplayValue(True, Availability.AVAILABLE, "Charging")
    elif battery.is_ac_plugged is False:
        status = DisplayValue(False, Availability.AVAILABLE, "Discharging")
    elif battery.is_ac_plugged is True:
        status = DisplayValue(False, Availability.AVAILABLE, "Not charging")
    else:
        status = DisplayValue(None, Availability.UNKNOWN, "Unknown")

    if battery.is_ac_plugged is True:
        ac = DisplayValue(True, Availability.AVAILABLE, "Connected")
    elif battery.is_ac_plugged is False:
        ac = DisplayValue(False, Availability.AVAILABLE, "Disconnected")
    else:
        ac = DisplayValue(None, Availability.UNKNOWN, "Unknown")

    level = (
        DisplayValue(battery.battery_level, Availability.AVAILABLE,
                     f"{battery.battery_level}%")
        if battery.battery_level is not None
        else DisplayValue(None, Availability.UNAVAILABLE, "Unavailable")
    )
    power = (
        DisplayValue(battery.power_watts, Availability.AVAILABLE,
                     f"{battery.power_watts:.2f} W")
        if battery.power_watts is not None
        else DisplayValue(None, Availability.UNAVAILABLE, "Unavailable")
    )
    return BatteryPresentation(
        status=status,
        level=level,
        ac=ac,
        charge_start=_known_text(battery.charging_start_threshold),
        charge_stop=_known_text(battery.charging_stop_threshold),
        power_watts=power,
    )


def interpret_average_temperature(report):
    temperature = report.cpu_avg_temp
    if temperature is None:
        readings = [
            core.temperature for core in report.cores_info
            if core.temperature > 0
        ]
        if readings:
            temperature = sum(readings) / len(readings)
    if temperature is None:
        return DisplayValue(None, Availability.UNAVAILABLE, "Unavailable")
    return DisplayValue(
        temperature, Availability.AVAILABLE, f"{temperature:.1f} °C"
    )


def present_report(report):
    """Pure, deterministic transformation from report to display semantics."""
    return ReportPresentation(
        governor=_known_text(report.current_gov),
        turbo=interpret_turbo(report.is_turbo_on),
        epp=_known_text(report.current_epp),
        epb=_known_text(report.current_epb),
        hwp_dynamic_boost=_flag(report.current_hwp_dynamic_boost),
        battery=interpret_battery(report.battery_info),
        average_temperature=interpret_average_temperature(report),
    )
