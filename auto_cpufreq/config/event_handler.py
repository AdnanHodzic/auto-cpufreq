from pyinotify import Event, ProcessEvent

class ConfigEventHandler(ProcessEvent):
    def __init__(self, config) -> None: self.config = config

    # activates when auto-cpufreq config file is deleted
    def process_IN_DELETE_SELF(self, event:Event) -> None: self.config.set_file(None)

    # activates when auto-cpufreq config file is modified
    def process_IN_MODIFY(self, event:Event) -> None: self.config.update_config()

    # activates when auto-cpufreq config file is moved
    def process_IN_MOVE_SELF(self, event:Event) -> None: self.config.set_file(None)