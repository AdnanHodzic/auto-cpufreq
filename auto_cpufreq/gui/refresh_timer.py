"""One low-overhead GLib refresh timer per active GTK view.

This is only the scheduling layer; GtkRefreshBridge owns delivery and
ReportRefreshCoordinator owns single-flight collection and coalescing.
Periodic ticks never queue work behind an already running collection.
"""
from gi.repository import GLib


STALL_SECONDS = 20.0


class GtkRefreshTimer:
    """Periodic refresh with stalled-collection checks; no extra timers."""

    def __init__(
        self, *, coordinator, request, active, diagnostics, component,
        interval,
    ):
        if interval <= 0:
            raise ValueError("Refresh interval must be positive")
        self.coordinator = coordinator
        self._request = request
        self._active = active
        self._diagnostics = diagnostics
        self._component = component
        self._interval = interval
        self._stall_reported = False
        self._source_id = None

    @property
    def source_id(self):
        return self._source_id

    def _log(self, method, *args):
        try:
            method(*args)
        except Exception:
            pass  # Optional diagnostics must not disable a live UI timer.

    def start(self):
        if self._source_id is not None or not self._active():
            return
        self._source_id = GLib.timeout_add_seconds(
            self._interval, self._tick
        )

    def set_interval(self, seconds):
        if seconds <= 0:
            raise ValueError("Refresh interval must be positive")
        if seconds == self._interval:
            return
        was_active = self._source_id is not None
        self.stop()
        self._interval = seconds
        if was_active:
            self.start()

    def _tick(self):
        if not self._active():
            # GLib removes this source when False is returned.
            self._source_id = None
            return False
        try:
            if self.coordinator.in_progress:
                age = self.coordinator.request_age_seconds()
                if (age is not None and age >= STALL_SECONDS
                        and not self._stall_reported):
                    self._stall_reported = True
                    self._log(
                        self._diagnostics.warning,
                        "%s collection/delivery pending for %.1fs; "
                        "keeping single-flight worker",
                        self._component, age,
                    )
            else:
                self._stall_reported = False
                self._request()
        except Exception as error:
            # Do not permit a transient failure to silently remove the timer.
            self._log(
                self._diagnostics.warning,
                "%s periodic refresh failed: %s", self._component, error,
            )
        return True

    def stop(self):
        source_id, self._source_id = self._source_id, None
        if source_id is not None:
            GLib.source_remove(source_id)
        self._stall_reported = False
