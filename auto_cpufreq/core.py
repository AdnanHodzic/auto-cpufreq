#!/usr/bin/env python3
#
# auto-cpufreq - core functionality

import os, psutil, sys
from math import isclose
from pathlib import Path
from shutil import copy
from subprocess import getoutput, run, DEVNULL
from time import sleep

from auto_cpufreq.batteries import BATTERIES
from auto_cpufreq.config.config import CONFIG
from auto_cpufreq.globals import AVAILABLE_GOVERNORS, CPUS, GOVERNOR_OVERRIDE_FILE, IS_INSTALLED_WITH_SNAP
from auto_cpufreq.power_helper import *
from auto_cpufreq.prints import print_error, print_header, print_info, print_separator, print_suggestion, print_warning

# ToDo:
# - replace get system/CPU load from: psutil.getloadavg() | available in 5.6.2)

SCRIPTS_DIR = Path('/usr/local/share/auto-cpufreq/scripts/')

# powersave/performance system load thresholds
powersave_load_threshold = (75 * CPUS) / 100
performance_load_threshold = (50 * CPUS) / 100

auto_cpufreq_stats_file = None

auto_cpufreq_stats_path = Path('/var/snap/auto-cpufreq/current/auto-cpufreq.stats') if IS_INSTALLED_WITH_SNAP else Path('/var/run/auto-cpufreq.stats')

def file_stats():
    global auto_cpufreq_stats_file
    auto_cpufreq_stats_file = open(auto_cpufreq_stats_path, 'w')
    sys.stdout = auto_cpufreq_stats_file

def get_override() -> str:
    if os.path.isfile(GOVERNOR_OVERRIDE_FILE): return getoutput('cat '+GOVERNOR_OVERRIDE_FILE)
    else: return 'default'

# get and set state of turbo
def turbo(value:bool|None = None) -> bool:
    amd_pstate = Path('/sys/devices/system/cpu/amd_pstate/status')
    cpufreq = Path('/sys/devices/system/cpu/cpufreq/boost')
    p_state = Path('/sys/devices/system/cpu/intel_pstate/no_turbo')

    if amd_pstate.exists():
        if amd_pstate.read_text().strip() == 'active': print_info('CPU turbo is controlled by amd-pstate-epp driver')
        return False
    if cpufreq.exists():
        f = cpufreq
        inverse = False
    elif p_state.exists():
        f = p_state
        inverse = True
    else:
        print_warning('CPU turbo is not available')
        return False

    if value is not None:
        if inverse: value = not value
        try: f.write_text(f'{int(value)}\n')
        except PermissionError:
            print_warning('Changing CPU turbo is not supported.')
            return False

    return bool(int(f.read_text().strip())) ^ inverse

def get_turbo() -> None: print_info('Currently turbo boost is', 'on' if turbo() else 'off')
def set_turbo(value:bool) -> None:
    print_info('Setting turbo boost', 'on' if value else 'off')
    turbo(value)

def current_gov_msg():
    print('Currently using:', getoutput('cpufreqctl.auto-cpufreq --governor').strip().split(' ')[0], 'governor')

# deploy cpufreqctl script
def cpufreqctl():
    if not (IS_INSTALLED_WITH_SNAP or os.path.isfile('/usr/local/bin/cpufreqctl.auto-cpufreq')):
        copy(SCRIPTS_DIR / 'cpufreqctl.sh', '/usr/local/bin/cpufreqctl.auto-cpufreq')

# remove cpufreqctl.auto-cpufreq script
def cpufreqctl_restore():
    if not IS_INSTALLED_WITH_SNAP and os.path.isfile('/usr/local/bin/cpufreqctl.auto-cpufreq'):
        os.remove('/usr/local/bin/cpufreqctl.auto-cpufreq')

def deploy_daemon():
    print_header('Deploying auto-cpufreq as a daemon')
    
    cpufreqctl() # deploy cpufreqctl script func call
    set_bluetooth_at_boot(False) # turn off bluetooth on boot

    auto_cpufreq_stats_path.touch(exist_ok=True)

    print('\n* Deploy auto-cpufreq install script')
    copy(SCRIPTS_DIR / 'auto-cpufreq-install.sh', '/usr/local/bin/auto-cpufreq-install')

    print('\n* Deploy auto-cpufreq remove script')
    copy(SCRIPTS_DIR / 'auto-cpufreq-remove.sh', '/usr/local/bin/auto-cpufreq-remove')

    gnome_power_svc_disable()

    run(['/usr/local/bin/auto-cpufreq-install'])

