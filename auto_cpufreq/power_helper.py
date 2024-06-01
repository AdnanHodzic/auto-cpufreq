# * add status as one of the available options
# * alert user on snap if detected and how to remove first time live/stats message starts
# * if daemon is disabled and auto-cpufreq is removed (snap) remind user to enable it back
import click
from os.path import isfile
from shutil import which
from subprocess import call, check_output, DEVNULL, STDOUT
from sys import argv

from auto_cpufreq.core import *
from auto_cpufreq.globals import APP_NAME, GITHUB, IS_INSTALLED_WITH_SNAP, POWER_PROFILES_DAEMON_IS_RUNNING
from auto_cpufreq.init_system import INIT_SYSTEM, ServiceCommand
from auto_cpufreq.prints import print_error, print_info, print_warning, print_warning_block

bluetooth_conf_file = '/etc/bluetooth/main.conf'
powerprofilesctl_exists = which('powerprofilesctl') is not None

# stops gnome >= 40 power profiles (live)
def gnome_power_stop_live():
    try: INIT_SYSTEM(ServiceCommand.stop, 'power-profiles-daemon')
    except: print_warning('Unable to stop power-profiles-daemon')

# starts gnome >= 40 power profiles (live)
def gnome_power_start_live():
    try: INIT_SYSTEM(ServiceCommand.start, 'power-profiles-daemon')
    except: print_warning('Unable to start power-profiles-daemon')

# enable gnome >= 40 power profiles (uninstall)
def gnome_power_svc_enable():
    try:
        INIT_SYSTEM(ServiceCommand.enable, 'power-profiles-daemon')
        INIT_SYSTEM(ServiceCommand.start, 'power-profiles-daemon')
    except:
        print('\nUnable to enable power profiles daemon')
        print('If this causes any problems, please submit an issue:')
        print(GITHUB+'/issues')

# gnome power profiles current status
def gnome_power_svc_status():
    try:
        print('* GNOME power profiles status')
        INIT_SYSTEM(ServiceCommand.status, 'power-profiles-daemon')
    except:
        print('\nUnable to see power profiles daemon status')
        print('If this causes any problems, please submit an issue:')
        print(GITHUB+'/issues')

def set_bluetooth_at_boot(auto_enable:bool) -> None:
    if IS_INSTALLED_WITH_SNAP:
        if auto_enable: bluetooth_on_notif_snap()
        else: bluetooth_notif_snap()
    elif isfile(bluetooth_conf_file):
        turn_str = ('on' if auto_enable else 'off')+' bluetooth on boot'
        print_info('Turn', turn_str)
        def bool_to_str(value:bool) -> str: return '|AutoEnable='+str(value).lower()
        try: check_output(f'sed -i -e "s{bool_to_str(not auto_enable)}{bool_to_str(auto_enable)}|" -e "s|#AutoEnable|AutoEnable|" '+bluetooth_conf_file, shell=True)
        except Exception as e: print_error('Unable to turn', turn_str, repr(e))
    else: print_info('Turn off bluetooth on boot [skipping] (package providing bluetooth access is not present)')

# turn off bluetooth on snap message
def bluetooth_notif_snap():
    print('\n* Unable to turn off bluetooth on boot due to Snap package restrictions!')
    print('\nSteps to perform this action using auto-cpufreq: power_helper script:')
    print('python3 power_helper.py --bluetooth_boot_off')

# turn off bluetooth on snap message
def bluetooth_on_notif_snap():
    print('\n* Unable to turn on bluetooth on boot due to Snap package restrictions!')
    print('\nSteps to perform this action using auto-cpufreq: power_helper script:')
    print('python3 power_helper.py --bluetooth_boot_on')

# gnome power removal reminder
def gnome_power_rm_reminder():
    if POWER_PROFILES_DAEMON_IS_RUNNING:
        print_warning_block(
            'Detected GNOME Power Profiles daemon service is stopped!',
            'This service will now be enabled and started again.'
        )

def gnome_power_rm_reminder_snap():
    print_warning_block(
        'Unable to detect state of GNOME Power Profiles daemon service!',
        'Now it is recommended to enable this service.',
        '\nSteps to perform this action using auto-cpufreq: power_helper script:',
        f'git clone {GITHUB}.git',
        'cd auto-cpufreq/auto_cpufreq',
        'python3 power_helper.py --gnome_power_enable',
        f'\nReference: {GITHUB}#configuring-auto-cpufreq'
    )

def disable_power_profiles_daemon():
    try:
        INIT_SYSTEM(ServiceCommand.disable, 'power-profiles-daemon')
        INIT_SYSTEM(ServiceCommand.stop, 'power-profiles-daemon')
    except:
        print('\nUnable to disable GNOME power profiles')
        print('If this causes any problems, please submit an issue:')
        print(GITHUB+'/issues')

# default gnome_power_svc_disable func (balanced)
def gnome_power_svc_disable():
    snap_pkg_check = 0
    if POWER_PROFILES_DAEMON_IS_RUNNING:
        try:
            # check if snap package installed
            snap_pkg_check = call('snap list | grep auto-cpufreq', shell=True, stderr=STDOUT, stdout=DEVNULL)
            # check if snapd is present and if snap package is installed | 0 is success
            if not bool(snap_pkg_check):
                print('GNOME Power Profiles Daemon is already disabled, it can be re-enabled by running:\n'
                    'sudo python3 power_helper.py --gnome_power_enable\n'
                )
            elif snap_pkg_check == 1:
                print('auto-cpufreq snap package not installed\nGNOME Power Profiles Daemon should be enabled. run:\n\n'
                    'sudo python3 power_helper.py --gnome_power_enable'
                )
        except:
            # snapd not found on the system
            print('There was a problem, could not determine GNOME Power Profiles Daemon')
            snap_pkg_check = 0

    if not POWER_PROFILES_DAEMON_IS_RUNNING and powerprofilesctl_exists:
        if snap_pkg_check == 1:
            print('auto-cpufreq snap package not installed.\nGNOME Power Profiles Daemon should be enabled, run:\n\n'
                'sudo python3 power_helper.py --gnome_power_enable'
            )
        else:
            print('auto-cpufreq snap package installed, GNOME Power Profiles Daemon should be disabled.\n')
            print('Using profile: ', 'balanced')
            call(['powerprofilesctl', 'set', 'balanced'])

            disable_power_profiles_daemon()

@click.command()
@click.option('--gnome_power_disable', is_flag=True, help='Disable GNOME Power profiles service')
@click.option('--gnome_power_enable', is_flag=True, help='Enable GNOME Power profiles service')
@click.option('--gnome_power_status', is_flag=True, help='Get status of GNOME Power profiles service')
@click.option('--bluetooth_boot_on', is_flag=True, help='Turn on Bluetooth on boot')
@click.option('--bluetooth_boot_off', is_flag=True, help='Turn off Bluetooth on boot')
def main(gnome_power_enable, gnome_power_disable, gnome_power_status, bluetooth_boot_off, bluetooth_boot_on):
    if len(argv) == 1: call([APP_NAME, '--help'])
    else:
        if gnome_power_enable: gnome_power_svc_enable()
        elif gnome_power_disable: gnome_power_svc_disable()
        elif gnome_power_status: gnome_power_svc_status()
        elif bluetooth_boot_off: set_bluetooth_at_boot(False)
        elif bluetooth_boot_on: set_bluetooth_at_boot(True)

if __name__ == '__main__': main()