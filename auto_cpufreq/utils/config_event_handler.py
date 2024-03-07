import pyinotify

class ConfigEventHandler(pyinotify.ProcessEvent):
    def __init__(self, config) -> None:
        self.config = config

    # activates when file is modified
    def process_IN_MODIFY(self, event: pyinotify.Event) -> None:
        if event.pathname.rstrip("~") == self.config.path:
            self.config.update_config()
            print("file modified")

    # activates when file is deleted
    def process_IN_DELETE(self, event: pyinotify.Event) -> None:
        if event.pathname.rstrip("~") == self.config.path:
            self.config.update_config()
            print("File deleted")
    
    # activates when file is created
    def process_IN_CREATE(self, event: pyinotify.Event) -> None:
        if event.pathname.rstrip("~") == self.config.path:
            self.config.update_config()
            print("File created")