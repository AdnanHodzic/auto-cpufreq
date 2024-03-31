#!/usr/bin/env python3
import subprocess

from auto_cpufreq.battery_scripts.thinkpad import thinkpad_setup, thinkpad_print_thresholds
from auto_cpufreq.battery_scripts.ideapad_acpi import ideapad_acpi_setup, ideapad_acpi_print_thresholds
from auto_cpufreq.battery_scripts.ideapad_laptop import ideapad_laptop_setup, ideapad_laptop_print_thresholds


def lsmod(module):
    output = subprocess.run(
        ['lsmod'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
    if module in output.stdout:
        return True
    else:
        return False


def battery_setup():

    if lsmod("thinkpad_acpi"):
        thinkpad_setup()

    elif lsmod("ideapad_acpi"):
        ideapad_acpi_setup()

    elif lsmod("ideapad_laptop"):
        ideapad_laptop_setup()

    else:
        return


def battery_get_thresholds():
    if lsmod("thinkpad_acpi"):
        thinkpad_print_thresholds()

    elif lsmod("ideapad_acpi"):
        ideapad_acpi_print_thresholds()

    elif lsmod("ideapad_laptop"):
        ideapad_laptop_print_thresholds()

    else:
        return


