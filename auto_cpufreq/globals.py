from os import getenv, path
from subprocess import getoutput

GITHUB = "https://github.com/AdnanHodzic/auto-cpufreq"
IS_INSTALLED_WITH_AUR = path.isfile("/etc/arch-release") and bool(getoutput("pacman -Qs auto-cpufreq"))
IS_INSTALLED_WITH_SNAP = getenv("PKG_MARKER") == "SNAP"