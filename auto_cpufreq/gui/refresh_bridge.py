"""GTK/GLib adapter for one toolkit-independent report refresh coordinator.

This module runs no hardware policy and owns no GTK widgets or timers.
The worker thread only schedules delivery through GLib.idle_add().
All callbacks which render or schedule the next refresh run in the GTK loop.
"""
import time

from gi.repository import GLib

from auto_cpufreq.modules.report_refresh import ReportRefreshCoordinator


class GtkRefreshBridge:
    """Common delivery, diagnostics and acknowledgement for GTK report views.

    Both GTK views use a separate GtkRefreshTimer for periodic scheduling.
    This bridge only transports results and acknowledges deliveries.
    """

    def __init__(
        self, collect, *,
        component, diagnostics, active, interval,
        on_report, on_error, thread_name, before_ack=None,
    ):
        self._component = component
        self._diagnostics = diagnostics
        self._active = active
        self._interval = interval
        self._on_report = on_report
        self._on_error = on_error
        self._before_ack = before_ack
        self.coordinator = ReportRefreshCoordinator(
            collect, self.dispatch, thread_name=thread_name,
            on_dispatch_error=self._dispatch_failure,
        )

    def _safe(self, method, *args, **kwargs):
        try:
            method(*args, **kwargs)
        except Exception:
            # A broken diagnostics backend cannot strand delivery or shut
            # down the GTK event loop. Each metric remains independent.
            pass

    def _dispatch_failure(self, error):
        self._safe(
            self._diagnostics.warning,
            "%s report delivery failed: %s", self._component, error,
        )

    def dispatch(self, result):
        """Called on the collector thread: never touch a GTK widget here."""
        GLib.idle_add(self.deliver, result)

    def _record_metrics(self, result):
        interval = self._interval()
        prefix = self._component
        self._safe(
            self._diagnostics.record_duration,
            f"{prefix} queue", result.queue_seconds,
            slow_after=max(1.0, interval),
        )
        self._safe(
            self._diagnostics.record_duration,
            f"{prefix} collection", result.duration,
            slow_after=max(2.0, interval * 2),
        )
        if result.completed_at:
            self._safe(
                self._diagnostics.record_duration,
                f"{prefix} delivery latency",
                max(0.0, time.monotonic() - result.completed_at),
                slow_after=max(1.0, interval),
            )

    def deliver(self, result):
        """One GLib idle callback; return False to remove the source."""
        if not self._active() or not self.coordinator.is_current(
            result.generation
        ):
            return False

        try:
            self._record_metrics(result)
            try:
                if result.error is not None:
                    self._safe(
                        self._diagnostics.warning,
                        "%s collection failed: %s",
                        self._component, result.error,
                    )
                    self._on_error(str(result.error))
                else:
                    self._on_report(result.report)
            except Exception as error:
                self._safe(
                    self._diagnostics.exception,
                    "%s presentation failed", self._component,
                )
                # Even a faulty error widget must not prevent acknowledgement.
                try:
                    self._on_error(str(error))
                except Exception:
                    self._safe(
                        self._diagnostics.exception,
                        "%s error presentation failed", self._component,
                    )
        finally:
            try:
                if result.requested_at:
                    self._safe(
                        self._diagnostics.record_duration,
                        f"{self._component} end-to-end refresh",
                        max(0.0, time.monotonic() - result.requested_at),
                        slow_after=max(2.0, self._interval() * 2),
                    )
                if self._before_ack is not None:
                    try:
                        self._before_ack()
                    except Exception:
                        self._safe(
                            self._diagnostics.exception,
                            "%s pending refresh scheduling failed",
                            self._component,
                        )
            finally:
                self.coordinator.acknowledge(result.generation)
        return False
