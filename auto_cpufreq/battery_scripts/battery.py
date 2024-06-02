#!/usr/bin/env python3
import subprocess

from auto_cpufreq.battery_scripts.thinkpad import thinkpad_setup, thinkpad_print_thresholds
from auto_cpufreq.battery_scripts.ideapad_acpi import ideapad_acpi_setup, ideapad_acpi_print_thresholds
from auto_cpufreq.battery_scripts.ideapad_laptop import ideapad_laptop_setup, ideapad_laptop_print_thresholds

from auto_cpufreq.battery_scripts.thinkpad import thinkpad_set_fullcharge
from auto_cpufreq.battery_scripts.ideapad_acpi import ideapad_acpi_set_fullcharge
from auto_cpufreq.battery_scripts.ideapad_laptop import ideapad_laptop_set_fullcharge

from auto_cpufreq.utils.config import config
from auto_cpufreq.core import footer

def lsmod(module): return module in subprocess.run(['lsmod'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True).stdout

def battery_setup():
    if lsmod("thinkpad_acpi"): thinkpad_setup()
    elif lsmod("ideapad_acpi"): ideapad_acpi_setup()
    elif lsmod("ideapad_laptop"): ideapad_laptop_setup()
    else: return

def battery_get_thresholds():
    if lsmod("thinkpad_acpi"): thinkpad_print_thresholds()
    elif lsmod("ideapad_acpi"): ideapad_acpi_print_thresholds()
    elif lsmod("ideapad_laptop"): ideapad_laptop_print_thresholds()
    else: return

def fullcharge_thresholds():
    conf = config.get_config()
    if not (conf.has_option("battery", "enable_thresholds") and conf["battery"]["enable_thresholds"] == "true"): 
        print("\n" + "-" * 33 + " Fullcharge " + "-" * 34 + "\n")
        print("ERROR:\n\nCan only run this command if default start/stop thresholds are set in a config file!")
        footer()
        exit(1)
   
    if lsmod("thinkpad_acpi"): thinkpad_set_fullcharge()
    elif lsmod("ideapad_acpi"): ideapad_acpi_set_fullcharge()
    elif lsmod("ideapad_laptop"): ideapad_laptop_set_fullcharge()
    else: return