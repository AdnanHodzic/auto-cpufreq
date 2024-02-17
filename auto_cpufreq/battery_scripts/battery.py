#!/usr/bin/env python3
import subprocess

from auto_cpufreq.battery_scripts.thinkpad import *
from auto_cpufreq.battery_scripts.ideapad import *
from auto_cpufreq.battery_scripts.ideapad_laptop import *


def lsmod(module):
    output = subprocess.run(
        ['lsmod'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if module in output.stdout:
        return True
    else:
        return False


def battery_setup():

    if lsmod("thinkpad_acpi"):
        thinkpad_setup()

    elif lsmod("ideapad_acpi"):
        ideapad_setup()

    elif lsmod("ideapad_laptop"):
        ideapad_laptop_setup()

    else:
        return


def battery_get_thresholds():
