"""Toolkit-independent, opt-in diagnostic logging for frontend processes.

There is deliberately no GTK, Urwid, policy or service dependency here.
Each start() gets its own writer, bounded queue and rotation set.
"""
import copy
import logging
from logging.handlers import QueueHandler, RotatingFileHandler
import os
from pathlib import Path
from queue import Empty, Full, Queue
import re
import secrets
import sys
from threading import Lock, Thread
from auto_cpufreq.modules.process_health import ProcessHealthSampler
import time
import traceback


MAX_LOG_BYTES = 1024 * 1024
LOG_BACKUPS = 3
RETAIN_SESSIONS = 4
QUEUE_SIZE = 256
MAX_MESSAGE_CHARS = 8192
MAX_TRACEBACK_CHARS = 16384
_ACTIVE_LOGS = set()
_ACTIVE_LOCK = Lock()
_PRUNE_LOCK = Lock()
_SESSION_FILE = re.compile(
    r"^([a-z][a-z0-9_-]*)-(\d{8})-(\d{6})-(\d+)-[0-9a-f]{8}\.log$"
)


def _xdg_path(variable, fallback):
    value = os.environ.get(variable, "")
    return Path(value) if value.startswith("/") else Path.home() / fallback


def cli_state_directory():
    """Keep sudo-run diagnostics out of the invoking user's home.

    For root, ignore inherited HOME/XDG_STATE_HOME and use the actual
    root account home. No directory is created until logging is enabled.
    """
    if os.geteuid() == 0:
        import pwd
        return Path(pwd.getpwuid(0).pw_dir) / ".local/state/auto-cpufreq"
    return _xdg_path("XDG_STATE_HOME", ".local/state") / "auto-cpufreq"


