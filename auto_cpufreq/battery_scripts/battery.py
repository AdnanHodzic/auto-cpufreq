#!/usr/bin/env python3
from subprocess import PIPE, run

from auto_cpufreq.battery_scripts.asus import AsusBatteryDevice
from auto_cpufreq.battery_scripts.ideapad_laptop import IdeapadBatteryDevice
from auto_cpufreq.battery_scripts.shared import BatteryDevice


def lsmod(module):
    return (
        module in run(["lsmod"], stdout=PIPE, stderr=PIPE, text=True, shell=True).stdout
    )


def battery_get_thresholds():
    if lsmod("ideapad_acpi"):
        BatteryDevice().print_thresholds()
    elif lsmod("ideapad_laptop"):
        IdeapadBatteryDevice().print_thresholds()
    elif lsmod("thinkpad_acpi"):
        BatteryDevice().print_thresholds()
    elif lsmod("asus_wmi"):
        AsusBatteryDevice.print_thresholds()
    else:
        return


def battery_setup():
    if lsmod("ideapad_acpi"):
        BatteryDevice().setup()
    elif lsmod("ideapad_laptop"):
        IdeapadBatteryDevice().setup()
    elif lsmod("thinkpad_acpi"):
        BatteryDevice().setup()
    elif lsmod("asus_wmi"):
        AsusBatteryDevice.setup()
    else:
        return
