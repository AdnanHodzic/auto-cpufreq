#!/usr/bin/env python3
import os
import subprocess
from auto_cpufreq.core import root_check


def set_battery(value, mode, bat):
    file_path = f'/sys/class/power_supply/BAT{bat}/charge_{mode}_threshold'
    try:
        subprocess.check_output(f"echo {value} | tee /sys/class/power_supply/BAT{bat}/charge_{mode}_threshold", shell=True, text=True)
    except Exception as e:
        print(f"Error writing to {file_path}: {e}")


def thinkpad_setup(start_threshold, stop_threshold):
    root_check()
    battery_count = len([name for name in os.listdir("/sys/class/power_supply/") if name.startswith('BAT')])
    for bat in range(battery_count):
        set_battery(start_threshold, "start", bat)
        set_battery(stop_threshold, "stop", bat)


def thinkpad_print_thresholds():
    root_check()
    battery_count = len([name for name in os.listdir(
        "/sys/class/power_supply/") if name.startswith('BAT')])
    print(f"number of batteries = {battery_count}")
    for b in range(battery_count):
        try:
            with open(f'/sys/class/power_supply/BAT{b}/charge_start_threshold', 'r') as f:
                print(f'battery{b} start threshold is set to {f.read()}')
                f.close()

            with open(f'/sys/class/power_supply/BAT{b}/charge_stop_threshold', 'r') as f:
                print(f'battery{b} stop threshold is set to {f.read()}')
                f.close()

        except Exception as e:
            print(f"Error reading battery thresholds: {e}")
