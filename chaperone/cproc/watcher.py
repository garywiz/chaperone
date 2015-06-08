import os
import asyncio
import threading

from functools import partial
from asyncio.unix_events import BaseChildWatcher

from chaperone.cutil.logging import warn, info, debug
from chaperone.cutil.misc import get_signal_name

class ProcStatus(int):
    def __new__(cls, val):
        return int.__new__(cls, val)

    @property
    def exited(self):
        return os.WIFEXITED(self)

    @property
    def signaled(self):
        return os.WIFSIGNALED(self)

    @property
    def stopped(self):
        return os.WIFSTOPPED(self)

    @property
    def continued(self):
        return os.WIFCONTINUED(self)

    @property
    def exit_status(self):
        return (os.WIFEXITED(self) or None) and os.WEXITSTATUS(self)

    @property
    def normal_exit(self):
        return self.exit_status == 0 and not (self.signaled or self.stopped)

    @property
    def exit_message(self):
        es = self.exit_status
        if es is not None:
            return os.strerror(es)
        return None
        
    @property
    def signal(self):
        if os.WIFSTOPPED(self):
            return os.WSTOPSIG(self)
        if os.WIFSIGNALED(self):
            return os.WTERMSIG(self)
        return None

    @property
    def briefly(self):
        if self.signaled or self.stopped:
            return get_signal_name(self.signal)
        if self.exited:
            return "exit({0})".format(self.exit_status)
        return '?'

    def __format__(self, spec):
        if spec:
            return int.__format__(self, spec)
        msg = "<ProcStatus"
        if self.exited:
            msg += " exit_status={0}".format(self.exit_status)
        if self.signaled:
            msg += " signal=%d" % self.signal
        if self.stopped:
            msg += " stoppped=%d" % self.signal
        return msg + ">"


class InitChildWatcher(BaseChildWatcher):
    """An init-responsible child watcher.

    Plugs into the asyncio child watcher framework to allow harvesting of both known and unknown
    child processes.
    """
    def __init__(self):
        super().__init__()
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

    def add_no_processes_handler(self, callback, *args):
        self._no_processes = partial(callback, *args)

    def remove_no_processes_handler(self):
        self._no_processes = None

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

    def _do_waitpid_all(self):
        # Because of signal coalescing, we must keep calling waitpid() as
        # long as we're able to reap a child.
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                debug("REAP pid={0},status={1}".format(pid,status))
            except ChildProcessError:
                # No more child processes exist.
                if self._had_children and self._no_processes:
                    self._no_processes()
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
