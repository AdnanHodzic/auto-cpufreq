"""GTK-only diagnostic adapter over the shared process logging engine."""
import json
import os
import sys
import tempfile
from threading import Event, Lock, Thread, main_thread
import time
import traceback

from auto_cpufreq.modules.diagnostics import SessionDiagnostics, _xdg_path


HEARTBEAT_SECONDS = 5
STALL_SECONDS = 20
SUMMARY_SECONDS = 60


def _boottime():
    try:
        return time.clock_gettime(time.CLOCK_BOOTTIME)
    except (AttributeError, OSError):
        return None


class GuiDiagnostics(SessionDiagnostics):
    def __init__(self):
        super().__init__(component="gtk")
        self.settings_path = (
            _xdg_path("XDG_CONFIG_HOME", ".config") /
            "auto-cpufreq" / "gtk-debug.json"
        )
        self._glib = None
        self._heartbeat_id = None
        self._last_heartbeat = time.monotonic()
        self._last_boottime = _boottime()
        self._main_thread_id = main_thread().ident
        self._stall_reported = False
        self._watchdog_stop = None
        self._watchdog_thread = None
        self._lock = Lock()
        self._summary = {}
        self._last_summary = time.monotonic()
        self._error_callback = None
        self._last_gui_error = None

    def _read_preference(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return data.get("debug_logging") is True
        except (OSError, ValueError, AttributeError):
            return False

    def _save_preference(self, enabled):
        directory = self.settings_path.parent
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".gtk-debug-", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"debug_logging": enabled}, stream)
                stream.write("\n")
            os.chmod(name, 0o600)
            os.replace(name, self.settings_path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def set_error_callback(self, callback):
        with self._lock:
            self._error_callback = callback
            error = self._last_gui_error
        if callback is not None and error is not None:
            self._notify_error(error)

    def _notify_error(self, message):
        if self._glib is not None:
            self._glib.idle_add(self._deliver_error, message)

    def _deliver_error(self, message):
        with self._lock:
            callback = self._error_callback
        if callback:
            callback(message)
        return False

    def _report_error(self, error):
        super()._report_error(error)
        message = f"Unable to write GUI debug log: {error}"
        with self._lock:
            if self._last_gui_error == message:
                return
            self._last_gui_error = message
        self._notify_error(message)

    def attach_mainloop(self, glib):
        """Activate saved logging only when the GTK app actually starts.

        Importing the UI modules, including from unit tests, must not
        create diagnostic files or background threads.
        """
        self._glib = glib
        if not self.enabled and self._read_preference():
            try:
                self._activate()
            except (OSError, RuntimeError) as error:
                # A saved preference must not make GTK startup depend on
                # the availability of optional log and watchdog threads.
                self._report_error(error)
        elif self.enabled:
            self._start_heartbeat()

    def _start_heartbeat(self):
        if self._glib is None or self._heartbeat_id is not None:
            return
        with self._lock:
            self._last_heartbeat = time.monotonic()
            self._last_boottime = _boottime()
        self._heartbeat_id = self._glib.timeout_add_seconds(
            HEARTBEAT_SECONDS, self._heartbeat
        )

    def _heartbeat(self):
        if not self.enabled:
            self._heartbeat_id = None
            return False
        now = time.monotonic()
        boottime = _boottime()
        with self._lock:
            gap = now - self._last_heartbeat
            suspended = (
                boottime - self._last_boottime - gap
                if boottime is not None and self._last_boottime is not None
                else 0
            )
            self._last_heartbeat = now
            self._last_boottime = boottime
            self._stall_reported = False
        if suspended > 3:
            self.info(
                "System suspend/resume detected: %.1f seconds suspended",
                suspended,
            )
        if gap > HEARTBEAT_SECONDS * 2:
            self.warning("GTK main loop delay: %.2f seconds", gap)
        self._flush_summary(now)
        return True

    def _flush_summary(self, now=None, force=False):
        now = time.monotonic() if now is None else now
        with self._lock:
            if not force and now - self._last_summary < SUMMARY_SECONDS:
                return
            summary, self._summary = self._summary, {}
            self._last_summary = now
        for kind, (count, total, maximum) in summary.items():
            self.info(
                "%s: %d calls, mean=%.3fs max=%.3fs",
                kind, count, total / count, maximum,
            )

    def record_duration(self, kind, duration, slow_after=2.0):
        if not self.enabled:
            return
        with self._lock:
            count, total, maximum = self._summary.get(kind, (0, 0.0, 0.0))
            self._summary[kind] = (
                count + 1, total + duration, max(maximum, duration)
            )
        if duration > slow_after:
            self.warning("Slow %s: %.3fs", kind, duration)

    def _check_stall(self):
        if not self.enabled or self._glib is None:
            return
        with self._lock:
            delay = time.monotonic() - self._last_heartbeat
            if delay < STALL_SECONDS or self._stall_reported:
                return
            self._stall_reported = True
        self._flush_summary(force=True)
        frame = sys._current_frames().get(self._main_thread_id)
        stack = (
            "".join(traceback.format_stack(frame, limit=24))
            if frame else "unavailable"
        )
        self.warning(
            "GTK main loop unresponsive for at least %.1f seconds; "
            "main thread stack:\n%s", delay, stack,
        )

    def _watchdog(self, stop):
        while not stop.wait(HEARTBEAT_SECONDS):
            self._check_stall()

    def _activate(self):
        if (
            self._watchdog_thread is not None
            and self._watchdog_thread.is_alive()
        ):
            # A rapid off/on UI toggle can race with the cooperative
            # watchdog stop. Allow a bounded hand-off, without starting a
            # second watchdog or blocking GTK indefinitely.
            join = getattr(self._watchdog_thread, "join", None)
            if callable(join):
                join(timeout=0.05)
            if self._watchdog_thread.is_alive():
                raise OSError("Previous GTK diagnostic watchdog is still stopping")
        self._watchdog_thread = None
        super()._activate()
        try:
            with self._lock:
                self._last_summary = time.monotonic()
                self._summary = {}
                self._stall_reported = False
                self._last_gui_error = None
            self.info("GUI session=%s", os.environ.get("XDG_SESSION_TYPE", "unknown"))
            self._start_heartbeat()
            stop = Event()
            worker = Thread(
                target=self._watchdog, args=(stop,), daemon=True,
                name="gui-debug-watchdog",
            )
            worker.start()
            self._watchdog_stop = stop
            self._watchdog_thread = worker
        except (OSError, RuntimeError):
            # A failure after opening the log must also release its timer,
            # health sampler and writer before reporting activation failure.
            self._deactivate(wait=True)
            raise

    def _deactivate(self, *, wait=False):
        if not self.enabled:
            return
        self._flush_summary(force=True)
        if self._watchdog_stop is not None:
            self._watchdog_stop.set()
            self._watchdog_stop = None
        worker = self._watchdog_thread
        if wait and worker is not None and worker.is_alive():
            worker.join(timeout=0.2)
        # Retain the reference while a slow watchdog is still alive.
        if worker is not None and not worker.is_alive():
            self._watchdog_thread = None
        if self._heartbeat_id is not None and self._glib is not None:
            self._glib.source_remove(self._heartbeat_id)
            self._heartbeat_id = None
        super()._deactivate(wait=wait)

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        if enabled:
            self._activate()
            try:
                self._save_preference(True)
            except OSError:
                self._deactivate()
                raise
        else:
            self._save_preference(False)
            self._deactivate()

    def shutdown(self):
        self.info("GUI session ended")
        # Only at process exit do we make bounded attempts to flush logs.
        self._deactivate(wait=True)


diagnostics = GuiDiagnostics()
