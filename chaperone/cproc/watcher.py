import os
import asyncio
import threading

from functools import partial
from asyncio.unix_events import BaseChildWatcher

from chaperone.cutil.logging import warn, info, debug
from chaperone.cutil.proc import ProcStatus
from chaperone.cutil.misc import get_signal_name
from chaperone.cutil.events import EventSource

class InitChildWatcher(BaseChildWatcher):
    """An init-responsible child watcher.

    Plugs into the asyncio child watcher framework to allow harvesting of both known and unknown
    child processes.
    """
    def __init__(self, **kwargs):
        super().__init__()
        self.events = EventSource(**kwargs)
        self._callbacks = {}
        self._lock = threading.Lock()
        self._zombies = {}
        self._forks = 0
        self._no_processes = None
        self._had_children = False

    def close(self):
        self._callbacks.clear()
        self._zombies.clear()
        super().close()

    def __enter__(self):
        with self._lock:
            self._forks += 1

            return self

    def __exit__(self, a, b, c):
        with self._lock:
            self._forks -= 1

            if self._forks or not self._zombies:
                return

            collateral_victims = str(self._zombies)
            self._zombies.clear()

        info(
            "Caught subprocesses termination from unknown pids: %s",
            collateral_victims)

    @property
    def number_of_waiters(self):
        return len(self._callbacks)

    def add_child_handler(self, pid, callback, *args):
        assert self._forks, "Must use the context manager"
        with self._lock:
            try:
                returncode = self._zombies.pop(pid)
            except KeyError:
                # The child is running.
                self._callbacks[pid] = callback, args
                return

        # The child is dead already. We can fire the callback.
        callback(pid, returncode, *args)

    def remove_child_handler(self, pid):
        try:
            del self._callbacks[pid]
            return True
        except KeyError:
            return False

    def check_processes(self):
        # Checks to see if any processes terminated, and triggers onNoProcesses
        self._do_waitpid_all()

    def _do_waitpid_all(self):
        # Because of signal coalescing, we must keep calling waitpid() as
        # long as we're able to reap a child.
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                debug("REAP pid={0},status={1}".format(pid,status))
            except ChildProcessError:
                # No more child processes exist.
                if self._had_children:
                    debug("no child processes present")
                    self.events.onNoProcesses()
                return
            else:
                self._had_children = True
                if pid == 0:
                    # A child process is still alive.
                    return

                returncode = ProcStatus(status)

            with self._lock:
                try:
                    callback, args = self._callbacks.pop(pid)
                except KeyError:
                    # unknown child
                    if self._forks:
                        # It may not be registered yet.
                        self._zombies[pid] = returncode
                        continue
                    callback = None

            if callback is None:
                info(
                    "Caught subprocess termination from unknown pid: "
                    "%d -> %d", pid, returncode)
            else:
                callback(pid, returncode, *args)