# remove auto-cpufreq daemon
def remove_daemon():
    # check if auto-cpufreq is installed
    if not os.path.exists('/usr/local/bin/auto-cpufreq-remove'):
        print_error('auto-cpufreq daemon is not installed')
        exit(1)

    print_header('Removing auto-cpufreq daemon')

    set_bluetooth_at_boot(True) # turn on bluetooth on boot

    # output warning if gnome power profile is stopped
    gnome_power_rm_reminder()
    gnome_power_svc_enable()

    # run auto-cpufreq daemon remove script
    run(['/usr/local/bin/auto-cpufreq-remove'])

    # remove auto-cpufreq-remove
    os.remove('/usr/local/bin/auto-cpufreq-remove')

    # delete override pickle if it exists
    if os.path.isfile(GOVERNOR_OVERRIDE_FILE): os.remove(GOVERNOR_OVERRIDE_FILE)

    # delete stats file
    if auto_cpufreq_stats_path.exists():
        if auto_cpufreq_stats_file is not None: auto_cpufreq_stats_file.close()
        auto_cpufreq_stats_path.unlink()

    # restore original cpufrectl script
    cpufreqctl_restore()

# refresh countdown
def countdown(s:int):
    print('\nauto-cpufreq is about to refresh (press ctrl+c to quit)', end = '')

    # empty log file if size is larger then 10mb
    if auto_cpufreq_stats_file is not None:
        if os.path.getsize(auto_cpufreq_stats_path) >= 1e+7:
            auto_cpufreq_stats_file.seek(0)
            auto_cpufreq_stats_file.truncate(0)

    # auto-refresh counter
    for remaining in range(s, -1, -1):
        if remaining <= 3 and remaining >= 0: print('.', end='', flush=True)
        sleep(s/3)

    print('\nExecuted on:', getoutput('date'))

# get cpu usage + system load for (last minute)
def display_load():
    cpuload = psutil.cpu_percent(interval=1)# get CPU utilization as a percentage
    load1m = os.getloadavg()[0]             # get system/CPU load

    print(f'\nTotal CPU usage: {cpuload}%')
    print(f'Total system load: {load1m:.2f}')
    print(f'Average temp. of all cores: {avg_all_core_temp:.2f}°C \n')

    return cpuload, load1m

# get system load average 1m, 5m, 15m (equivalent to uptime)
def display_system_load_avg():
    print(' (load average: {:.2f}, {:.2f}, {:.2f})'.format(*os.getloadavg()))

# set minimum and maximum CPU frequencies
def set_frequencies():
    '''
    Sets frequencies:
     - if option is used in auto-cpufreq.conf: use configured value
     - if option is disabled/no conf file used: set default frequencies
    Frequency setting is performed only once on power supply change
    '''
    power_supply = 'charger' if BATTERIES.charging() else 'battery'

    # don't do anything if the power supply hasn't changed
    if (
        hasattr(set_frequencies, 'prev_power_supply')
        and power_supply == set_frequencies.prev_power_supply
    ): return
    
    set_frequencies.prev_power_supply = power_supply

    frequency = {
        'scaling_max_freq': {
            'cmdargs': '--frequency-max',
            'minmax': 'maximum',
        },
        'scaling_min_freq': {
            'cmdargs': '--frequency-min',
            'minmax': 'minimum',
        },
    }
    if not hasattr(set_frequencies, 'max_limit'): set_frequencies.max_limit = int(getoutput(f'cpufreqctl.auto-cpufreq --frequency-max-limit'))
    if not hasattr(set_frequencies, 'min_limit'): set_frequencies.min_limit = int(getoutput(f'cpufreqctl.auto-cpufreq --frequency-min-limit'))

    for freq_type in frequency.keys():
        value = None
        if not CONFIG.has_option(power_supply, freq_type):
            # fetch and use default frequencies
            if freq_type == 'scaling_max_freq':
                curr_freq = int(getoutput(f'cpufreqctl.auto-cpufreq --frequency-max'))
                value = set_frequencies.max_limit
            else:
                curr_freq = int(getoutput(f'cpufreqctl.auto-cpufreq --frequency-min'))
                value = set_frequencies.min_limit
            if curr_freq == value: continue

        try: frequency[freq_type]['value'] = value if value else int(CONFIG.get_option(power_supply, freq_type))
        except ValueError:
            print_error(f'Invalid value for "{freq_type}":', frequency[freq_type]['value'])
            exit(1)

        if not set_frequencies.min_limit <= frequency[freq_type]['value'] <= set_frequencies.max_limit:
            print_error(f'Given value for "{freq_type}" is not within the allowed frequencies {set_frequencies.min_limit}-{set_frequencies.max_limit} kHz')
            exit(1)

        # set the frequency
        print(f'Setting {frequency[freq_type]["minmax"]} CPU frequency to {round(frequency[freq_type]["value"]/1000)} Mhz')
        run(['cpufreqctl.auto-cpufreq', frequency[freq_type]['cmdargs'], f'--set={frequency[freq_type]["value"]}'])

