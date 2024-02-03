import os
import thinkpad
import ideapad


def battery_thresholds():
    return {0, 100}


def battery_setup():
    thresholds = battery_thresholds()
    lsmod = os.system("lsmod")
    if lsmod.find("thinkpad_acpi") is not None:
        thinkpad.thinkpad(thresholds[0], thresholds[1])
    elif lsmod.find("ideapad_acpi") is not None:
        ideapad.ideapad_setup(thresholds[0], thresholds[1])
