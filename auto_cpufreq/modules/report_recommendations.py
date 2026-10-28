"""Pure, read-only recommendations for frontend monitors.

A recommendation is not an instruction to apply a policy. The daemon and
Live mode continue to own all power-state changes independently.
"""
from dataclasses import dataclass
from enum import Enum
from math import isfinite


class RecommendationStatus(str, Enum):
    CHANGE = "change"
    NO_CHANGE = "no-change"
    UNAVAILABLE = "unavailable"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class Recommendation:
    status: RecommendationStatus
    current: str | bool | None = None
    target: str | bool | None = None

    @property
    def suggested(self):
        """Legacy monitor-friendly value, or None if action is not knowable."""
        if self.status in (RecommendationStatus.CHANGE,
                           RecommendationStatus.NO_CHANGE):
            return self.target
        return None

    @property
    def needs_change(self):
        return self.status is RecommendationStatus.CHANGE


@dataclass(frozen=True)
class ReportRecommendations:
    governor: Recommendation
    turbo: Recommendation


def governor_candidate(ac_plugged, available_governors):
    """Preserve the existing governor suggestion ordering.

    Unknown AC was historically treated like AC by the older helper. Only
    the new UI evaluation declines to recommend when power source is unknown.
    """
    if not available_governors:
        return None
    return (
        available_governors[0] if ac_plugged is not False
        else available_governors[-1]
    )


def turbo_candidate(cpu_usage, average_temperature):
    """Preserve the legacy 20% CPU threshold without an inert heat branch.

    The temperature argument remains for callers of the established API.
    Historically the temperature conditional also returned False, making
    its outcome identical to the final return.
    """
    return cpu_usage >= 20.0


def _current_and_candidate(current, target):
    if current is None:
        return Recommendation(RecommendationStatus.INDETERMINATE)
    return Recommendation(
        RecommendationStatus.NO_CHANGE if current == target
        else RecommendationStatus.CHANGE,
        current=current,
        target=target,
    )


def evaluate_recommendations(report, available_governors):
    """Evaluate one already collected SystemReport without further I/O."""
    battery = getattr(report, "battery_info", None)
    ac = getattr(battery, "is_ac_plugged", None)
    current_gov = getattr(report, "current_gov", None)
    if not available_governors:
        governor = Recommendation(
            RecommendationStatus.UNAVAILABLE, current=current_gov
        )
    elif ac is None or current_gov is None:
        governor = Recommendation(
            RecommendationStatus.INDETERMINATE, current=current_gov
        )
    else:
        governor = _current_and_candidate(
            current_gov, governor_candidate(ac, available_governors)
        )

    turbo_state = getattr(report, "is_turbo_on", (None, None))
    current_turbo, managed = turbo_state
    usage = getattr(report, "cpu_usage", None)
    if current_turbo is None:
        status = (
            RecommendationStatus.UNAVAILABLE
            if managed is not None else RecommendationStatus.INDETERMINATE
        )
        turbo = Recommendation(status)
    elif usage is None or not isinstance(usage, (int, float)) or not isfinite(usage):
        turbo = Recommendation(
            RecommendationStatus.INDETERMINATE, current=current_turbo
        )
    else:
        # Temperature is not required to decide below 20% load under
        # the existing suggestion rule; unknown temperature must never
        # be replaced with an invented reading.
        temp = getattr(report, "cpu_avg_temp", None)
        if temp is None:
            valid = [
                core.temperature
                for core in getattr(report, "cores_info", ())
                if getattr(core, "temperature", 0) > 0
            ]
            temp = sum(valid) / len(valid) if valid else 0.0
        turbo = _current_and_candidate(
            current_turbo, turbo_candidate(usage, temp)
        )
    return ReportRecommendations(governor=governor, turbo=turbo)
