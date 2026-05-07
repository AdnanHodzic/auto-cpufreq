#!/usr/bin/env python3
"""
D-Bus support for auto-cpufreq.

This package provides a drop-in replacement for power-profiles-daemon,
implementing the org.freedesktop.UPower.PowerProfiles D-Bus interface.
This allows desktop environments like GNOME and KDE to control CPU
performance through their native power management interfaces.
"""

from .service import PowerProfilesService, PowerProfilesInterface
from .profile_manager import ProfileHoldManager, ProfileHold
from .constants import (
    DBUS_SERVICE_NAME,
    DBUS_OBJECT_PATH,
    DBUS_INTERFACE_NAME,
    PROFILE_POWER_SAVER,
    PROFILE_BALANCED,
    PROFILE_PERFORMANCE,
    VALID_PROFILES,
)

__all__ = [
    # Main service
    "PowerProfilesService",
    "PowerProfilesInterface",
    # Profile management
    "ProfileHoldManager",
    "ProfileHold",
    # Constants
    "DBUS_SERVICE_NAME",
    "DBUS_OBJECT_PATH",
    "DBUS_INTERFACE_NAME",
    "PROFILE_POWER_SAVER",
    "PROFILE_BALANCED",
    "PROFILE_PERFORMANCE",
    "VALID_PROFILES",
]