def _is_running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class _PrivateRotatingFileHandler(RotatingFileHandler):
    """Create a private log; retain its permissions after rotation."""

    def __init__(self, *args, on_error=None, **kwargs):
        self._on_error = on_error
        super().__init__(*args, **kwargs)

    def _open(self):
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        flags |= getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_CLOEXEC", 0)
        fd = os.open(self.baseFilename, flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
            return os.fdopen(fd, "a", encoding="utf-8")
        except BaseException:
            os.close(fd)
            raise

    def handleError(self, record):
        if self._on_error:
            self._on_error(sys.exc_info()[1] or OSError("Unknown log write failure"))


class _BoundedQueueHandler(QueueHandler):
    """Non-blocking writes, including concurrent producer-safe shutdown.

    Closing the producer gate and inserting the sentinel happen under the
    same lock. No producer can enqueue *after* the sentinel.
    """

    def __init__(self, events, on_drop):
        super().__init__(events)
        self._gate = Lock()
        self._closing = False
        self._on_drop = on_drop

    def prepare(self, record):
        # No live args/tracebacks/stack objects may be retained in the queue.
        # Bound the largest record even when a slow filesystem stalls the
        # writer. The producer pays for formatting, but never for disk I/O.
        result = copy.copy(record)
        message = record.getMessage()
        result.msg = str(message)[:MAX_MESSAGE_CHARS]
        result.args = None
        if record.exc_info:
            result.exc_text = "".join(traceback.format_exception(
                *record.exc_info, limit=24
            ))[:MAX_TRACEBACK_CHARS]
        elif record.exc_text:
            result.exc_text = str(record.exc_text)[:MAX_TRACEBACK_CHARS]
        result.exc_info = None
        if record.stack_info:
            result.stack_info = str(record.stack_info)[:MAX_TRACEBACK_CHARS]
        return result

    def enqueue(self, record):
        dropped = False
        with self._gate:
            if self._closing:
                return
            try:
                self.queue.put_nowait(record)
                return
            except Full:
                dropped = True
                if record.levelno >= logging.WARNING:
                    try:
                        self.queue.get_nowait()
                        self.queue.put_nowait(record)
                    except (Empty, Full):
                        pass
        if dropped:
            self._on_drop()

    def close_producers(self):
        with self._gate:
            if self._closing:
                return
            self._closing = True
            try:
                self.queue.put_nowait(None)
            except Full:
                try:
                    self.queue.get_nowait()
                except Empty:
                    pass
                # No competing producers can fill the freed slot now.
                self.queue.put_nowait(None)


class _Session:
    def __init__(self, events, handler, output, writer):
        self.events = events
        self.handler = handler
        self.output = output
        self.writer = writer
        self.dropped = 0
        self.drop_lock = Lock()

    def on_drop(self):
        with self.drop_lock:
            self.dropped += 1

    def take_dropped(self):
        with self.drop_lock:
            dropped, self.dropped = self.dropped, 0
        return dropped


class SessionDiagnostics:
    """Shared logging storage and lifecycle, with per-instance error hook."""

    def __init__(self, component="gtk", state_dir=None):
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", component):
            raise ValueError("Invalid diagnostic component")
        self.component = component
        self.state_dir = (
            Path(state_dir) if state_dir is not None
            else _xdg_path("XDG_STATE_HOME", ".local/state") / "auto-cpufreq"
        )
        self.log_path = self._new_log_path()
        self._logger = logging.getLogger(
            f"auto_cpufreq.diagnostics.{component}.{id(self)}"
        )
        self._logger.propagate = False
        self._logger.setLevel(logging.DEBUG)
        self._session = None
        self._handler = None
        self._file_handler = None
        self._writer = None
        self._events = None
        self._activated_once = False
        self._health_sampler = None
        self._retiring_session = None
        self._error_lock = Lock()
        self.last_error = None
        self._error_count = 0
        self.enabled = False

    @property
    def _dropped(self):
        session = self._session
        return session.dropped if session is not None else 0

    def _new_log_path(self):
        filename = (
            f"{self.component}-{time.strftime('%Y%m%d-%H%M%S')}-"
            f"{os.getpid()}-{secrets.token_hex(4)}.log"
        )
        return self.state_dir / filename

    def _report_error(self, error):
        """Store errors without writing to the failed destination.

        GUI adapters may additionally schedule an error notification on
        their own UI context. Worker threads must not touch UI widgets.
        """
        message = f"Unable to write diagnostic log: {str(error)[:240]}"
        with self._error_lock:
            self.last_error = message
            self._error_count += 1

    def error_status(self):
        with self._error_lock:
            return self._error_count, self.last_error

    def _writer_loop(self, session):
        try:
            self._prune_old_sessions()
            while True:
                record = session.events.get()
                if record is None:
                    break
                try:
                    session.output.handle(record)
                except Exception as error:
                    self._report_error(error)
                dropped = session.take_dropped()
                if dropped:
                    notice = self._logger.makeRecord(
                        self._logger.name, logging.WARNING, __file__, 0,
                        "Dropped %d debug log entries because the queue was full",
                        (dropped,), None,
                    )
                    try:
                        session.output.handle(notice)
                    except Exception as error:
                        self._report_error(error)
        finally:
            try:
                session.output.close()
            finally:
                with _ACTIVE_LOCK:
                    _ACTIVE_LOGS.discard(Path(session.output.baseFilename))

    def _prune_old_sessions(self):
        # Prevent two writers from simultaneously enumerating/unlinking
        # the same completed files. External processes can still remove a
        # file between stat/unlink, so individual races are nonfatal.
        with _PRUNE_LOCK:
            try:
                completed = []
                for base in self.state_dir.glob(f"{self.component}-*.log"):
                    match = _SESSION_FILE.fullmatch(base.name)
                    if not match or match.group(1) != self.component:
                        continue
                    with _ACTIVE_LOCK:
                        if base in _ACTIVE_LOGS:
                            continue
                    pid = int(match.group(4))
                    if pid != os.getpid() and _is_running(pid):
                        continue
                    try:
                        timestamp = base.stat().st_mtime
                    except OSError:
                        continue
                    completed.append((timestamp, base))
                completed.sort(key=lambda pair: pair[0], reverse=True)
                for _timestamp, base in completed[RETAIN_SESSIONS:]:
                    for suffix in ("", *(f".{i}" for i in range(
                        1, LOG_BACKUPS + 1
                    ))):
                        try:
                            base.with_name(base.name + suffix).unlink(
                                missing_ok=True
                            )
                        except OSError:
                            pass
            except OSError:
                # Retention failure must never prevent a GUI from launching.
                pass

    def _activate(self):
        if self.enabled:
            return
        # A writer stuck in I/O may outlive the bounded shutdown wait.
        # Do not create a second unsupervised session while it remains.
        retiring = self._retiring_session
        if retiring is not None and retiring.writer.is_alive():
            # Off/on in rapid succession must not race normal cooperative
            # writer shutdown. Bound the hand-off on the calling thread.
            retiring.writer.join(timeout=0.05)
            if retiring.writer.is_alive():
                raise OSError("Previous diagnostic writer is still stopping")
        self._retiring_session = None
        if self._health_sampler is not None and self._health_sampler.is_alive():
            # A stopped sampler may still be exiting its Event.wait loop.
            if not self._health_sampler.stop(wait=True):
                raise OSError("Previous process-health sampler is still stopping")
        self._health_sampler = None
        if self._activated_once:
            self.log_path = self._new_log_path()
        self.state_dir = self.log_path.parent
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        output = _PrivateRotatingFileHandler(
            self.log_path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUPS,
            delay=False, on_error=self._report_error,
        )
        output.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(threadName)s %(message)s"
        ))
        events = Queue(maxsize=QUEUE_SIZE)
        # Build session before wiring on_drop and the writer.
        session = _Session(events, None, output, None)
        handler = _BoundedQueueHandler(events, session.on_drop)
        writer = Thread(
            target=self._writer_loop, args=(session,),
            daemon=True, name=f"{self.component}-debug-writer",
        )
        session.handler, session.writer = handler, writer
        with _ACTIVE_LOCK:
            _ACTIVE_LOGS.add(self.log_path)
        try:
            writer.start()
        except RuntimeError:
            with _ACTIVE_LOCK:
                _ACTIVE_LOGS.discard(self.log_path)
            output.close()
            raise
        self._session = session
        self._handler = handler
        self._file_handler = output
        self._events = events
        self._writer = writer
        self._logger.addHandler(handler)
        self.enabled = True
        self._activated_once = True
        with self._error_lock:
            self.last_error = None
            self._error_count = 0
        self.info("%s debug logging enabled; pid=%d", self.component, os.getpid())
        # Sampling is opt-in and shares this process's own session log.
        # It never touches cpufreq, daemon services or the GUI event loop.
        sampler = ProcessHealthSampler(self)
        try:
            sampler.start()
        except (OSError, RuntimeError) as error:
            self.warning("Process health sampler unavailable: %s", error)
        else:
            self._health_sampler = sampler

    def _deactivate(self, *, wait=True):
        if not self.enabled:
            return
        # Retain sampler ownership if a procfs read outlives stop().
        sampler = self._health_sampler
        if sampler is not None:
            sampler.stop(wait=wait)
        self.info("%s debug logging disabled", self.component)
        self.enabled = False
        session = self._session
        if session is None:
            return
        self._logger.removeHandler(session.handler)
        session.handler.close_producers()
        if wait:
            session.writer.join(timeout=0.3)
        self._retiring_session = (
            session if session.writer.is_alive() else None
        )
        self._session = None
        self._handler = None
        self._file_handler = None
        self._events = None
        self._writer = None

    def debug(self, message, *args):
        if self.enabled:
            self._logger.debug(message, *args)

    def info(self, message, *args):
        if self.enabled:
            self._logger.info(message, *args)

    def warning(self, message, *args):
        if self.enabled:
            self._logger.warning(message, *args)

    def exception(self, message, *args):
        if self.enabled:
            self._logger.exception(message, *args)

    def shutdown(self):
        self._deactivate()
