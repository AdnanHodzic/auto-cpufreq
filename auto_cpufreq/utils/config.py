from configparser import ConfigParser, ParsingError
from auto_cpufreq.utils.config_event_handler import ConfigEventHandler
import pyinotify
import os

class _Config:
    def __init__(self) -> None:
        self.path: str = ""
        self._config: ConfigParser = ConfigParser()
        self.watch_manager: pyinotify.WatchManager = pyinotify.WatchManager()
        self.config_handler = ConfigEventHandler(self)

        # check for file changes using threading
        notifier: pyinotify.ThreadedNotifierNotifier = pyinotify.ThreadedNotifier(
            self.watch_manager, self.config_handler)
        notifier.start()
        
    def set_path(self, path: str) -> None:
        self.path = path;
        mask = pyinotify.IN_CREATE | pyinotify.IN_DELETE | pyinotify.IN_MODIFY
        self.watch_manager.add_watch(os.path.dirname(path), mask=mask)
        if os.path.isfile(path):
            self.update_config()


    def has_config(self) -> bool:
        return os.path.isfile(self.path)
    
    def get_config(self) -> ConfigParser:
        return self._config
    
    def update_config(self) -> None:
        # create new ConfigParser to prevent old data from remaining
        self._config = ConfigParser()
        try:
            self._config.read(self.path)
        except ParsingError as e:
            print(f"The following error occured while parsing the config file: \n{e}")

config = _Config()