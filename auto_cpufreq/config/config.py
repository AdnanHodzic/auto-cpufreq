import pyinotify
from configparser import ConfigParser, ParsingError
from os import getenv, path

from auto_cpufreq.config.event_handler import ConfigEventHandler
from auto_cpufreq.globals import USER_HOME_DIR
from auto_cpufreq.prints import print_info, print_error

def find_config_file(args_config_file:str|None) -> str:
    if args_config_file is not None:
        if path.isfile(args_config_file): return args_config_file   # (1) Command line argument was specified
        print_error(f'Config file specified with "--config {args_config_file}" not found.')
        exit(1)

    user_config_path = getenv('XDG_CONFIG_HOME', default=USER_HOME_DIR+'.config')
    for dir in ('', '/auto-cpufreq'):
        if path.isfile(user_config_path+dir+'/auto-cpufreq.conf'):
            return user_config_path+dir+'/auto-cpufreq.conf'        # (2) User config file
    
    system_config_file = '/etc/auto-cpufreq.conf'
    if path.isfile(system_config_file): return system_config_file   # (3) System config file (default if nothing else is found)
    print_error('No config file found')
    exit(1)

class Config:
    file:str = ''
    config:ConfigParser|None = None

    def __init__(self) -> None:
        self.watch_manager:pyinotify.WatchManager = pyinotify.WatchManager()
        self.notifier:pyinotify.ThreadedNotifier = pyinotify.ThreadedNotifier(self.watch_manager, ConfigEventHandler(self))

    def get_option(self, section:str, option:str) -> str: return self.config[section][option]

    def has_option(self, section:str, option:str) -> bool: return self.config.has_option(section, option)

    def setup(self, args_config_file:str|None) -> None:
        self.set_file(args_config_file)
        self.notifier.start()
        
    def set_file(self, args_config_file:str|None) -> None:
        self.file = find_config_file(args_config_file)
        print_info('Using settings defined in', self.file)
        self.watch_manager.add_watch(self.file, pyinotify.IN_DELETE_SELF | pyinotify.IN_MODIFY | pyinotify.IN_MOVE_SELF)
        self.update_config()
    
    def update_config(self) -> None:
        self.config = ConfigParser() # create new ConfigParser to prevent old data from remaining
        try: self.config.read(self.file)
        except ParsingError as e: print_error('The following error occured while parsing the config file:', e)

CONFIG = Config()