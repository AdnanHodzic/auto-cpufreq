import os
import pyinotify

class ConfigEventHandler(pyinotify.ProcessEvent):
    def __init__(self, config) -> None:
        self.config = config

    def process_IN_MODIFY(self, event: pyinotify.Event) -> None:
        if event.pathname.rstrip("~") == self.config.path:
            self.config.update_config()