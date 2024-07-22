from configparser import ConfigParser, ParsingError
from os import getenv, path
from pyinotify import ThreadedNotifier, WatchManager
from subprocess import getoutput

from auto_cpufreq.config.event_handler import ConfigEventHandler, MASK

def find_config_file(args_config_file) -> str:
    if args_config_file is not None:
        if path.isfile(args_config_file): return args_config_file    # (1) Command line argument was specified
        print(f'Error: Config file specified with "--config {args_config_file}" not found.')
        exit(1)

    user_config_path = getenv('XDG_CONFIG_HOME', default=getoutput('getent passwd ${SUDO_USER:-$USER} | cut -d: -f6')+'/.config')
    for dir in ('', '/auto-cpufreq'):
        conf_file = user_config_path+dir+'/auto-cpufreq.conf'
        if path.isfile(conf_file): return conf_file                  # (2) User config file
    
    system_config_file = '/etc/auto-cpufreq.conf'
    if path.isfile(system_config_file): return system_config_file    # (3) System config file (default if nothing else is found)
    print('Error: No config file found')
    exit(1)

class Config:
    conf:ConfigParser = None
    file:str = ""

    def get_option(self, section:str, option:str) -> str: return self.conf[section][option]

    def has_option(self, section:str, option:str) -> bool: return self.conf.has_option(section, option)

    def set_file(self, file:str):
        self.file = file
        print(f"Info: Using settings defined in {file} file")
        self.update_config()
        if self.auto_reload: self.watch_manager.add_watch(path.dirname(file), mask=MASK)
        
    def setup(self, args_config_file:str, auto_reload:bool) -> None:
        self.auto_reload = auto_reload
        if self.auto_reload:    # check for file changes using threading
            self.watch_manager: WatchManager = WatchManager()
            self.notifier: ThreadedNotifier = ThreadedNotifier(self.watch_manager, ConfigEventHandler(self))
            self.notifier.start()

        self.set_file(find_config_file(args_config_file))

    def stop_notifier(self) -> None:
        if self.auto_reload: self.notifier.stop()
    
    def update_config(self) -> None:
        self.conf = ConfigParser()      # create new ConfigParser to prevent old data from remaining
        try: self.conf.read(self.file)
        except ParsingError as e: print(f"The following error occured while parsing the config file: \n{repr(e)}")