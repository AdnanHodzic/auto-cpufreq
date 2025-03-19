from enum import Enum


class ObserverEvent(Enum):
    POWER_SOURCE = "POWER_SOURCE"
    SYS_LOAD = "HIGH_SYS_LOAD"
    SYS_TEMP = "NORMAL_SYS_LOAD"


class GovernorOverrideOptions(Enum):
    POWERSAVE = "powersave"
    PERFORMANCE = "performance"
    RESET = "reset"


class CPUFrequences(Enum):
    MAX = "max_limit"
    MIN = "min_limit"


class PowerStates(Enum):
    AC = "ac"
    BATTERY = "battery"


class TempStates(Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class CPULoadStates(Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
