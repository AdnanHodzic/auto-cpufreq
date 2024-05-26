#!/usr/bin/env python3
from os.path import basename
from subprocess import check_output, getoutput

from auto_cpufreq.config.config import CONFIG
from auto_cpufreq.prints import print_info, print_info_block, print_warning

class Batteries:
    def __init__(self) -> None:
        self.batteries:tuple[str] = tuple(getoutput('find /sys/class/power_supply/BAT*').splitlines())
        self.charge_threshold_files:list[tuple[str, str]] = [] # charge_start_threshold, charge_stop_threshold
        for bat in self.batteries:
            charge_threshold_files = getoutput(f'find {bat}/ -type f -name "charge_*_threshold" | sort').splitlines()
            if len(charge_threshold_files) == 2: self.charge_threshold_files.append(tuple(charge_threshold_files))
        self.conservation_mode_files:tuple[str] = tuple(getoutput('find /sys/devices/ -type f -name conservation_mode').splitlines())

    def charging(self) -> bool: return any(map(lambda bat: getoutput(f'cat {bat}/status') == 'Charging', self.batteries))

    def setup(self) -> None:
        self.set_charge_threshold()
        if CONFIG.has_option('battery', 'conservation_mode'):
            self.set_conservation_mode(int(CONFIG.get_option('battery', 'conservation_mode') == 'true'))

    def set_charge_threshold(self) -> None:
        for charge_start_threshold_file, charge_stop_threshold_file in self.charge_threshold_files:
            _set_value_in_file(_get_threshold_value('start'), charge_start_threshold_file, 'charge start threshold')
            _set_value_in_file(_get_threshold_value('stop'), charge_stop_threshold_file, 'charge stop threshold')

    def set_conservation_mode(self, value:int) -> None:
        for conservation_mode_file in self.conservation_mode_files:
            _set_value_in_file(value, conservation_mode_file, 'conservation mode')

    def show_batteries_info(self) -> None:
        print_info_block(
            'Batteries',
            *(
                basename(bat)+'\n  '+
                _show_value_in_file(bat+'/manufacturer', 'Manufacturer')+'\n  '+
                _show_value_in_file(bat+'/model_name', 'Model name')+'\n  '+
                _show_value_in_file(bat+'/technology', 'Technology')+'\n  '+
                _show_value_in_file(bat+'/status', 'Status')+'\n  '+
                _show_value_in_file(bat+'/capacity', 'Capacity')+'\n'
                for bat in self.batteries
            ),
            *(_show_value_in_file(conservation_mode_file, 'Conservation mode', True) for conservation_mode_file in self.conservation_mode_files),
            *(
                _show_value_in_file(charge_start_threshold, 'Charge start threshold', True)+'\n'+
                _show_value_in_file(charge_stop_threshold, 'Charge stop threshold', True)
                for charge_start_threshold, charge_stop_threshold in self.charge_threshold_files
            ),
        )

def _get_threshold_value(mode:str) -> int:
    option = ('battery', mode+'_threshold')
    return int(CONFIG.get_option(*option)) if CONFIG.has_option(*option) else 100*int(mode != 'start')

def _set_value_in_file(value:object, file:str, role:str) -> None:
    str = f'{role} {value} in {file}'
    try:
        check_output(f'echo {value} | tee {file}', shell=True)
        print_info('Set', str)
    except: print_warning('Unable to set', str)

def _show_value_in_file(file:str, role:str, show_file_path:bool=False) -> str: return f'{role}: {getoutput("cat "+file)}\t{file*int(show_file_path)}'

BATTERIES = Batteries()