"""Low-overhead, opt-in Linux process and thread CPU diagnostics.

Measures CPU time in /proc using CLOCK_TICKS and wall elapsed time.
100% means approximately one logical CPU, not 100% of the entire host.
No privileged access, GUI toolkit, psutil or energy-policy dependencies.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from threading import Event, Lock, Thread, enumerate as enumerate_threads
import time
import traceback


CLOCK_TICKS = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
SAMPLE_SECONDS = 5
HIGH_CPU_PERCENT = 70.0
HIGH_CPU_SAMPLES = 3
SUMMARY_SECONDS = 60


def parse_task_stat(source):
    """Extract utime, stime, starttime despite spaces and ')' in comm."""
    fields = source.rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12]), int(fields[19])


@dataclass(frozen=True)
class Snapshot:
    monotonic: float
    ticks: int
    starttime: int
    task_ticks: dict
    rss_mib: float | None
    threads: int | None
    fds: int | None


def read_snapshot(pid=None, proc_root=Path("/proc"), clock=time.monotonic):
    pid = os.getpid() if pid is None else pid
    root = Path(proc_root) / str(pid)
    ticks, starttime = parse_task_stat(
        (root / "stat").read_text(encoding="ascii")
    )
    tasks = {}
    try:
        for task in (root / "task").iterdir():
            if not task.name.isdigit():
                continue
            try:
                task_ticks, task_start = parse_task_stat(
                    (task / "stat").read_text(encoding="ascii")
                )
                tasks[int(task.name)] = (task_ticks, task_start)
            except (OSError, ValueError, IndexError):
                # Threads can legitimately disappear during enumeration.
                continue
    except OSError:
        pass

    rss = None
    thread_count = None
    try:
        with (root / "status").open(encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1]) / 1024
                elif line.startswith("Threads:"):
                    thread_count = int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass

    fds = None
    try:
        with os.scandir(root / "fd") as entries:
            fds = sum(1 for _ in entries)
    except OSError:
        pass

    return Snapshot(
        monotonic=clock(), ticks=ticks, starttime=starttime,
        task_ticks=tasks, rss_mib=rss, threads=thread_count, fds=fds,
    )


@dataclass(frozen=True)
class ProcessHealth:
    cpu_percent: float
    hottest_tid: int | None
    hottest_thread_percent: float
    rss_mib: float | None
    threads: int | None
    fds: int | None


def compute_health(previous, current, ticks_per_second=CLOCK_TICKS):
    elapsed = current.monotonic - previous.monotonic
    if elapsed <= 0 or current.starttime != previous.starttime:
        return None
    ticks_delta = current.ticks - previous.ticks
    if ticks_delta < 0:
        return None

    hottest_tid, hottest_percent = None, 0.0
    for tid, (ticks, birth) in current.task_ticks.items():
        original = previous.task_ticks.get(tid)
        if original is None or original[1] != birth or ticks < original[0]:
            continue
        cpu = 100.0 * (ticks - original[0]) / ticks_per_second / elapsed
        if cpu > hottest_percent:
            hottest_tid, hottest_percent = tid, cpu

    return ProcessHealth(
        cpu_percent=100.0 * ticks_delta / ticks_per_second / elapsed,
        hottest_tid=hottest_tid,
        hottest_thread_percent=hottest_percent,
        rss_mib=current.rss_mib,
        threads=current.threads,
        fds=current.fds,
    )


class ProcessHealthSampler:
    """A diagnostic-only worker; every sample is nonblocking.

    A quiet session produces one summary per minute, not one line every
    interval. A sustained high-CPU episode logs the hottest Linux TID.
    The first reading primes deltas and must not be interpreted as CPU%.
    """

    def __init__(
        self, log, read=read_snapshot, interval=SAMPLE_SECONDS,
        high_threshold=HIGH_CPU_PERCENT, consecutive=HIGH_CPU_SAMPLES,
        summary_interval=SUMMARY_SECONDS,
    ):
        self.log = log
        self.read = read
        self.interval = interval
        self.high_threshold = high_threshold
        self.consecutive = consecutive
        self.summary_interval = summary_interval
        self._previous = None
        self._last_summary = None
        self._samples = 0
        self._sum_cpu = 0.0
        self._max_cpu = 0.0
        self._above = 0
        self._in_episode = False
        self._stop = None
        self._worker = None
        self._lifecycle_lock = Lock()
        self._read_errors = 0
        self._last_read_error_log = None
        self._fatal_errors = 0  # Consecutive unexpected failures
        self._unexpected_errors_total = 0

    def _interrupt_observation(self):
        """Re-prime after missing/invalid samples, permitting a new CPU alert."""
        if self._in_episode:
            self.log.info("Sustained process CPU episode interrupted by sampling gap")
        self._previous = None
        self._above = 0
        self._in_episode = False

    def _log_hot_python_thread(self, tid):
        if tid is None:
            return
        # Native TIDs are not Python frame IDs. Resolve a live Python
        # Thread object to its interpreter ident before looking up frames.
        for thread in enumerate_threads():
            if thread.native_id != tid or thread.ident is None:
                continue
            frame = sys._current_frames().get(thread.ident)
            if frame is not None:
                stack = "".join(traceback.format_stack(frame, limit=16))
                self.log.warning(
                    "High CPU Python thread stack: tid=%d name=%s\\n%s",
                    tid, thread.name, stack,
                )
            return

    def observe(self, current):
        if self._last_summary is None:
            self._last_summary = current.monotonic
        previous, self._previous = self._previous, current
        if previous is None:
            return None
        health = compute_health(previous, current)
        if health is None:
            # Invalid delta or process restart. Do not carry an old alert
            # episode or compare the next sample with a broken baseline.
            self._interrupt_observation()
            return None

        self._samples += 1
        self._sum_cpu += health.cpu_percent
        self._max_cpu = max(self._max_cpu, health.cpu_percent)
        if health.cpu_percent >= self.high_threshold:
            self._above += 1
            if self._above >= self.consecutive and not self._in_episode:
                self._in_episode = True
                self.log.warning(
                    "Sustained process CPU: %.1f%% of one core, samples=%d, "
                    "hottest_tid=%s hottest_thread=%.1f%%, rss_mib=%s "
                    "threads=%s fds=%s",
                    health.cpu_percent, self._above, health.hottest_tid,
                    health.hottest_thread_percent, health.rss_mib,
                    health.threads, health.fds,
                )
                self._log_hot_python_thread(health.hottest_tid)
        else:
            self._above = 0
            if self._in_episode:
                self.log.info(
                    "Sustained process CPU episode ended: %.1f%% of one core",
                    health.cpu_percent,
                )
                self._in_episode = False
        if (
            current.monotonic - self._last_summary
            >= self.summary_interval and self._samples
        ):
            self.log.info(
                "Process health: %d samples, mean_cpu=%.1f%% one core, "
                "max_cpu=%.1f%% one core, rss_mib=%s threads=%s fds=%s",
                self._samples, self._sum_cpu / self._samples,
                self._max_cpu, health.rss_mib, health.threads, health.fds,
            )
            self._last_summary = current.monotonic
            self._samples = 0
            self._sum_cpu = 0.0
            self._max_cpu = 0.0
        return health

    def _run(self, stop):
        while not stop.is_set():
            try:
                sample = self.read()
                self.observe(sample)
                if self._fatal_errors:
                    self.log.info(
                        "Process health sampler recovered after %d "
                        "consecutive unexpected failures",
                        self._fatal_errors,
                    )
                    self._fatal_errors = 0
                if self._read_errors:
                    self.log.info(
                        "Process health sampling recovered after %d failed reads",
                        self._read_errors,
                    )
                    self._read_errors = 0
                    self._last_read_error_log = None
            except (OSError, ValueError, IndexError) as error:
                # A persistent /proc error should not crowd out useful logs.
                self._read_errors += 1
                now = time.monotonic()
                if (
                    self._last_read_error_log is None
                    or now - self._last_read_error_log >= SUMMARY_SECONDS
                ):
                    self.log.warning(
                        "Process health sampling unavailable (%d failures): %s",
                        self._read_errors, error,
                    )
                    self._last_read_error_log = now
                self._interrupt_observation()
            except Exception as error:
                # Unexpected code failures should neither silently kill the
                # sampler nor cause an endless high-frequency traceback flood.
                self._fatal_errors += 1
                self._unexpected_errors_total += 1
                if self._fatal_errors == 1:
                    self.log.warning(
                        "Process health sampler unexpected failure: %s",
                        error,
                    )
                if self._fatal_errors >= 3:
                    self.log.warning(
                        "Process health sampler stopped after %d unexpected "
                        "failures", self._fatal_errors,
                    )
                    return
                self._interrupt_observation()
            if stop.wait(self.interval):
                break

    def is_alive(self):
        with self._lifecycle_lock:
            return self._worker is not None and self._worker.is_alive()

    def start(self):
        with self._lifecycle_lock:
            if self._worker is not None and self._worker.is_alive():
                if self._stop is not None and self._stop.is_set():
                    raise OSError(
                        "Previous process-health sampler is still stopping"
                    )
                return
            stop = Event()
            worker = Thread(
                target=self._run, args=(stop,),
                daemon=True, name="process-health-debug",
            )
            # New sampling session must not use the previous session's
            # deltas, counters or alert state.
            self._previous = None
            self._last_summary = None
            self._samples = 0
            self._sum_cpu = 0.0
            self._max_cpu = 0.0
            self._above = 0
            self._in_episode = False
            self._read_errors = 0
            self._last_read_error_log = None
            self._fatal_errors = 0
            self._unexpected_errors_total = 0
            worker.start()
            self._stop = stop
            self._worker = worker

    def stop(self, *, wait=True):
        with self._lifecycle_lock:
            stop, worker = self._stop, self._worker
            if stop is None:
                return True
            stop.set()
        if wait and worker is not None and worker.is_alive():
            # CLI exit may make a bounded wait; GTK toggling must not block.
            worker.join(timeout=0.2)
        with self._lifecycle_lock:
            if worker is not None and worker.is_alive():
                # Retain ownership so start() cannot create a second
                # sampler while an older one remains stuck.
                return False
            if self._worker is worker:
                self._stop = None
                self._worker = None
            return True
