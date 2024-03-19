import pyinotify

class ConfigEventHandler(pyinotify.ProcessEvent):
    def __init__(self, config) -> None:
        self.config = config

    def _process_update(self, event: pyinotify.Event):
        if event.pathname.rstrip("~") == self.config.path:
            self.config.update_config()

    # activates when auto-cpufreq config file is modified
    def process_IN_MODIFY(self, event: pyinotify.Event) -> None:
        self._process_update(event)

    # activates when auto-cpufreq config file is deleted
    def process_IN_DELETE_SELF(self, event: pyinotify.Event) -> None:
        self._process_update(event)

    # activates when auto-cpufreq config file is created
    def process_IN_CREATE(self, event: pyinotify.Event) -> None:
        self._process_update(event)

    # activates when auto-cpufreq config file is moved from watched directory
    def process_IN_MOVED_FROM(self, event: pyinotify.Event) -> None:
        self._process_update(event)

    # activates when auto-cpufreq config file is moved into the watched directory
    def process_IN_MOVED_TO(self, event: pyinotify.Event) -> None:
        self._process_update(event)