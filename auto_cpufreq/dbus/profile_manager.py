#!/usr/bin/env python3
"""
Profile hold management for power-profiles-daemon D-Bus compatibility.

This module handles the HoldProfile/ReleaseProfile mechanism that allows
applications to temporarily request a specific power profile.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable

from .constants import (
    PROFILE_PRIORITY,
    PROFILE_BALANCED,
    VALID_PROFILES,
)


@dataclass
class ProfileHold:
    """Represents a single profile hold request from an application."""
    cookie: int
    profile: str
    reason: str
    application_id: str
    sender: str  # D-Bus unique name for tracking disconnections
    timestamp: float = field(default_factory=time.time)


class ProfileHoldManager:
    """
    Manages profile holds with cookie-based tracking.

    Profile holds allow applications to temporarily request a specific
    power profile. When multiple holds are active, the highest-priority
    profile wins (performance > balanced > power-saver).
    """

    def __init__(self, on_effective_profile_changed: Optional[Callable[[str], None]] = None):
        """
        Initialize the profile hold manager.

        Args:
            on_effective_profile_changed: Callback invoked when the effective
                profile changes due to holds being added/removed.
        """
        self._holds: Dict[int, ProfileHold] = {}
        self._next_cookie: int = 1
        self._lock = threading.Lock()
        self._on_effective_profile_changed = on_effective_profile_changed
        self._last_effective_profile: Optional[str] = None

    def hold_profile(
        self,
        profile: str,
        reason: str,
        application_id: str,
        sender: str
    ) -> int:
        """
        Create a new profile hold.

        Args:
            profile: The profile to hold ("power-saver", "balanced", "performance")
            reason: Human-readable reason for the hold
            application_id: Application identifier (e.g., "org.gnome.Settings")
            sender: D-Bus unique name of the requesting client

        Returns:
            Cookie (unique identifier) for this hold

        Raises:
            ValueError: If the profile is not valid
        """
        if profile not in VALID_PROFILES:
            raise ValueError(f"Invalid profile: {profile}. Must be one of {VALID_PROFILES}")

        with self._lock:
            cookie = self._next_cookie
            self._next_cookie += 1

            self._holds[cookie] = ProfileHold(
                cookie=cookie,
                profile=profile,
                reason=reason,
                application_id=application_id,
                sender=sender,
            )

            self._check_effective_profile_change()
            return cookie

    def release_profile(self, cookie: int) -> bool:
        """
        Release a profile hold by its cookie.

        Args:
            cookie: The cookie returned by hold_profile()

        Returns:
            True if the hold was found and released, False otherwise
        """
        with self._lock:
            if cookie in self._holds:
                del self._holds[cookie]
                self._check_effective_profile_change()
                return True
            return False

    def cleanup_sender_holds(self, sender: str) -> List[int]:
        """
        Remove all holds from a disconnected D-Bus client.

        Args:
            sender: D-Bus unique name of the disconnected client

        Returns:
            List of cookies that were released (for emitting ProfileReleased signals)
        """
        with self._lock:
            to_remove = [
                cookie for cookie, hold in self._holds.items()
                if hold.sender == sender
            ]
            for cookie in to_remove:
                del self._holds[cookie]

            if to_remove:
                self._check_effective_profile_change()

            return to_remove

    def get_effective_profile(self, base_profile: str) -> str:
        """
        Determine the effective profile based on active holds.

        The effective profile is the highest-priority profile among all
        active holds. If no holds are active, returns the base profile.

        Priority order: performance > balanced > power-saver

        Args:
            base_profile: The profile to use if no holds are active

        Returns:
            The effective profile name
        """
        with self._lock:
            if not self._holds:
                return base_profile

            # Find the highest-priority hold
            max_priority = -1
            effective = base_profile

            for hold in self._holds.values():
                priority = PROFILE_PRIORITY.get(hold.profile, 0)
                if priority > max_priority:
                    max_priority = priority
                    effective = hold.profile

            return effective

    def get_active_holds(self) -> List[Dict]:
        """
        Get information about all active holds.

        Returns:
            List of dictionaries with hold information for D-Bus ActiveProfileHolds property
        """
        with self._lock:
            return [
                {
                    "ApplicationId": hold.application_id,
                    "Profile": hold.profile,
                    "Reason": hold.reason,
                }
                for hold in self._holds.values()
            ]

    def has_holds(self) -> bool:
        """Check if there are any active holds."""
        with self._lock:
            return len(self._holds) > 0

    def _check_effective_profile_change(self):
        """
        Check if the effective profile has changed and invoke callback.

        Must be called with _lock held.
        """
        if self._on_effective_profile_changed is None:
            return

        # Calculate current effective profile
        if not self._holds:
            current = PROFILE_BALANCED  # Default when no holds
        else:
            max_priority = -1
            current = PROFILE_BALANCED
            for hold in self._holds.values():
                priority = PROFILE_PRIORITY.get(hold.profile, 0)
                if priority > max_priority:
                    max_priority = priority
                    current = hold.profile

        if current != self._last_effective_profile:
            self._last_effective_profile = current
            # Release lock before callback to avoid deadlocks
            callback = self._on_effective_profile_changed
            # Schedule callback outside of lock
            threading.Thread(
                target=callback,
                args=(current,),
                daemon=True
            ).start()
