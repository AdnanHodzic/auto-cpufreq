#!/usr/bin/env python3
"""
D-Bus service implementing org.freedesktop.UPower.PowerProfiles interface.

This module provides a drop-in replacement for power-profiles-daemon,
allowing desktop environments like GNOME and KDE to control CPU performance
through the standard D-Bus interface.
"""

import logging
from typing import List, Dict

from dasbus.connection import SystemMessageBus
from dasbus.identifier import DBusServiceIdentifier
from dasbus.loop import EventLoop
from dasbus.server.interface import dbus_interface, dbus_signal
from dasbus.server.template import PropertiesInterface
from dasbus.server.property import emits_properties_changed
from dasbus.server.publishable import Publishable
from dasbus.typing import Str, Bool, UInt32, Variant, get_variant
from dasbus.structure import DBusData
from gi.repository import GLib

from .constants import (
    DBUS_SERVICE_NAME,
    DBUS_OBJECT_PATH,
    DBUS_INTERFACE_NAME,
    PROFILE_POWER_SAVER,
    PROFILE_BALANCED,
    PROFILE_PERFORMANCE,
    VALID_PROFILES,
    PROFILE_TO_OVERRIDE,
    OVERRIDE_TO_PROFILE,
    PROFILE_TURBO_SETTINGS,
    SERVICE_VERSION,
)
from .profile_manager import ProfileHoldManager

# Set up logging
log = logging.getLogger(__name__)

# D-Bus service identifier
POWER_PROFILES = DBusServiceIdentifier(
    namespace=("org", "freedesktop", "UPower"),
    service_version=1,
    message_bus=SystemMessageBus()
)


