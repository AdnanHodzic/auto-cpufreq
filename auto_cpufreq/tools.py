import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from auto_cpufreq.globals import IS_INSTALLED_WITH_SNAP


class ConditionalFormatter(logging.Formatter):
    """
    A custom formatter that applies different format strings based on record level.
    Shows file name and line number only for ERROR and CRITICAL levels.
    """

    def __init__(self) -> None:
        self.default_fmt = "%(asctime)s [%(levelname)s] [%(module)s] %(message)s"
        self.error_fmt = "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"

        super().__init__(fmt=self.default_fmt, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record) -> str:
        original_fmt: str = self._style._fmt

        if record.levelno >= logging.ERROR:
            self._style._fmt = self.error_fmt
        else:
            self._style._fmt = self.default_fmt

        result: str = super().format(record)

        self._style._fmt = original_fmt

        return result


file_handler = RotatingFileHandler(
    "/var/log/auto-cpufreq/app.log", 
    maxBytes=10*1024*1024, # 10MB
    encoding="utf-8"
)
file_handler.setFormatter(ConditionalFormatter())
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("[%(levelname)s] [%(module)s] %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        file_handler,
        stream_handler
    ],
)

def get_gov_override_path() -> Path:
    if IS_INSTALLED_WITH_SNAP:
        return Path("/var/snap/auto-cpufreq/current/override.pickle")
    else:
        return Path("/opt/auto-cpufreq/override.pickle")
