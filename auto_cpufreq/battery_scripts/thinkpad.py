#!/usr/bin/env python3
import os


def thinkpad_setup(start_threshold, stop_threshold):

    # check if thinkpad_acpi is enabled if not this wont work
    if os.system("lsmod | grep thinkpad_acpi") is not None:
        # this path is specific to thinkpads
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


# this is for testing and debuging

def thinkpad_print_thresholds():
    path_to_bats = '/sys/class/power_supply/'
    battery_count = len([name for name in os.listdir(path_to_bats) if name.startswith('BAT')])

    for b in range(battery_count):

        try:
            with open(f'{path_to_bats}BAT{b}/charge_start_threshold', 'r') as f:
                print(f'BAT{b} start is set to {f.read()}')
                f.close()

            with open(f'{path_to_bats}BAT{b}/charge_stop_threshold', 'r') as f:
                print(f'BAT{b} stop is set to {f.read()}')
                f.close()

        except Exception as e:
            print(f"Error reading battery thresholds: {e}")