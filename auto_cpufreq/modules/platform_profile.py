from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PLATFORM_PROFILE_CLASS_ROOT = Path("/sys/class/platform-profile")
LEGACY_PLATFORM_PROFILE = Path("/sys/firmware/acpi/platform_profile")
LEGACY_PLATFORM_PROFILE_CHOICES = Path(
    "/sys/firmware/acpi/platform_profile_choices"
)


@dataclass(frozen=True)
class PlatformProfileDevice:
    """One kernel platform-profile provider and its observed state."""

    provider: str | None
    profile: str | None
    choices: tuple[str, ...]
    profile_path: Path
    choices_known: bool = False


@dataclass(frozen=True)
class PlatformProfileSnapshot:
    """One coherent read-only view of the kernel platform-profile state."""

    devices: tuple[PlatformProfileDevice, ...] = ()
    interface: str = "none"
    current: str | None = None
    available_profiles: tuple[str, ...] = ()
    choices_known: bool = False
    writable: bool = False

    @property
    def control_available(self) -> bool:
        """Whether auto-cpufreq has enough state for a safe write."""
        return self.writable and self.current is not None

    @property
    def providers(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                device.provider
                for device in self.devices
                if device.provider
            )
        )

    @property
    def provider_states(self) -> tuple[tuple[str, str | None], ...]:
        return tuple(
            (device.provider, device.profile)
            for device in self.devices
            if device.provider
        )

    @property
    def status(self) -> str:
        if not self.devices:
            return "unavailable"
        if any(device.profile is None for device in self.devices):
            return "partial"
        if not self.writable:
            return "read-only"
        return "available"


def summarize_platform_profile_devices(
    devices: Iterable[PlatformProfileDevice],
) -> tuple[str | None, tuple[str, ...]]:
    devices = tuple(devices)
    if not devices or any(device.profile is None for device in devices):
        current = None
    else:
        profiles = [device.profile for device in devices]
        current = (
            profiles[0]
            if len(set(profiles)) == 1
            else "custom"
        )

    providers = tuple(
        dict.fromkeys(
            device.provider
            for device in devices
            if device.provider
        )
    )
    return current, providers


