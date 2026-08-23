import os, pyinotify, sys
from configparser import ConfigParser, Error as ConfigError
from subprocess import run, PIPE
from typing import Optional

from auto_cpufreq.config.config_event_handler import ConfigEventHandler

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
        self.notifier: pyinotify.ThreadedNotifier = pyinotify.ThreadedNotifier(
            self.watch_manager,
            self.config_handler,
        )
        self._watched_directory: Optional[str] = None

    def set_path(self, path: str) -> None:
        self.path = os.path.abspath(path)
        directory = os.path.dirname(self.path)
        if directory != self._watched_directory:
            mask = (
                pyinotify.IN_CLOSE_WRITE
                | pyinotify.IN_DELETE
                | pyinotify.IN_MOVED_TO
            )
            self.watch_manager.add_watch(directory, mask=mask)
            self._watched_directory = directory
        self.update_config()

    def has_config(self) -> bool:
        return os.path.isfile(self.path)

    def get_config(self) -> ConfigParser:
        return self._config

    def update_config(self) -> bool:
        """Replace the active config only after a complete successful parse."""
        candidate = ConfigParser()
        if not self.path or not os.path.isfile(self.path):
            self._config = candidate
            return True

        try:
            with open(self.path, "r") as config_file:
                candidate.read_file(config_file)
        except (OSError, ConfigError) as error:
            print(
                "The following error occurred while reading the config file: "
                f"\n{error!r}"
            )
            return False

        self._config = candidate
        return True

config = _Config()
