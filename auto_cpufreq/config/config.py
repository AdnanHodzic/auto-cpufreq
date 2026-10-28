"""Configuration selection, safe snapshots, and Linux file-change watches."""
import logging
import os
import pwd
import sys
import threading
from configparser import ConfigParser, Error as ConfigError

from auto_cpufreq.config.file_watcher import ConfigFileWatcher


_LOG = logging.getLogger(__name__)


def find_config_file(args_config_file) -> str:
    """Select explicit, user, then system configuration (unchanged order)."""
    # Match the pre-existing sudo/user precedence without changing daemon
    # policy or implicitly making the GUI user's file authoritative for root.
    username = os.environ.get("SUDO_USER") or os.environ.get("USER")
    try:
        home = (
            pwd.getpwnam(username).pw_dir
            if username else pwd.getpwuid(os.getuid()).pw_dir
        )
    except KeyError:
        home = pwd.getpwuid(os.getuid()).pw_dir
    user_config_dir = os.getenv(
        "XDG_CONFIG_HOME", default=os.path.join(home, ".config")
    )
    user_config_file = os.path.join(
        user_config_dir, "auto-cpufreq/auto-cpufreq.conf"
    )
    system_config_file = "/etc/auto-cpufreq.conf"

    if args_config_file is not None:
        if os.path.isfile(args_config_file):
            return args_config_file
        print(
            f"Config file specified with '--config {args_config_file}' not found."
        )
        sys.exit(1)
    if os.path.isfile(user_config_file):
        return user_config_file
    return system_config_file


class _Config:
    """Publish fully parsed snapshots; watch only in live CLI/daemon modes.

    A genuine removal restores defaults. Transient read/parse failures keep
    the last valid snapshot. The observer and all its descriptors are lazy.
    """

    def __init__(self) -> None:
        self.path: str = ""
        self._config: ConfigParser = ConfigParser()
        self._notifier = None
        self._reload_lock = threading.RLock()

    @property
    def notifier(self) -> ConfigFileWatcher:
        """Preserve the CLI's .notifier.start()/stop() lifecycle API."""
        if self._notifier is None:
            if not self.path:
                raise RuntimeError("Select a configuration path before watching")
            self._notifier = ConfigFileWatcher(self.path, self.update_config)
        return self._notifier

    def stop_watching(self) -> None:
        """Stop without allocating a watcher in read-only GUI/Stats modes."""
        if self._notifier is not None:
            self._notifier.stop()

    def set_path(self, path: str) -> None:
        selected = os.path.abspath(os.path.expanduser(path))
        with self._reload_lock:
            if self._notifier is not None:
                # A running observer must never silently keep the old pathname.
                self._notifier.set_path(selected)
            self.path = selected
            self.update_config()

    def has_config(self) -> bool:
        return bool(self.path) and os.path.isfile(self.path)

    def get_config(self) -> ConfigParser:
        # Readers retain their snapshot even if the notifier publishes a new
        # one concurrently; they never observe a parser being filled in place.
        return self._config

    def update_config(self) -> bool:
        # Serialize simultaneous callback and foreground reloads so a slow
        # earlier reader cannot publish over a newer completed reload.
        with self._reload_lock:
            return self._update_config_locked()

    def _update_config_locked(self) -> bool:
        if not self.path:
            return False
        replacement = ConfigParser()
        try:
            with open(self.path, "r", encoding="utf-8") as source:
                before = os.fstat(source.fileno())
                replacement.read_file(source)
                after = os.fstat(source.fileno())
            current = os.stat(self.path)
            # Reject a file being edited in place or atomically replaced
            # during a read: a parse without syntax errors is not enough to
            # establish that its bytes came from one complete revision.
            signature = lambda st: (
                st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns,
            )
            if (
                signature(before) != signature(after)
                or signature(after) != signature(current)
            ):
                _LOG.warning(
                    "Keeping previous configuration: %s changed during read",
                    self.path,
                )
                return False
        except FileNotFoundError:
            # File deleted or moved away: restore default settings, which is
            # what the original IN_DELETE / IN_MOVED_FROM callbacks did.
            if not os.path.lexists(self.path):
                # read_file() may already have populated replacement before
                # the path disappeared at the final stat().
                self._config = ConfigParser()
                return True
            _LOG.warning(
                "Cannot read configuration %s: missing target", self.path
            )
            return False
        except (OSError, UnicodeError, ConfigError) as error:
            _LOG.warning(
                "Keeping previous configuration after failed reload of %s: %s",
                self.path, error,
            )
            return False
        self._config = replacement
        return True


config = _Config()
