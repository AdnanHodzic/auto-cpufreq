from os import getenv, path
from subprocess import getoutput

ALL_GOVERNORS = ('performance', 'ondemand', 'conservative', 'schedutil', 'userspace', 'powersave') # from the highest performance to the lowest
AVAILABLE_GOVERNORS = getoutput('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors').split(' ')
AVAILABLE_GOVERNORS_SORTED = tuple(filter(lambda gov: gov in AVAILABLE_GOVERNORS, ALL_GOVERNORS))

CONSERVATION_MODE_FILE = "/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"
GITHUB = "https://github.com/AdnanHodzic/auto-cpufreq"
IS_INSTALLED_WITH_AUR = path.isfile("/etc/arch-release") and bool(getoutput("pacman -Qs auto-cpufreq"))
IS_INSTALLED_WITH_SNAP = getenv("PKG_MARKER") == "SNAP"
POWER_SUPPLY_DIR = "/sys/class/power_supply/"