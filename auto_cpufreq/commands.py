from os import getenv, path, remove
from subprocess import check_output, getoutput

from auto_cpufreq.batteries import BATTERIES
from auto_cpufreq.config.config import CONFIG
from auto_cpufreq.core import (
    auto_cpufreq_stats_file, auto_cpufreq_stats_path, countdown, cpufreqctl, current_gov_msg, deploy_daemon,
    file_stats, get_turbo, gnome_power_start_live, gnome_power_stop_live, mon_autofreq, remove_daemon, set_autofreq, sysinfo
)
from auto_cpufreq.dialogs import hardware_info, head, python_info, warning_power_profiles_daemon_service, warning_tlp_service
from auto_cpufreq.globals import (
    APP_NAME, AUTO_CPUFREQ_DAEMON_IS_RUNNING, AVAILABLE_SHELLS, GITHUB,
    GOVERNOR_OVERRIDE_FILE, IS_INSTALLED_WITH_AUR, IS_INSTALLED_WITH_SNAP, USER_HOME_DIR
)
from auto_cpufreq.power_helper import bluetooth_notif_snap, gnome_power_rm_reminder_snap
from auto_cpufreq.prints import print_block, print_error, print_info, print_separator
from auto_cpufreq.update import check_for_update, update

def check_auto_cpufreq_daemon_state(state_is_running:bool) -> None:
    if state_is_running ^ AUTO_CPUFREQ_DAEMON_IS_RUNNING:
        print_error(
            f'auto-cpufreq is{"" if AUTO_CPUFREQ_DAEMON_IS_RUNNING else " not"} running in daemon mode.',
            f'Make sure you {"stop" if AUTO_CPUFREQ_DAEMON_IS_RUNNING else "start"} the auto-cpufreq daemon before'
        )
        exit(1)

def completions_command() -> None:
    shell = path.basename(getenv('SHELL'))
    if not AVAILABLE_SHELLS.get(shell):
        print_error(f'Shell unavailable : {shell}, only available for', ', '.join(AVAILABLE_SHELLS))
        exit(1)

    print_info(shell, 'detected')
    try:
        check_output(f'echo "eval \'$(_AUTO_CPUFREQ_COMPLETE={shell}_source auto-cpufreq)\'" >> '+USER_HOME_DIR+AVAILABLE_SHELLS[shell], shell=True)
        print('You need to restart your shell to apply the modifications')
    except:
        print_error('Unable to add shell completions')
        exit(1)

def donnate_command() -> None:
    print_block(
        'Donate',
        'If auto-cpufreq helped you out and you find it useful...\n',
        'Show your appreciation by donating!',
        GITHUB+'#donate'
    )

def force_command(override:str) -> None:
    check_auto_cpufreq_daemon_state(True)
    if override == 'reset':
        if path.isfile(GOVERNOR_OVERRIDE_FILE): remove(GOVERNOR_OVERRIDE_FILE)
        print_info('Governor override removed')
    else:
        try:
            check_output(f'echo {override} | tee '+GOVERNOR_OVERRIDE_FILE, shell=True)
            print_info('Set governor override to '+override)
        except: print_error('Unable to set governor override')

def help_command() -> None:
    head()
    print('\nExample usage:')
    print('sudo', APP_NAME, '--monitor')
    print_block('auto-cpufreq help', getoutput(APP_NAME+' --help'))

def remove_command() -> None:
    if IS_INSTALLED_WITH_SNAP:
        try:
            check_output(['snapctl', 'set', 'daemon=disabled'])
            check_output(['snapctl', 'stop', '--disable', 'auto-cpufreq'])
        except: print_error('Unable to remove auto-cpufreq daemon with snapctl')
        if auto_cpufreq_stats_path.exists():
            if auto_cpufreq_stats_file is not None: auto_cpufreq_stats_file.close()
            auto_cpufreq_stats_path.unlink()
        gnome_power_rm_reminder_snap()
    else: remove_daemon()
    print('auto-cpufreq successfully removed')

def update_command() -> None:
    if IS_INSTALLED_WITH_SNAP:
        print('Detected auto-cpufreq was installed using snap')
        print('Please update using snap package manager, i.e: `sudo snap refresh auto-cpufreq`.')
    elif IS_INSTALLED_WITH_AUR:
        print('Detected auto-cpufreq was installed using AUR')
        print('Please update using your AUR helper.')
    elif check_for_update(): update()

def run_command(setup:bool, config_file:str|None = None) -> None:
    head()
    warning_power_profiles_daemon_service()
    warning_tlp_service()
    if setup:
        print()
        CONFIG.setup(config_file)
        BATTERIES.setup()

def daemon_command(config_file:str|None) -> None:
    run_command(True, config_file)
    print_info('Daemon started')
    file_stats()
    while True:
        try:
            BATTERIES.show_batteries_info()
            cpufreqctl()
            sysinfo()
            set_autofreq()
            countdown(2)
        except:
            print()
            CONFIG.notifier.stop()
            break

def debug_command() -> None:
    run_command(False)
    hardware_info()
    BATTERIES.show_batteries_info()
    python_info()
    cpufreqctl()
    sysinfo()
    print()
    current_gov_msg()
    get_turbo()
    print_separator()

def install_command():
    run_command(False)
    check_auto_cpufreq_daemon_state(False)
    if IS_INSTALLED_WITH_SNAP:
        bluetooth_notif_snap()
        try:
            check_output(['snapctl', 'set', 'daemon=enabled'])
            check_output(['snapctl', 'start', '--enable auto-cpufreq'])
        except:
            print_error('Unable to install auto-cpufreq daemon with snapctl')
            exit(1)
    else: deploy_daemon()
    print_block(
        'auto-cpufreq daemon installed and running',
        'To view live stats, run:\nauto-cpufreq --stats\n',
        'To disable and remove auto-cpufreq daemon, run:\nsudo auto-cpufreq --remove'
    )

def live_command(config_file:str|None) -> None:
    run_command(True, config_file)
    if not IS_INSTALLED_WITH_SNAP: gnome_power_stop_live()
    while True:
        try:
            check_auto_cpufreq_daemon_state(False)
            BATTERIES.show_batteries_info()
            cpufreqctl()
            sysinfo()
            set_autofreq()
            countdown(2)
        except:
            print()
            gnome_power_start_live()
            break
    CONFIG.notifier.stop()

def monitor_command(config_file:str|None) -> None:
    run_command(True, config_file)
    while True:
        try:
            check_auto_cpufreq_daemon_state(False)
            BATTERIES.show_batteries_info()
            cpufreqctl()
            sysinfo()
            mon_autofreq()
            countdown(2)
        except:
            print()
            break
    CONFIG.notifier.stop()