class PlatformProfileManager:
    """Discover platform profiles through the class ABI with legacy fallback."""

    def __init__(
        self,
        class_root: Path = PLATFORM_PROFILE_CLASS_ROOT,
        legacy_profile: Path = LEGACY_PLATFORM_PROFILE,
        legacy_choices: Path = LEGACY_PLATFORM_PROFILE_CHOICES,
    ):
        self.class_root = Path(class_root)
        self.legacy_profile = Path(legacy_profile)
        self.legacy_choices = Path(legacy_choices)

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            return path.read_text().strip()
        except OSError:
            return None

    @classmethod
    def _read_choices_state(
        cls,
        path: Path,
    ) -> tuple[tuple[str, ...], bool]:
        value = cls._read(path)
        if value is None:
            return (), False
        return tuple(value.split()), True

    @staticmethod
    def _without_aggregate_custom(
        choices: Iterable[str],
    ) -> tuple[str, ...]:
        return tuple(choice for choice in choices if choice != "custom")

    @staticmethod
    def _common_choices(
        devices: tuple[PlatformProfileDevice, ...],
    ) -> tuple[str, ...]:
        if not devices:
            return ()

        common = set(devices[0].choices)
        for device in devices[1:]:
            common.intersection_update(device.choices)
        return tuple(
            choice
            for choice in devices[0].choices
            if choice in common
        )

    def _modern_paths(self) -> tuple[Path, ...]:
        try:
            paths = sorted(self.class_root.glob("platform-profile-*"))
        except OSError:
            return ()
        return tuple(path for path in paths if path.is_dir())

    def _devices_for_paths(
        self,
        modern_paths: tuple[Path, ...],
    ) -> tuple[PlatformProfileDevice, ...]:
        if modern_paths:
            devices = []
            for path in modern_paths:
                choices, choices_known = self._read_choices_state(
                    path / "choices"
                )
                devices.append(
                    PlatformProfileDevice(
                        provider=self._read(path / "name") or None,
                        profile=self._read(path / "profile") or None,
                        choices=choices,
                        profile_path=path / "profile",
                        choices_known=choices_known,
                    )
                )
            return tuple(devices)

        if not self.legacy_profile.exists():
            return ()

        choices, choices_known = self._read_choices_state(
            self.legacy_choices
        )
        return (
            PlatformProfileDevice(
                provider=None,
                profile=self._read(self.legacy_profile) or None,
                choices=choices,
                profile_path=self.legacy_profile,
                choices_known=choices_known,
            ),
        )

    def _current_for(
        self,
        modern_paths: tuple[Path, ...],
        devices: tuple[PlatformProfileDevice, ...],
    ) -> str | None:
        if len(modern_paths) > 1 and self.legacy_profile.exists():
            aggregate = self._read(self.legacy_profile)
            if aggregate:
                return aggregate

        current, _ = summarize_platform_profile_devices(devices)
        return current

    def _available_choices_state_for(
        self,
        modern_paths: tuple[Path, ...],
        devices: tuple[PlatformProfileDevice, ...],
    ) -> tuple[tuple[str, ...], bool]:
        if len(modern_paths) > 1:
            legacy_choices, legacy_known = self._read_choices_state(
                self.legacy_choices
            )
            if legacy_known:
                return (
                    self._without_aggregate_custom(legacy_choices),
                    True,
                )
            if all(device.choices_known for device in devices):
                return (
                    self._without_aggregate_custom(
                        self._common_choices(devices)
                    ),
                    True,
                )
            return (), False

        if not devices:
            return (), False

        if len(modern_paths) == 1:
            # Prefer the class ABI. Only fall back when its choices attribute
            # could not be read; a readable empty choices file is authoritative
            # and is distinct from an unknown list.
            if devices[0].choices_known:
                return devices[0].choices, True
            legacy_choices, legacy_known = self._read_choices_state(
                self.legacy_choices
            )
            return (
                self._without_aggregate_custom(legacy_choices),
                legacy_known,
            )

        # The legacy aggregate ABI reports custom as state, but rejects it as
        # a write target. Do not advertise a value auto-cpufreq cannot set.
        return (
            self._without_aggregate_custom(devices[0].choices),
            devices[0].choices_known,
        )

    def _available_choices_for(
        self,
        modern_paths: tuple[Path, ...],
        devices: tuple[PlatformProfileDevice, ...],
    ) -> tuple[str, ...]:
        choices, _ = self._available_choices_state_for(
            modern_paths,
            devices,
        )
        return choices

    def _control_path_for(
        self,
        modern_paths: tuple[Path, ...],
    ) -> Path | None:
        if len(modern_paths) == 1:
            profile_path = modern_paths[0] / "profile"
            return profile_path if profile_path.exists() else None
        if len(modern_paths) > 1:
            return self.legacy_profile if self.legacy_profile.exists() else None
        return self.legacy_profile if self.legacy_profile.exists() else None

    def devices(self) -> tuple[PlatformProfileDevice, ...]:
        modern_paths = self._modern_paths()
        return self._devices_for_paths(modern_paths)

    def current(self) -> str | None:
        modern_paths = self._modern_paths()
        devices = self._devices_for_paths(modern_paths)
        return self._current_for(modern_paths, devices)

    def available_choices(self) -> tuple[str, ...]:
        modern_paths = self._modern_paths()
        devices = self._devices_for_paths(modern_paths)
        return self._available_choices_for(modern_paths, devices)

    def providers(self) -> tuple[str, ...]:
        _, providers = summarize_platform_profile_devices(self.devices())
        return providers

    def control_path(self) -> Path | None:
        return self._control_path_for(self._modern_paths())

    def snapshot(self) -> PlatformProfileSnapshot:
        modern_paths = self._modern_paths()
        devices = self._devices_for_paths(modern_paths)
        available_profiles, choices_known = (
            self._available_choices_state_for(
                modern_paths,
                devices,
            )
        )
        control_path = self._control_path_for(modern_paths)
        control_current = (
            self._read(control_path)
            if control_path is not None
            else None
        )
        return PlatformProfileSnapshot(
            devices=devices,
            interface=(
                "modern"
                if modern_paths
                else "legacy"
                if devices
                else "none"
            ),
            current=self._current_for(modern_paths, devices),
            available_profiles=available_profiles,
            choices_known=choices_known,
            writable=(
                control_path is not None
                and bool(control_current)
                and choices_known
                and bool(available_profiles)
            ),
        )

    def supported(self) -> bool:
        return bool(self.devices())


platform_profile = PlatformProfileManager()
