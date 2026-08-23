from pyinotify import Event, ProcessEvent


class ConfigEventHandler(ProcessEvent):
    def __init__(self, config) -> None:
        self.config = config

    def _process_update(self, event: Event):
        if event.pathname == self.config.path:
            self.config.update_config()

    def process_IN_CLOSE_WRITE(self, event: Event) -> None:
        self._process_update(event)

    def process_IN_DELETE(self, event: Event) -> None:
        self._process_update(event)

    def process_IN_MOVED_TO(self, event: Event) -> None:
        self._process_update(event)
