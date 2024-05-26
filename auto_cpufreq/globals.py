from os import cpu_count, getenv, path
from subprocess import getoutput
from sys import argv

APP_NAME = 'python3 power_helper.py' if argv[0] == 'power_helper.py' else 'auto-cpufreq'
AVAILABLE_SHELLS = {
    'bash': '.bashrc',
    'fish': '.config/fish/completions/auto-cpufreq.fish',
    'zsh': '.zshrc'
}
CPUS = cpu_count()
GITHUB = 'https://github.com/AdnanHodzic/auto-cpufreq'
IS_INSTALLED_WITH_AUR = path.isfile('/etc/arch-release') and bool(getoutput('pacman -Qs auto-cpufreq'))
IS_INSTALLED_WITH_SNAP = getenv('PKG_MARKER') == 'SNAP'

GOVERNOR_OVERRIDE_FILE = '/'+('var/snap/auto-cpufreq/current' if IS_INSTALLED_WITH_SNAP else 'opt/auto-cpufreq')+'/override.pickle'
USER_HOME_DIR = getoutput('getent passwd ${SUDO_USER:-$USER} | cut -d: -f6')+'/'

def _get_app_version() -> str:
    if IS_INSTALLED_WITH_SNAP: return getoutput(r'echo \(Snap\) $SNAP_VERSION')
    if IS_INSTALLED_WITH_AUR: return getoutput('pacman -Qs auto-cpufreq').split()[1]

    from importlib.metadata import metadata
    nb_version, _, git_version = metadata('auto-cpufreq')['Version'].partition('+')
    return f'{nb_version} (git {git_version})'

APP_VERSION = _get_app_version()

def _service_is_running(service:str) -> bool: return bool(getoutput(f'ps -ef | grep -E "{service}" | sed "/grep/d"'))

AUTO_CPUFREQ_DAEMON_IS_RUNNING = (
    _service_is_running('|'.join(map(lambda opt:'auto-cpufreq -'+opt, ('d', '-daemon')))) or
    (IS_INSTALLED_WITH_SNAP and getoutput('snapctl get daemon') == 'enabled')
)
POWER_PROFILES_DAEMON_IS_RUNNING = _service_is_running('power-profiles-daemon')

def _get_available_governors_sorted() -> tuple[str]:
    avail_gov = set(getoutput('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors').split(' '))
    return tuple(filter(lambda gov: gov in avail_gov, ('performance', 'ondemand', 'conservative', 'schedutil', 'userspace', 'powersave')))

AVAILABLE_GOVERNORS = _get_available_governors_sorted() # from the highest performance to the lowest

def _get_distro_and_id() -> tuple[str, str]:
    def extract_value(line:str) -> str: return line.split('=', 1)[-1].strip('"')
    dist, vers, id = '', '', ''
    for line in getoutput('cat '+('/var/lib/snapd/hostfs' if IS_INSTALLED_WITH_SNAP else '')+'/etc/os-release').splitlines():
        if dist and vers and id: break
        if line.startswith('NAME='): dist = extract_value(line)
        elif line.startswith('VERSION='): vers = extract_value(line)
        elif line.startswith('ID='): id = extract_value(line)
    if dist or vers: dist = f'{dist} {vers}'

    return (dist if dist else 'UNKNOWN', id if id else 'UNKNOWN')

DISTRO, ID = _get_distro_and_id()