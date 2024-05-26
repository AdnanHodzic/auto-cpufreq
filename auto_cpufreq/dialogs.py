import click, gi, psutil, pyinotify, requests
import platform as pl
from subprocess import getoutput

from auto_cpufreq.batteries import BATTERIES
from auto_cpufreq.globals import APP_VERSION, CPUS, DISTRO, GITHUB, IS_INSTALLED_WITH_SNAP, POWER_PROFILES_DAEMON_IS_RUNNING
from auto_cpufreq.init_system import INIT_SYSTEM
from auto_cpufreq.prints import print_block, print_info_block, print_warning_block

def app_version() -> None: print('auto-cpufreq version:', APP_VERSION)

def hardware_info() -> None:
    print_info_block(
        'Hardware',
        'Linux distro: '+DISTRO,
        'Linux kernel: '+pl.release(),
        'Init system: '+(INIT_SYSTEM.__name__ if INIT_SYSTEM else 'Unknown'),
        'Processor: '+getoutput('grep "model name" /proc/cpuinfo -m 1').split(': ', 1)[-1],
        f'Cores: {CPUS}',
        'Architecture: '+pl.machine(),
        'Driver: '+getoutput('cpufreqctl.auto-cpufreq --driver'),
        'Computer type: '+getoutput('dmidecode --string chassis-type'),
        f'Batteries amount: {len(BATTERIES.batteries)}'
    )

def head():
    print_block(
        'auto-cpufreq',
        'Automatic CPU speed & power optimizer for Linux',
        'auto-cpufreq version: '+APP_VERSION,
        f'Github: {GITHUB}'
    )

def python_info():
    def pkg_version(pkg) -> str: return f'{pkg.__name__} package version: {pkg.__version__}'
    print_info_block(
        'Python',
        'Python version: '+pl.python_version(),
        pkg_version(click),
        pkg_version(gi),
        pkg_version(pl),
        pkg_version(psutil),
        pkg_version(pyinotify),
        pkg_version(requests)
    )

def warning_running_service(service_name:str, service_detected:bool) -> None:
    if IS_INSTALLED_WITH_SNAP or service_detected:
        print_warning_block(
            ('Unable to detect if' if IS_INSTALLED_WITH_SNAP else 'Detected')+f' you are running {service_name} service!',
            'This daemon might interfere with auto-cpufreq which can lead to unexpected results.',
            f'We strongly encourage you to disable {service_name} unless you really know what you are doing.',
        )

def warning_power_profiles_daemon_service() -> None:
    warning_running_service('Power Profiles daemon', POWER_PROFILES_DAEMON_IS_RUNNING)

def warning_tlp_service() -> None:
    warning_running_service('TLP', len(getoutput('tlp-stat -s | grep State').split('enabled', 1)) > 1)