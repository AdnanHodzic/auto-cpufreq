from enum import Enum
from subprocess import getoutput
from typing import Callable

from auto_cpufreq.globals import GITHUB, ID, IS_INSTALLED_WITH_SNAP
from auto_cpufreq.prints import print_info, print_warning_block

class ServiceCommand(str, Enum):
    disable = 'disable'
    enable = 'enable'
    start = 'start'
    status = 'status'
    stop = 'stop'

def _init_system(init_system_command:str, service_command:ServiceCommand, service:str) -> None:
    print_info(getoutput(f'{init_system_command} {service_command.value} {service}'))

def _touch_or_rm(service_command:ServiceCommand) -> str: return 'touch' if service_command is ServiceCommand.disable else 'rm'

def dinit(service_command:ServiceCommand, service:str) -> None: _init_system('dinitctl', service_command, service)

def openRC(service_command:ServiceCommand, service:str) -> None:
    if service_command is ServiceCommand.disable: print_info(getoutput('rc-update del '+service))
    elif service_command is ServiceCommand.enable: print_info(getoutput('rc-update add '+service))
    else: print_info(getoutput(f'rc-service {service} {service_command.value}'))

def runit(service_command:ServiceCommand, service:str):
    if service_command is ServiceCommand.disable or service_command is ServiceCommand.enable:
        getoutput(
            _touch_or_rm(service_command)+('/var' if ID == 'void' else '/run/runit')+f' /service/{service}/down'
        )
        print_info(ServiceCommand.value.title(), service)
    else: _init_system('sv', service_command, service)

def systemd(service_command:ServiceCommand, service:str) -> None: _init_system('systemctl', service_command, service)

def s6(service_command:ServiceCommand, service:str) -> None:
    if service_command is ServiceCommand.disable or service_command is ServiceCommand.enable:
        getoutput(_touch_or_rm(service_command)+' /etc/s6/adminsv/default/contents.d/'+service)
        print_info(ServiceCommand.value.title(), service)
        print_info(getoutput('s6-db-reload'))
    elif service_command is ServiceCommand.start or service_command is ServiceCommand.stop:
        print_info(getoutput(f's6-rc -{"u" if service_command is ServiceCommand.start else "d"} change '+service))
    elif service_command is ServiceCommand.status:
        print_info(getoutput('s6-svstat /run/service/'+service))

def _get_init_system() -> Callable|None:
    warning_msg = 'Unsupported init system detected'
    if IS_INSTALLED_WITH_SNAP: return None
    init_system = getoutput('ps h -o comm 1')
    if init_system in ('dinit', 'systemd'): return globals()[init_system]
    if init_system == 'init': return openRC
    if init_system == 'runit':
        if ID in ('artix', 'debian', 'devuan', 'void'): return runit
        warning_msg = 'Runit init system detected but your distro is not supported'
    if init_system == 's6-svscan': return s6
    print_warning_block('Init system', warning_msg, f'Please open an issue on {GITHUB}/issues')
    return None

INIT_SYSTEM = _get_init_system()