# set powersave and enable turbo
def set_powersave():
    gov = CONFIG.get_option('battery', 'governor') if CONFIG.has_option('battery', 'governor') else AVAILABLE_GOVERNORS[-1]
    print(f'Setting to use: "{gov}" governor')

    if get_override() != 'default': print_warning('governor overwritten using `--force` flag.')
    run(['cpufreqctl.auto-cpufreq', '--governor', '--set='+gov])


    if not Path('/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference').exists():
        print('Not setting EPP (not supported by system)')
    else:
        dynboost_enabled = Path('/sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost').exists()

        if dynboost_enabled:
            dynboost_enabled = bool(int(
                getoutput('cat /sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost')
            ))

        if dynboost_enabled: print('Not setting EPP (dynamic boosting is enabled)')
        else:
            if CONFIG.has_option('battery', 'energy_performance_preference'):
                epp = CONFIG.get_option('battery', 'energy_performance_preference')
                run(['cpufreqctl.auto-cpufreq', '--epp', '--set='+epp])
                print(f'Setting to use: "{epp}" EPP')
            else:
                run(['cpufreqctl.auto-cpufreq', '--epp', '--set=balance_power'])
                print('Setting to use: "balance_power" EPP')
    # set frequencies
    set_frequencies()

    cpuload, load1m = display_load()

    # conditions for setting turbo in powersave
    auto = CONFIG.get_option('battery', 'turbo') if CONFIG.has_option('battery', 'turbo') else 'auto'

    if auto == 'always':
        print('Configuration file enforces turbo boost')
        set_turbo(True)
    elif auto == 'never':
        print('Configuration file disables turbo boost')
        set_turbo(False)
    else:
        if psutil.cpu_percent(percpu=False, interval=0.01) >= 30.0 or isclose(
            max(psutil.cpu_percent(percpu=True, interval=0.01)), 100
        ): print('High CPU load', end='')
        elif load1m > powersave_load_threshold: print('High system load', end='')
        else: print('Load optimal', end='')

        display_system_load_avg()

        if cpuload >= 20: set_turbo(True)   # high cpu usage trigger
        else:                               # set turbo state based on average of all core temperatures
            print(f'Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C')
            set_turbo(False)

    print_separator()

# make turbo suggestions in powersave
def mon_powersave():
    cpuload, load1m = display_load()

    if psutil.cpu_percent(percpu=False, interval=0.01) >= 30.0 or isclose(
        max(psutil.cpu_percent(percpu=True, interval=0.01)), 100
    ): print('High CPU load', end='')
    elif load1m > powersave_load_threshold: print('High system load', end='')
    else: print('Load optimal', end='')

    display_system_load_avg()

    if cpuload >= 20: print_suggestion('Set turbo boost on')# high cpu usage trigger
    else:                                                   # set turbo state based on average of all core temperatures
        print(f'Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C')
        print_suggestion('Set turbo boost off')

    get_turbo()
    print_separator()

