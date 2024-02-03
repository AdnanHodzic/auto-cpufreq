import os
import thinkpad
import ideapad
from core import get_config


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
    if conf.has_option("battery", "enable_thresholds") && conf["battery"]["enable_thresholds"] == True:
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
