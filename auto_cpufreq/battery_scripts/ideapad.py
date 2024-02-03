#!/usr/bin/env python3
import os


def ideapad_setup(start_threshold, stop_threshold):
    # this path is specific to ideapads
    path_to_bats = '/sys/class/power_supply/'
    # gets the numb of batteries
    battery_count = len([name for name in os.listdir(path_to_bats) if name.startswith('BAT')])

    for b in range(battery_count):

        try:
            with open(f'{path_to_bats}BAT{b}/charge_start_threshold', 'w') as f:
                f.write(str(start_threshold) + '\n')
                f.close()

            with open(f'{path_to_bats}BAT{b}/charge_stop_threshold', 'w') as f:
                f.write(str(stop_threshold) + '\n')
                f.close()

        except Exception:
            pass


def ideapad_print_thresholds():
    path_to_bats = '/sys/class/power_supply/'
    battery_count = len([name for name in os.listdir(path_to_bats) if name.startswith('BAT')])
    print(f"number of batteries = {battery_count}")
    for b in range(battery_count):
        try:
            with open(f'{path_to_bats}BAT{b}/charge_start_threshold', 'r') as f:
                print(f'battery{b} start threshold is set to {f.read()}')
                f.close()

            with open(f'{path_to_bats}BAT{b}/charge_stop_threshold', 'r') as f:
                print(f'battery{b} stop threshold is set to {f.read()}')
                f.close()

        except Exception as e:
            print(f"Error reading battery thresholds: {e}")
