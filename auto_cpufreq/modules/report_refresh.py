"""Toolkit-independent single-flight report refresh coordination.

An adapter decides *when* to request refresh and *how* to deliver results
onto GTK/GLib or Urwid's event loop. This module never touches widgets,
system policy, or privileged APIs.
"""
from collections import deque
from dataclasses import dataclass
import logging
from threading import Lock, Thread
import time
from typing import Any, Callable
import weakref

_LOG = logging.getLogger(__name__)


class _ProcessCollectionLane:
    """One short-lived daemon worker for all frontend collectors in a process.

    Waiting UI instances enqueue weak references. A closed view removes its
    queued job. This bounds active collectors to one even when the user
    repeatedly closes/reopens Monitor while a kernel read is blocked.
    """

    def __init__(self):
        self._lock = Lock()
        self._jobs = deque()
        self._worker = None

    def enqueue(self, coordinator, generation, requested_at):
        with self._lock:
            self._jobs.append((weakref.ref(coordinator), generation, requested_at))
            if self._worker is not None and self._worker.is_alive():
                return
            worker = Thread(
                target=self._drain,
                daemon=True,
                name=coordinator._thread_name,
            )
            try:
                worker.start()
            except RuntimeError:
                self._jobs.pop()
                raise
            self._worker = worker

    def cancel(self, coordinator):
        with self._lock:
            self._jobs = deque(
                (ref, generation, requested_at)
                for ref, generation, requested_at in self._jobs
                if ref() is not None and ref() is not coordinator
            )

    def _drain(self):
        while True:
            with self._lock:
                if not self._jobs:
                    self._worker = None
                    return
                ref, generation, requested_at = self._jobs.popleft()
            coordinator = ref()
            if coordinator is not None:
                coordinator._run(generation, requested_at)


_PROCESS_LANE = _ProcessCollectionLane()


@dataclass(frozen=True)
class RefreshResult:
    generation: int
    report: Any
    error: Exception | None
    duration: float
    queue_seconds: float = 0.0
    requested_at: float = 0.0
    completed_at: float = 0.0

    @property
    def succeeded(self):
        return self.error is None


class ReportRefreshCoordinator:
    """Coalesce refresh requests; no overlapping collectors for one view.

    Dispatch is called from a worker thread and must only schedule delivery
    onto the appropriate UI context. The UI calls acknowledge(generation)
    once it has processed a result; a pending request then starts a fresh
    collection. Closing invalidates all outstanding generations but does not
    pretend to forcibly interrupt psutil or another blocking system read.
    """

    def __init__(
        self,
        collect: Callable[[], Any],
        dispatch: Callable[[RefreshResult], None],
        thread_name="report-refresh",
        on_dispatch_error=None,
    ):
        self._collect = collect
        self._dispatch = dispatch
        self._thread_name = thread_name
        self._on_dispatch_error = on_dispatch_error
        self._lock = Lock()
        self._generation = 0
        self._running = False
        self._delivering = False
        self._pending = False
        self._closed = False
        self._requested_at = None

    @property
    def closed(self):
        with self._lock:
            return self._closed

    @property
    def in_progress(self):
        with self._lock:
            return self._running or self._delivering

    def request_age_seconds(self):
        """Age of the active collection/delivery, or None when idle.

        Diagnostic-only: never start another collector to clear a stalled one.
        """
        with self._lock:
            if not (self._running or self._delivering):
                return None
            requested_at = self._requested_at
        if requested_at is None:
            return None
        return max(0.0, time.monotonic() - requested_at)

    def request(self):
        """Explicit request: coalesce one successor if a collection is busy."""
        return self._request(queue_if_busy=True)

    def request_if_idle(self):
        """Periodic request: skip busy cycles without creating pending work.

        The busy check and reservation share the same lock, so concurrent
        callers cannot queue a periodic successor between those operations.
        """
        return self._request(queue_if_busy=False)

    def _request(self, *, queue_if_busy):
        with self._lock:
            if self._closed:
                return False
            if self._running or self._delivering:
                if queue_if_busy:
                    self._pending = True
                return False
            generation, requested_at = self._reserve_locked()
        try:
            _PROCESS_LANE.enqueue(self, generation, requested_at)
        except RuntimeError:
            with self._lock:
                if generation == self._generation:
                    # A concurrent explicit request may have set _pending
                    # while enqueue() attempted to start the worker.
                    self._pending = False
                    self._running = False
                    self._requested_at = None
            raise
        return True

    def _reserve_locked(self):
        self._generation += 1
        generation = self._generation
        requested_at = time.monotonic()
        self._requested_at = requested_at
        self._running = True
        return generation, requested_at

    def _report_dispatch_failure(self, error):
        # May be called by a worker or by the GUI main loop when queuing
        # a successor fails. The error reporter itself cannot be fatal.
        try:
            if self._on_dispatch_error is not None:
                self._on_dispatch_error(error)
            else:
                _LOG.warning("Report delivery failed: %s", error)
        except Exception:
            _LOG.exception("Reporting a refresh delivery error failed")

    def _run(self, generation, requested_at):
        with self._lock:
            if self._closed or generation != self._generation:
                return
        started = time.monotonic()
        queue_seconds = max(0.0, started - requested_at)
        try:
            value = self._collect()
            error = None
        except Exception as exc:
            value = None
            error = exc
        completed_at = time.monotonic()
        result = RefreshResult(
            generation=generation,
            report=value,
            error=error,
            duration=completed_at - started,
            queue_seconds=queue_seconds,
            requested_at=requested_at,
            completed_at=completed_at,
        )
        with self._lock:
            if self._closed or generation != self._generation:
                return
            self._running = False
            self._delivering = True
        try:
            self._dispatch(result)
        except Exception as error:
            # Failed UI dispatch cannot strand the coordinator.
            try:
                self._report_dispatch_failure(error)
            finally:
                self.acknowledge(generation)

    def is_current(self, generation):
        with self._lock:
            return (
                not self._closed
                and generation == self._generation
                and self._delivering
            )

    def acknowledge(self, generation):
        with self._lock:
            if (
                self._closed
                or generation != self._generation
                or not self._delivering
            ):
                return False
            self._delivering = False
            again = self._pending
            self._pending = False
            if again:
                generation_next, requested_next = self._reserve_locked()
            else:
                self._requested_at = None
        if again:
            try:
                _PROCESS_LANE.enqueue(self, generation_next, requested_next)
            except RuntimeError as error:
                with self._lock:
                    if generation_next == self._generation:
                        # A new explicit request can arrive while this
                        # successor worker is being started.
                        self._pending = False
                        self._running = False
                        self._requested_at = None
                # Worker creation can fail after the previous report has
                # already been presented. The next periodic UI tick can
                # safely retry; do not leak this failure into GTK/Urwid.
                self._report_dispatch_failure(error)
        return True

    def close(self):
        with self._lock:
            self._closed = True
            self._generation += 1
            self._running = False
            self._pending = False
            self._delivering = False
            self._requested_at = None
        _PROCESS_LANE.cancel(self)
