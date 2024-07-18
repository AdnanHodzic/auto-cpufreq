from pyinotify import Event, ProcessEvent

class ConfigEventHandler(ProcessEvent):
    def __init__(self, config) -> None:
        self.config = config

    def _process_update(self, event: Event):
        if event.pathname.rstrip("~") == self.config.path: self.config.update_config()

    # activates when auto-cpufreq config file is modified
    def process_IN_MODIFY(self, event: Event) -> None: self._process_update(event)

    # activates when auto-cpufreq config file is deleted
    def process_IN_DELETE(self, event: Event) -> None: self._process_update(event)

    # activates when auto-cpufreq config file is created
    def process_IN_CREATE(self, event: Event) -> None: self._process_update(event)

    # activates when auto-cpufreq config file is moved from watched directory
    def process_IN_MOVED_FROM(self, event: Event) -> None: self._process_update(event)

    # activates when auto-cpufreq config file is moved into the watched directory
    def process_IN_MOVED_TO(self, event: Event) -> None: self._process_update(event)