# set performance and enable turbo
def set_performance():
    gov = CONFIG.get_option('charger', 'governor') if CONFIG.has_option('charger', 'governor') else AVAILABLE_GOVERNORS[0]

    print(f'Setting to use: "{gov}" governor')
    if get_override() != 'default': print_warning('governor overwritten using `--force` flag.')
    run(['cpufreqctl.auto-cpufreq', '--governor', '--set='+gov])

    if not os.path.isfile('/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference'):
        print('Not setting EPP (not supported by system)')
    else:
        if dynboost_enabled := Path('/sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost').exists():
            dynboost_enabled = bool(int(
                getoutput('cat /sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost')
            ))

        if dynboost_enabled: print('Not setting EPP (dynamic boosting is enabled)')
        else:
            intel_pstate_status_path = '/sys/devices/system/cpu/intel_pstate/status'

            if CONFIG.has_option('charger', 'energy_performance_preference'):
                epp = CONFIG.get_option('charger', 'energy_performance_preference')

                if Path(intel_pstate_status_path).exists() and open(intel_pstate_status_path, 'r').read().strip() == 'active' and epp != 'performance':
                    print_warning(f'"{epp}" EPP is not allowed in Intel CPU')
                    print('Overriding EPP to "performance"')
                    epp = 'performance'

                run(['cpufreqctl.auto-cpufreq', '--epp', '--set='+epp])
                print(f'Setting to use: "{epp}" EPP')
            else:
                if Path(intel_pstate_status_path).exists() and open(intel_pstate_status_path, 'r').read().strip() == 'active':
                    run(['cpufreqctl.auto-cpufreq', '--epp', '--set=performance'])
                    print('Setting to use: "performance" EPP')
                else:
                    run(['cpufreqctl.auto-cpufreq', '--epp', '--set=balance_performance'])
                    print('Setting to use: "balance_performance" EPP')

    # set frequencies
    set_frequencies()

    cpuload, load1m = display_load()

    auto = CONFIG.get_option('charger', 'turbo') if CONFIG.has_option('charger', 'turbo') else 'auto'

    if auto == 'always':
        print('Configuration file enforces turbo boost')
        set_turbo(True)
    elif auto == 'never':
        print('Configuration file disables turbo boost')
        set_turbo(False)
    else:
        if (
            psutil.cpu_percent(percpu=False, interval=0.01) >= 20.0
            or max(psutil.cpu_percent(percpu=True, interval=0.01)) >= 75
        ):
            print('High CPU load', end='')
            display_system_load_avg()
            if cpuload >= 20: set_turbo(True)   # high cpu usage trigger
            elif avg_all_core_temp >= 70:       # set turbo state based on average of all core temperatures
                print(f'Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C')
                set_turbo(False)
            else: set_turbo(True)
        elif load1m >= performance_load_threshold:
            print('High system load', end='')
            display_system_load_avg()
            if cpuload >= 20: set_turbo(True)   # high cpu usage trigger
            elif avg_all_core_temp >= 65:       # set turbo state based on average of all core temperatures
                print(f'Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C')
                set_turbo(False)
            else: set_turbo(True)
        else:
            print('Load optimal', end='')
            display_system_load_avg()
            if cpuload >= 20: set_turbo(True)   # high cpu usage trigger
            elif avg_all_core_temp >= 60:       # set turbo state based on average of all core temperatures
                print(f'Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C')
                set_turbo(False)
            else: set_turbo(False)

    print_separator()

# make turbo suggestions in performance
def mon_performance():
    cpuload, load1m = display_load()

    if (
        psutil.cpu_percent(percpu=False, interval=0.01) >= 20.0
        or max(psutil.cpu_percent(percpu=True, interval=0.01)) >= 75
    ):
        print('High CPU load', end='')
        display_system_load_avg()
        if cpuload >= 20: print_suggestion('Set turbo boost on')# high cpu usage trigger
        elif cpuload <= 25 and avg_all_core_temp >= 70:             # set turbo state based on average of all core temperatures
            print(f'Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C')
            print_suggestion('Set turbo boost off')
        else: print_suggestion('Set turbo boost on')
    elif load1m > performance_load_threshold:
        print('High system load', end='')
        display_system_load_avg()
        if cpuload >= 20: print_suggestion('Set turbo boost on')# high cpu usage trigger
        elif cpuload <= 25 and avg_all_core_temp >= 65:             # set turbo state based on average of all core temperatures
            print(f'Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C')
            print_suggestion('Set turbo boost off')
        else: print_suggestion('Set turbo boost on')
    else:
        print('Load optimal', end='')
        display_system_load_avg()
        if cpuload >= 20: print_suggestion('Set turbo boost on')# high cpu usage trigger
        elif cpuload <= 25 and avg_all_core_temp >= 60:             # set turbo state based on average of all core temperatures
            print(f'Optimal total CPU usage: {cpuload}%, high average core temp: {avg_all_core_temp}°C')
            print_suggestion('Set turbo boost off')
        else: print_suggestion('Set turbo boost on')

    get_turbo()
    print_separator()

def set_autofreq():
    '''
    set cpufreq governor based if device is charging
    '''
    print_header('CPU frequency scaling')

    # determine which governor should be used
    override = get_override()
    if override == 'powersave': set_powersave()
    elif override == 'performance': set_performance()
    elif BATTERIES.charging():
        print('Battery is charging\n')
        set_performance()
    else:
        print('Battery is discharging\n')
        set_powersave()