@dbus_interface(DBUS_INTERFACE_NAME)
class PowerProfilesInterface(Publishable, PropertiesInterface):
    """
    Implementation of the org.freedesktop.UPower.PowerProfiles D-Bus interface.

    This interface is compatible with power-profiles-daemon and allows desktop
    environments to control CPU performance profiles.
    """

    def __init__(self):
        """Initialize the power profiles interface."""
        super().__init__()
        self._hold_manager = ProfileHoldManager(
            on_effective_profile_changed=self._on_hold_effective_change
        )
        self._battery_aware = True
        self._bus = None
        self._connected_clients: Dict[str, bool] = {}

        # Import core functions (delayed to avoid circular imports)
        from auto_cpufreq.core import (
            get_override,
            set_override,
            get_turbo_override,
            set_turbo_override,
        )
        self._get_override = get_override
        self._set_override = set_override
        self._get_turbo_override = get_turbo_override
        self._set_turbo_override = set_turbo_override

    def for_publication(self):
        """Return this object for D-Bus publication."""
        return self

    def set_bus(self, bus):
        """Set the D-Bus connection for signal emission."""
        self._bus = bus

    def _on_hold_effective_change(self, new_profile: str):
        """Called when holds cause the effective profile to change."""
        self._apply_profile(new_profile)

    def _get_current_profile(self) -> str:
        """Get the current profile based on override state."""
        override = self._get_override()
        return OVERRIDE_TO_PROFILE.get(override, PROFILE_BALANCED)

    def _apply_profile(self, profile: str):
        """
        Apply a profile by setting the appropriate overrides.

        Args:
            profile: One of "power-saver", "balanced", "performance"
        """
        if profile not in VALID_PROFILES:
            log.warning(f"Invalid profile: {profile}")
            return

        # Map profile to override value
        override = PROFILE_TO_OVERRIDE.get(profile, "default")

        # Set governor override
        if override == "default":
            self._set_override("reset")
        else:
            self._set_override(override)

        # Set turbo override
        turbo = PROFILE_TURBO_SETTINGS.get(profile, "auto")
        self._set_turbo_override(turbo)

        log.info(f"Applied profile: {profile} (override={override}, turbo={turbo})")

    # ==================== D-Bus Methods ====================

    def HoldProfile(self, profile: Str, reason: Str, application_id: Str) -> UInt32:
        """
        Hold a power profile temporarily.

        Applications can request to hold a specific profile. When multiple
        holds are active, the highest-priority profile wins.

        Args:
            profile: Profile to hold ("power-saver", "balanced", "performance")
            reason: Human-readable reason for the hold
            application_id: Application identifier

        Returns:
            Cookie to use when releasing the hold
        """
        # Get the sender's unique bus name
        # Note: In production, this would come from the D-Bus message context
        # For now, use application_id as a fallback
        sender = application_id

        log.info(f"HoldProfile: profile={profile}, reason={reason}, app={application_id}")

        if profile not in VALID_PROFILES:
            raise ValueError(f"Invalid profile: {profile}")

        cookie = self._hold_manager.hold_profile(
            profile=profile,
            reason=reason,
            application_id=application_id,
            sender=sender,
        )

        # Apply the effective profile
        effective = self._hold_manager.get_effective_profile(self._get_current_profile())
        self._apply_profile(effective)

        log.info(f"HoldProfile: assigned cookie {cookie}")
        return cookie

    def ReleaseProfile(self, cookie: UInt32):
        """
        Release a previously held profile.

        Args:
            cookie: Cookie returned by HoldProfile
        """
        log.info(f"ReleaseProfile: cookie={cookie}")

        if self._hold_manager.release_profile(cookie):
            # Emit ProfileReleased signal
            self.ProfileReleased(cookie)

            # Revert to base profile if no more holds
            if not self._hold_manager.has_holds():
                base_profile = self._get_current_profile()
                self._apply_profile(base_profile)
                log.info(f"No more holds, reverted to base profile: {base_profile}")
        else:
            log.warning(f"ReleaseProfile: cookie {cookie} not found")

    def SetActionEnabled(self, action: Str, enabled: Bool):
        """
        Enable or disable an action.

        Currently not implemented as Actions are empty for initial release.

        Args:
            action: Action name
            enabled: Whether to enable the action
        """
        log.info(f"SetActionEnabled: action={action}, enabled={enabled}")
        # Actions not implemented in initial release
        pass

    # ==================== D-Bus Properties ====================

    @property
    def ActiveProfile(self) -> Str:
        """
        The currently active power profile.

        Returns one of: "power-saver", "balanced", "performance"
        """
        # If there are active holds, return the effective profile
        if self._hold_manager.has_holds():
            base = self._get_current_profile()
            return self._hold_manager.get_effective_profile(base)

        return self._get_current_profile()

    @ActiveProfile.setter
    @emits_properties_changed
    def ActiveProfile(self, profile: Str):
        """
        Set the active power profile.

        Args:
            profile: One of "power-saver", "balanced", "performance"
        """
        log.info(f"Setting ActiveProfile to: {profile}")

        if profile not in VALID_PROFILES:
            raise ValueError(f"Invalid profile: {profile}. Must be one of {VALID_PROFILES}")

        self._apply_profile(profile)

    @property
    def PerformanceInhibited(self) -> Str:
        """
        Reason why performance profile is inhibited.

        Returns empty string if performance is not inhibited.
        """
        # Performance is not inhibited in auto-cpufreq
        return ""

    @property
    def PerformanceDegraded(self) -> Str:
        """
        Reason why performance is degraded.

        Returns a string like "high-operating-temperature" if performance
        is degraded due to thermal throttling, empty string otherwise.
        """
        # Could integrate with temperature monitoring in the future
        # For now, return empty
        return ""

    @property
    def Profiles(self) -> List[Dict[Str, Variant]]:
        """
        List of available profiles with metadata.

        Returns array of dictionaries with profile information.
        """
        return [
            {
                "Profile": get_variant(Str, PROFILE_POWER_SAVER),
                "CpuDriver": get_variant(Str, "auto-cpufreq"),
                "Driver": get_variant(Str, "auto-cpufreq"),
            },
            {
                "Profile": get_variant(Str, PROFILE_BALANCED),
                "CpuDriver": get_variant(Str, "auto-cpufreq"),
                "Driver": get_variant(Str, "auto-cpufreq"),
            },
            {
                "Profile": get_variant(Str, PROFILE_PERFORMANCE),
                "CpuDriver": get_variant(Str, "auto-cpufreq"),
                "Driver": get_variant(Str, "auto-cpufreq"),
            },
        ]

    @property
    def Actions(self) -> List[Str]:
        """
        List of available actions.

        Empty for initial implementation.
        """
        return []

    @property
    def ActionsInfo(self) -> List[Dict[Str, Variant]]:
        """
        Detailed information about available actions.

        Empty for initial implementation.
        """
        return []

    @property
    def ActiveProfileHolds(self) -> List[Dict[Str, Variant]]:
        """
        List of active profile holds.

        Returns array of dictionaries with hold information.
        """
        holds = self._hold_manager.get_active_holds()
        # Convert to D-Bus variant format
        return [
            {
                "ApplicationId": get_variant(Str, h["ApplicationId"]),
                "Profile": get_variant(Str, h["Profile"]),
                "Reason": get_variant(Str, h["Reason"]),
            }
            for h in holds
        ]

    @property
    def Version(self) -> Str:
        """Service version string."""
        return SERVICE_VERSION

    @property
    def BatteryAware(self) -> Bool:
        """
        Whether the daemon automatically adjusts based on battery state.

        When True, "balanced" profile auto-switches between performance
        (on AC) and power-saver (on battery) settings.
        """
        return self._battery_aware

    @BatteryAware.setter
    @emits_properties_changed
    def BatteryAware(self, value: Bool):
        """Set whether the daemon is battery-aware."""
        self._battery_aware = value
        log.info(f"BatteryAware set to: {value}")

    # ==================== D-Bus Signals ====================

    @dbus_signal
    def ProfileReleased(self, cookie: UInt32):
        """
        Signal emitted when a profile hold is released.

        Args:
            cookie: The cookie of the released hold
        """
        pass


class PowerProfilesService:
    """
    Main service class that manages the D-Bus connection and lifecycle.
    """

    def __init__(self):
        """Initialize the power profiles service."""
        self._bus = SystemMessageBus()
        self._interface = PowerProfilesInterface()
        self._interface.set_bus(self._bus)
        self._loop = None
        self._registered = False

    def start(self):
        """
        Start the D-Bus service.

        Registers the service on the system bus and starts handling requests.
        """
        if self._registered:
            log.warning("Service already registered")
            return

        log.info(f"Registering D-Bus service: {DBUS_SERVICE_NAME}")

        # Publish the interface on the bus
        self._bus.publish_object(
            DBUS_OBJECT_PATH,
            self._interface
        )

        # Request the well-known name
        self._bus.register_service(DBUS_SERVICE_NAME)

        self._registered = True
        log.info("D-Bus service registered successfully")

    def stop(self):
        """
        Stop the D-Bus service.

        Unregisters from the system bus.
        """
        if not self._registered:
            return

        log.info("Stopping D-Bus service")

        try:
            self._bus.disconnect()
        except Exception as e:
            log.error(f"Error disconnecting from D-Bus: {e}")

        self._registered = False

    def get_event_loop(self) -> EventLoop:
        """
        Get the event loop for running the service.

        Returns:
            EventLoop instance that can be used to run the D-Bus service
        """
        if self._loop is None:
            self._loop = EventLoop()
        return self._loop

    @property
    def interface(self) -> PowerProfilesInterface:
        """Get the interface instance for direct access."""
        return self._interface
