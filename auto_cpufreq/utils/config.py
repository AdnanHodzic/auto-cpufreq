from configparser import ConfigParser, ParsingError
from auto_cpufreq.utils.config_event_handler import ConfigEventHandler
import pyinotify
from subprocess import run, PIPE
import os
import sys

def find_config_file(args_config_file) -> str:
    """
    Find the config file to use.

    Look for a config file in the following priorization order:
    1. Command line argument
    2. User config file
    3. System config file

    :param args_config_file: Path to the config file provided as a command line argument
    :return: The path to the config file to use
    """
    # Prepare paths

    # use $SUDO_USER or $USER to get home dir since sudo can't access
    # user env vars
    home = run(["getent passwd ${SUDO_USER:-$USER} | cut -d: -f6"],
        shell=True,
        stdout=PIPE,
        universal_newlines=True
    ).stdout.rstrip()
    user_config_dir = os.getenv("XDG_CONFIG_HOME", default=os.path.join(home, ".config"))
    user_config_file = os.path.join(user_config_dir, "auto-cpufreq/auto-cpufreq.conf")
    system_config_file = "/etc/auto-cpufreq.conf"

    if args_config_file is not None:                                # (1) Command line argument was specified
        # Check if the config file path points to a valid file
        if os.path.isfile(args_config_file): return args_config_file
        else:
            # Not a valid file
            print(f"Config file specified with '--config {args_config_file}' not found.")
            sys.exit(1)
    elif os.path.isfile(user_config_file): return user_config_file  # (2) User config file
    else: return system_config_file                                 # (3) System config file (default if nothing else is found)

class _Config:
    def __init__(self) -> None:
        self.path: str = ""
        self._config: ConfigParser = ConfigParser()
        self.watch_manager: pyinotify.WatchManager = pyinotify.WatchManager()
        self.config_handler = ConfigEventHandler(self)

        # check for file changes using threading
        self.notifier: pyinotify.ThreadedNotifier = pyinotify.ThreadedNotifier(self.watch_manager, self.config_handler)
        
    def set_path(self, path: str) -> None:
        self.path = path
        mask = pyinotify.IN_CREATE | pyinotify.IN_DELETE | pyinotify.IN_MODIFY | pyinotify.IN_MOVED_FROM | pyinotify.IN_MOVED_TO
        self.watch_manager.add_watch(os.path.dirname(path), mask=mask)
        if os.path.isfile(path): self.update_config()

    def has_config(self) -> bool:
        return os.path.isfile(self.path)
    
    def get_config(self) -> ConfigParser:
        return self._config
    
    def update_config(self) -> None:
        # create new ConfigParser to prevent old data from remaining
        self._config = ConfigParser()
        try: self._config.read(self.path)
        except ParsingError as e: print(f"The following error occured while parsing the config file: \n{e}")

config = _Config()