def mon_autofreq():
    print_header('CPU frequency scaling')

    # determine which governor should be used
    if BATTERIES.charging():
        print('Battery is charging\n')
        current_gov_msg()
        print_suggestion(f'Use of "{AVAILABLE_GOVERNORS[0]}" governor')
        mon_performance()
    else:
        print('Battery is discharging\n')
        current_gov_msg()
        print_suggestion(f'Use of "{AVAILABLE_GOVERNORS[-1]}" governor')
        mon_powersave()

# read stats func
def read_stats():
    if os.path.isfile(auto_cpufreq_stats_path): run(['tail', '-n 50', '-f', str(auto_cpufreq_stats_path)], stderr=DEVNULL)
    print_separator()

def sysinfo():
    '''
    get system information
    '''
    # psutil current freq not used, gives wrong values with offline cpu's
    minmax_freq_per_cpu = psutil.cpu_freq(percpu=True)

    # max and min freqs, psutil reports wrong max/min freqs with offline cores with percpu=False
    print_header('Current CPU stats')
    print(f'CPU max frequency: {max([freq.max for freq in minmax_freq_per_cpu]):.0f} MHz')
    print(f'CPU min frequency: {min([freq.min for freq in minmax_freq_per_cpu]):.0f} MHz\n')

    # get coreid's and frequencies of online cpus by parsing /proc/cpuinfo
    coreid_info = getoutput('grep -E "processor|cpu MHz|core id" /proc/cpuinfo').splitlines()
    cpu_core = dict()
    freq_per_cpu = []
    for i in range(0, len(coreid_info), 3):
        # ensure that indices are within the valid range, before accessing the corresponding elements
        if i + 1 < len(coreid_info): freq_per_cpu.append(float(coreid_info[i + 1].split(':')[-1]))
        else: continue # handle the case where the index is out of range
        # ensure that indices are within the valid range, before accessing the corresponding elements
        cpu = int(coreid_info[i].split(':')[-1])
        if i + 2 < len(coreid_info):
            core = int(coreid_info[i + 2].split(':')[-1])
            cpu_core[cpu] = core
        else: continue # handle the case where the index is out of range

    online_cpu_count = len(cpu_core)

    # temperatures
    temp_sensors = psutil.sensors_temperatures()
    temp_per_cpu = [float('nan')] * online_cpu_count
    try:
        # the priority for CPU temp is as follows: coretemp sensor -> sensor with CPU in the label -> acpi -> k10temp
        if 'coretemp' in temp_sensors:
            # list labels in 'coretemp'
            core_temp_labels = [temp.label for temp in temp_sensors['coretemp']]
            for i, cpu in enumerate(cpu_core):
                # get correct index in temp_sensors
                core = cpu_core[cpu]
                cpu_temp_index = core_temp_labels.index(f'Core {core}')
                temp_per_cpu[i] = temp_sensors['coretemp'][cpu_temp_index].current
        else:
            # iterate over all sensors
            for sensor in temp_sensors:
                # iterate over all temperatures in the current sensor
                for temp in temp_sensors[sensor]:
                    if 'CPU' in temp.label and temp.current != 0:
                        temp_per_cpu = [temp.current] * online_cpu_count
                        break
                else: continue
                break
            else:
                for sensor in ('acpitz', 'k10temp', 'zenpower'):
                    if sensor in temp_sensors and temp_sensors[sensor][0].current != 0:
                        temp_per_cpu = [temp_sensors[sensor][0].current] * online_cpu_count
                        break
    except Exception as e: print(repr(e))

    print('Core\t Usage\tTemperature\tFrequency')
    for cpu, usage, freq, temp in zip(cpu_core, psutil.cpu_percent(interval=1, percpu=True), freq_per_cpu, temp_per_cpu):
        print(f'CPU{cpu}\t{usage:>5.1f}%\t{temp:>9.0f}°C\t{freq:>5.0f} MHz')

    if offline_cpus := [str(cpu) for cpu in range(CPUS) if cpu not in cpu_core]: print('\nDisabled CPUs:', ', '.join(offline_cpus))

    # get average temperature of all cores
    global avg_all_core_temp
    avg_all_core_temp = float(sum(temp_per_cpu) / online_cpu_count)

    # print current fan speed
    current_fans = list(psutil.sensors_fans())
    for current_fan in current_fans:
        print('\nCPU fan speed:', psutil.sensors_fans()[current_fan][0].current, 'RPM')