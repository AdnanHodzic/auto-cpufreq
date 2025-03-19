import logging
from subprocess import getoutput, run
import os

if not os.path.isdir('/var/log/auto-cpufreq'):
    os.mkdir('/var/log/auto-cpufreq')
    run(["chmod", "644", "-R", "/var/log/auto-cpufreq"], shell=True)
    run(["touch", "/var/log/auto-cpufreq/main.log"])
    run(["chmod", "644", "/var/log/auto-cpufreq/main.log"])

ALL_GOVERNORS = ('performance', 'ondemand', 'conservative', 'schedutil', 'userspace', 'powersave') # from the highest performance to the lowest
AVAILABLE_GOVERNORS = getoutput('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors').strip().split(' ')
AVAILABLE_GOVERNORS_SORTED = tuple(filter(lambda gov: gov in AVAILABLE_GOVERNORS, ALL_GOVERNORS))

CONSERVATION_MODE_FILE = "/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"
GITHUB = "https://github.com/AdnanHodzic/auto-cpufreq"
IS_INSTALLED_WITH_AUR = os.path.isfile("/etc/arch-release") and bool(getoutput("pacman -Qs auto-cpufreq"))
IS_INSTALLED_WITH_SNAP = os.getenv("PKG_MARKER") == "SNAP"
POWER_SUPPLY_DIR = "/sys/class/power_supply/"
SNAP_DAEMON_CHECK = getoutput("snapctl get daemon")

CPU_TEMP_SENSOR_PRIORITY = ("coretemp", "acpitz", "k10temp", "zenpower")

LOW_TEMP_THRESHOLD = 60
HIGH_TEMP_THRESHOLD = 85
LOW_LOAD_THRESHOLD = 10
HIGH_LOAD_THRESHOLD = 20

CPU_FREQ_MAX_LIMIT: None | int = None
CPU_FREQ_MIN_LIMIT: None | int = None

try:
    if CPU_FREQ_MAX_LIMIT is None:
        with open('/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq') as max:
            CPU_FREQ_MAX_LIMIT = int(max.read().strip())
    if CPU_FREQ_MIN_LIMIT is None:
        with open('/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq') as min:
            CPU_FREQ_MIN_LIMIT = int(min.read().strip())
except Exception as e:
    logging.error(f"Failed to get frequency limits: {e}")
