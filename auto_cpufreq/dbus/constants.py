#!/usr/bin/env python3
"""
D-Bus constants for power-profiles-daemon compatibility.

This module provides the D-Bus service names, object paths, and interface
constants required to implement the org.freedesktop.UPower.PowerProfiles
interface as a drop-in replacement for power-profiles-daemon.
"""

# D-Bus service identification
DBUS_SERVICE_NAME = "org.freedesktop.UPower.PowerProfiles"
DBUS_OBJECT_PATH = "/org/freedesktop/UPower/PowerProfiles"
DBUS_INTERFACE_NAME = "org.freedesktop.UPower.PowerProfiles"

# Profile names matching power-profiles-daemon specification
PROFILE_POWER_SAVER = "power-saver"
PROFILE_BALANCED = "balanced"
PROFILE_PERFORMANCE = "performance"

# Valid profiles list (ordered from lowest to highest power)
VALID_PROFILES = [PROFILE_POWER_SAVER, PROFILE_BALANCED, PROFILE_PERFORMANCE]

# Profile priority for hold resolution (higher index = higher priority)
PROFILE_PRIORITY = {
    PROFILE_POWER_SAVER: 0,
    PROFILE_BALANCED: 1,
    PROFILE_PERFORMANCE: 2,
}

# Mapping from D-Bus profiles to auto-cpufreq override values
PROFILE_TO_OVERRIDE = {
    PROFILE_PERFORMANCE: "performance",
    PROFILE_BALANCED: "default",  # "default" means auto-switch based on AC/battery
    PROFILE_POWER_SAVER: "powersave",
}

# Mapping from auto-cpufreq override values to D-Bus profiles
OVERRIDE_TO_PROFILE = {
    "performance": PROFILE_PERFORMANCE,
    "default": PROFILE_BALANCED,
    "powersave": PROFILE_POWER_SAVER,
}

# Turbo settings per profile
PROFILE_TURBO_SETTINGS = {
    PROFILE_PERFORMANCE: "always",
    PROFILE_BALANCED: "auto",
    PROFILE_POWER_SAVER: "never",
}

# Service version (matches auto-cpufreq version)
SERVICE_VERSION = "3.0.0"
