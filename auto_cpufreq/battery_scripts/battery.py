#!/usr/bin/env python3
import subprocess
from auto_cpufreq.core import get_config, root_check

from auto_cpufreq.battery_scripts.thinkpad import *
from auto_cpufreq.battery_scripts.ideapad import *


def lsmod(module):
    output = subprocess.run(
        ['lsmod'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if module in output.stdout:
        return True
    else:
        return False


def battery_start_threshold():
    conf = get_config()
    if conf.has_option("battery", "start_threshold"):
        start_threshold = conf["battery"]["start_threshold"]
        return int(start_threshold)
    else:
        return 0


def battery_stop_threshold():
    conf = get_config()
    if conf.has_option("battery", "stop_threshold"):
        stop_threshold = conf["battery"]["stop_threshold"]
        return int(stop_threshold)
    else:
        return 100


def battery_setup():
    root_check()
    conf = get_config()
    if conf.has_option("battery", "enable_thresholds"):
        if conf["battery"]["enable_thresholds"] == "true":
            if lsmod("thinkpad_acpi"):
                thinkpad_setup(battery_start_threshold(),
                               battery_stop_threshold())
            elif lsmod("ideapad_acpi"):
                ideapad_setup(battery_start_threshold(),
                              battery_stop_threshold())
            else:
                pass
        else:
            pass
    else:
        pass


def battery_get_thresholds():
    conf = get_config()
    if conf.has_option("battery", "enable_thresholds"):
        if conf["battery"]["enable_thresholds"] == "true":
            print("-" * 30)
            if lsmod("thinkpad_acpi"):
                thinkpad_print_thresholds()
            elif lsmod("ideapad_acpi"):
                ideapad_print_thresholds()
            else:
                pass
        else:
            return
    else:
        return
