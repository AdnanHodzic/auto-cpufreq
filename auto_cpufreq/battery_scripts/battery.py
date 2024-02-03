#!/usr/bin/env python3
import os
from auto_cpufreq.core import get_config

import auto_cpufreq.battery_scripts.thinkpad
import auto_cpufreq.battery_scripts.ideapad


def battery_start_threshold():
    conf = get_config()
    if conf.has_option("battery", "start_threshold"):
        start_threshold = conf["battery"]["start_threshold"]
        return start_threshold
    else:
        return


def battery_stop_threshold():
    conf = get_config()
    if conf.has_option("battery", "stop_threshold"):
        stop_threshold = conf["battery"]["stop_threshold"]
        return stop_threshold
    else:
        return


def battery_setup():
    conf = get_config()
    if conf.has_option("battery", "enable_thresholds") and conf["battery"]["enable_thresholds"] == "true":
        lsmod = os.system("lsmod")
        if lsmod.find("thinkpad_acpi") is not None:
            thinkpad.thinkpad_setup(battery_start_threshold(), battery_stop_threshold())
        elif lsmod.find("ideapad_acpi") is not None:
            ideapad.ideapad_setup(battery_start_threshold(), battery_stop_threshold())
        else:
            pass
    else:
        pass


# TODO
def battery_get_thresholds():
    conf = get_config()
    if conf["battery"]["enable_thresholds"] != "true":
        return
    lsmod = os.system("lsmod")
    if conf.has_option("battery", "enable_thresholds") and conf["battery"]["enable_thresholds"] == True:
        if lsmod.find("thinkpad_acpi") is not None:
            thinkpad.thinkpad_print_thresholds()
        elif lsmod.find("ideapad_acpi") is not None:
            ideapad.ideapad_print_thresholds()
        else:
            pass
    else:
        return
