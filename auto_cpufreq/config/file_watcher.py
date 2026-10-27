"""Thread-owned, self-recovering Linux inotify watcher for one config pathname.

File parsing/policy decisions are deliberately outside this module. A missing
watch is recoverable rather than fatal to a running auto-cpufreq daemon.
"""
import logging
import os
import select
import stat
import threading
import time

from inotify_simple import INotify, flags


_LOG = logging.getLogger(__name__)


class ConfigFileWatcher:
    """Monitor one filename; select() is interrupted with a private stop pipe.

    state reflects observability: 'starting', 'watching', 'recovering',
    'stopping', or 'stopped'. Only the worker touches inotify descriptors.
    """

    _MASK = (
        flags.CLOSE_WRITE | flags.MOVED_TO | flags.MOVED_FROM
        | flags.DELETE | flags.CREATE | flags.MODIFY
        | flags.DELETE_SELF | flags.MOVE_SELF | flags.UNMOUNT
        | flags.ONLYDIR
    )
    _CHANGED = flags.CLOSE_WRITE | flags.MOVED_TO
    _LINK_MASK = (
        flags.CLOSE_WRITE | flags.MODIFY | flags.DELETE_SELF
        | flags.MOVE_SELF | flags.UNMOUNT
    )
    _REMOVED = flags.DELETE | flags.MOVED_FROM
    _LOST = flags.IGNORED | flags.DELETE_SELF | flags.MOVE_SELF | flags.UNMOUNT

    def __init__(
        self, path, on_change, retry_interval=1.0, delete_grace=0.12,
        max_retry_interval=30.0,
    ):
        self.path = os.path.abspath(os.path.expanduser(path))
        self._on_change = on_change
        self._retry_interval = max(0.1, float(retry_interval))
        self._max_retry_interval = max(
            self._retry_interval, float(max_retry_interval)
        )
        self._delete_grace = max(0.0, float(delete_grace))
        self._lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._stop_write = None
        self._state = "stopped"

    @property
    def state(self):
        with self._lock:
            return self._state

    def set_path(self, path):
        selected = os.path.abspath(os.path.expanduser(path))
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                if selected != self.path:
                    raise RuntimeError("Stop config watcher before changing its path")
            self.path = selected

    def is_alive(self):
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                if self._stop_event.is_set():
                    raise RuntimeError("Configuration watcher is still stopping")
                return
            read_fd, write_fd = os.pipe()
            try:
                # All setup steps after pipe creation can fail. Keep both
                # descriptors owned here until the worker has started.
                os.set_blocking(write_fd, False)
                self._stop_event = threading.Event()
                self._ready = threading.Event()
                worker = threading.Thread(
                    target=self._run, args=(read_fd, self._stop_event, self._ready),
                    name="auto-cpufreq-config-watch", daemon=True,
                )
                self._stop_write = write_fd
                self._state = "starting"
                self._thread = worker
                worker.start()
                ready = self._ready
            except BaseException:
                self._thread = None
                self._stop_write = None
                self._state = "stopped"
                for fd in (read_fd, write_fd):
                    try:
                        os.close(fd)
                    except OSError:
                        pass  # Preserve the original startup exception.
                raise
        # Reports the first watch attempt, not guaranteed successful coverage.
        # The 'state' property distinguishes a watched from a retrying path.
        ready.wait(timeout=3.0)

    def stop(self):
        with self._lock:
            worker = self._thread
            if worker is None:
                self._state = "stopped"
                return
            if not self._stop_event.is_set():
                self._stop_event.set()
                self._state = "stopping"
                try:
                    if self._stop_write is not None:
                        os.write(self._stop_write, b"x")
                except (OSError, BlockingIOError):
                    pass
        if threading.current_thread() is worker:
            return
        worker.join(timeout=5.0)
        with self._lock:
            if not worker.is_alive() and self._thread is worker:
                self._thread = None
                self._state = "stopped"
            elif worker.is_alive():
                _LOG.warning("Configuration watcher did not stop within five seconds")

    def _run(self, stop_read, stop_event, ready):
        notifier = None
        wd = None
        watched_dir = None
        watched_identity = None
        link_wd = None
        link_target = None
        link_identity = None
        link_replaced = False
        pending = None
        pending_deletion = False
        parent = os.path.dirname(self.path)
        basename = os.path.basename(self.path)
        retry_delay = self._retry_interval
        last_error = None
        last_error_at = 0.0

        def change_state(state):
            with self._lock:
                if self._thread is threading.current_thread() and not stop_event.is_set():
                    self._state = state

        def report_problem(detail):
            nonlocal last_error, last_error_at
            now = time.monotonic()
            if detail != last_error or now - last_error_at >= 30.0:
                _LOG.warning("Configuration watch unavailable: %s", detail)
                last_error, last_error_at = detail, now

        def notify():
            if stop_event.is_set():
                return
            try:
                self._on_change()
            except Exception:
                _LOG.exception("Configuration reload callback failed")

        def close_notifier():
            nonlocal notifier, wd, watched_dir, watched_identity
            nonlocal link_wd, link_target, link_identity, link_replaced
            if notifier is not None:
                try:
                    notifier.close()
                except OSError:
                    _LOG.exception("Failed to close inotify descriptor")
            notifier = None
            wd = None
            watched_dir = None
            watched_identity = None
            link_wd = link_target = link_identity = None
            link_replaced = False

        def nearest_existing_directory():
            candidate = parent
            while True:
                try:
                    identity = os.stat(candidate)
                    if stat.S_ISDIR(identity.st_mode):
                        return candidate, (identity.st_dev, identity.st_ino)
                except OSError:
                    pass
                previous = candidate
                candidate = os.path.dirname(candidate)
                if candidate == previous:
                    return None, None

        def reconcile():
            nonlocal wd, watched_dir, watched_identity
            nonlocal link_wd, link_target, link_identity
            directory, identity = nearest_existing_directory()
            changed = False
            if directory != watched_dir or identity != watched_identity or wd is None:
                # Rebuild the event stream if a directory was replaced.
                close_notifier()
                if directory is None:
                    raise OSError("No accessible ancestor of configuration directory")
                ensure_inotify()
                wd = notifier.add_watch(directory, self._MASK)
                watched_dir, watched_identity = directory, identity
                changed = True

            # A symlink target can lie outside the watched directory.
            # Record its inode so atomic replacement will rearm the watch.
            selected_target = None
            selected_identity = None
            if os.path.islink(self.path):
                selected_target = os.path.realpath(self.path)
                try:
                    info = os.stat(selected_target)
                    if stat.S_ISREG(info.st_mode):
                        selected_identity = (info.st_dev, info.st_ino)
                except OSError:
                    pass

            if (selected_target != link_target
                    or selected_identity != link_identity
                    or (selected_identity is not None and link_wd is None)):
                if link_wd is not None:
                    try:
                        notifier.rm_watch(link_wd)
                    except OSError:
                        pass
                link_wd = None
                link_target = selected_target
                link_identity = selected_identity
                if selected_identity is not None:
                    link_wd = notifier.add_watch(selected_target, self._LINK_MASK)
                changed = True
            return changed

        def ensure_inotify():
            nonlocal notifier
            if notifier is None:
                notifier = INotify(nonblocking=True)

        try:
            while not stop_event.is_set():
                try:
                    ensure_inotify()
                    changed_watch = reconcile()
                    if link_replaced and link_wd is not None:
                        # A watched symlink target was removed or moved. Its
                        # replacement may arrive after the loss event: retain
                        # the notice until its new inode can be observed.
                        link_replaced = False
                        pending = time.monotonic()
                        pending_deletion = False
                    if changed_watch and not os.path.lexists(self.path):
                        # A recovered watch cannot establish that an existing
                        # file was closed. Wait for CLOSE_WRITE or an atomic
                        # MOVED_TO instead of trusting quiet file metadata.
                        pending = time.monotonic() + self._delete_grace
                        pending_deletion = True
                    change_state("watching" if watched_dir == parent else "recovering")
                except OSError as error:
                    close_notifier()
                    report_problem(str(error))
                    change_state("recovering")

                ready.set()
                healthy = notifier is not None and wd is not None
                wait = self._retry_interval if healthy else retry_delay
                if pending is not None:
                    wait = min(wait, max(0.0, pending - time.monotonic()))
                sources = [stop_read]
                if healthy:
                    sources.append(notifier.fileno())
                try:
                    readable, _, _ = select.select(sources, [], [], wait)
                except (OSError, ValueError) as error:
                    report_problem("select: %s" % error)
                    close_notifier()
                    pending = None
                    change_state("recovering")
                    stop_event.wait(retry_delay)
                    retry_delay = min(retry_delay * 2, self._max_retry_interval)
                    continue
                if stop_read in readable or stop_event.is_set():
                    break
                if healthy:
                    retry_delay = self._retry_interval
                    if last_error is not None:
                        _LOG.info("Configuration watcher recovered: %s", watched_dir)
                        last_error = None

                if healthy and notifier.fileno() in readable:
                    try:
                        events = notifier.read(timeout=0)
                    except (OSError, BlockingIOError) as error:
                        report_problem("read: %s" % error)
                        close_notifier()
                        pending = None
                        change_state("recovering")
                        stop_event.wait(retry_delay)
                        retry_delay = min(retry_delay * 2, self._max_retry_interval)
                        continue
                    reset_stream = False
                    for event in events:
                        if event.mask & flags.Q_OVERFLOW:
                            reset_stream = True
                            # Lost events mean a writer may still be open.
                            pending = None
                            break
                        if event.wd == link_wd and link_wd is not None:
                            if event.mask & self._LOST:
                                # MOVE_SELF does not release an inotify watch.
                                # Drop our old watch before rearming its path.
                                if not event.mask & flags.IGNORED:
                                    try:
                                        notifier.rm_watch(link_wd)
                                    except OSError:
                                        pass  # Already removed by the kernel.
                                link_wd = None
                                link_identity = None
                                link_replaced = True
                                # Reconcile the replacement before reloading.
                                pending = None
                            elif event.mask & flags.CLOSE_WRITE:
                                pending = time.monotonic()
                                pending_deletion = False
                            elif event.mask & flags.MODIFY:
                                # Await the latest CLOSE_WRITE.
                                pending = None
                            continue
                        if event.wd != wd:
                            continue
                        if event.mask & self._LOST:
                            reset_stream = True
                            pending = None
                            break
                        if watched_dir == parent and event.name == basename:
                            if event.mask & self._CHANGED:
                                pending = time.monotonic()
                                pending_deletion = False
                            elif event.mask & flags.CREATE:
                                if os.path.islink(self.path):
                                    # Link creation itself is atomic; regular
                                    # file creation does not imply write close.
                                    pending = time.monotonic()
                                    pending_deletion = False
                                else:
                                    # Hard links are indistinguishable from
                                    # newly opened files here: require a later
                                    # CLOSE_WRITE or atomic MOVED_TO.
                                    pending = None
                            elif event.mask & flags.MODIFY:
                                # New writes supersede any pending reload.
                                pending = None
                            elif event.mask & self._REMOVED:
                                pending = time.monotonic() + self._delete_grace
                                pending_deletion = True
                    if reset_stream:
                        # inotify(7) recommends rebuilding state and a fresh
                        # descriptor after lost events, not reusing queued IDs.
                        close_notifier()
                        pending = None
                        change_state("recovering")

                if pending is not None and time.monotonic() >= pending:
                    pending = None
                    if not pending_deletion or not os.path.lexists(self.path):
                        notify()
                if not healthy:
                    retry_delay = min(retry_delay * 2, self._max_retry_interval)
        finally:
            ready.set()
            close_notifier()
            os.close(stop_read)
            with self._lock:
                write_fd = self._stop_write
                if self._thread is threading.current_thread():
                    self._stop_write = None
                    self._state = "stopped"
                else:
                    write_fd = None
            if write_fd is not None:
                os.close(write_fd)
