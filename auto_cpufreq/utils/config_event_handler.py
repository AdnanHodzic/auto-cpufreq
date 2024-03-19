import pyinotify

class ConfigEventHandler(pyinotify.ProcessEvent):
    def __init__(self, config) -> None:
        self.config = config

    def _process_update(self, event: pyinotify.Event):
        if event.pathname.rstrip("~") == self.config.path:
            self.config.update_config()

    # activates when file is modified
    def process_IN_MODIFY(self, event: pyinotify.Event) -> None:
        self._process_update(event)

    # activates when file is deleted
    def process_IN_DELETE_SELF(self, event: pyinotify.Event) -> None:
        self._process_update(event)

    # activates when file is created
    def process_IN_CREATE(self, event: pyinotify.Event) -> None:
        self._process_update(event)

    def process_IN_MOVED_FROM(self, event: pyinotify.Event) -> None:
        self._process_update(event)

    def process_IN_MOVED_TO(self, event: pyinotify.Event) -> None:
        self._process_update(event)