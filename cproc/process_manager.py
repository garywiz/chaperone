import os
from time import time, sleep

from cutil.logging import warn, info
import threading
import signal

def _ignore_signals_and_raise_keyboard_interrupt(signame):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    raise KeyboardInterrupt(signame)

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

    def __format__(self, spec):
        if spec:
            return int.__format__(self, spec)
        msg = "<ProcStatus"
        if self.exited:
            msg += " exit_status={0} \"{1}\"".format(self.exit_status, self.exit_message)
        if self.signaled:
            msg += " signal=%d" % self.signal
        if self.stopped:
            msg += " stoppped=%d" % self.signal
        return msg + ">"


class Reaper(threading.Thread):

    # Adjustable constants
    KILL_ALL_PROCESSES_TIMEOUT = 5
    FORCED_KILL_TIMEOUT = 2
    REAPER_SLEEP_TIMEOUT = 0.5

    # Class variables
    _cls_singleton = None

    # Instance variables
    _reaper_die = False
    _waiters = None
    _deadlist = None

    @classmethod
    def sharedInstance(cls):
        if not cls._cls_singleton:
            cls._cls_singleton = s = Reaper()
            s.start()
        return cls._cls_singleton

    def __init__(self):
        super(Reaper, self).__init__()
        self._deadlist = dict()
        self._waiters = dict()
        self._trigger = threading.Semaphore()
        self.daemon = True

    def run(self):
        while True:
            self._trigger.acquire(timeout=self.REAPER_SLEEP_TIMEOUT)
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid:
                self._reap(pid, status)
            if self._reaper_die:
                return

    def tickle(self, delay = 0.1):
        self._trigger.notify()
        if delay is not None:
            sleep(delay)

    def _reap(self, pid, status):
        info("reaping pid={0} status={1}".format(pid, ProcStatus(status)))
        self._deadlist[pid] = (status, time())
        waiter = self._waiters.get(pid)
        if waiter:
            del self._waiters[pid]  # No new waiters will appear because the deadlist will prevent this.  the GIL is our friend here.
            waiter.acquire()
            waiter.notify_all()
            waiter.release()

    def waitForProcess(self, pid):
        "Called by any thread which wants to wait until a particular child PID is reaped"
        if pid not in self._deadlist:
            waiter = self._waiters.get(pid)
            if not waiter:
                waiter = self._waiters[pid] = threading.Condition()
                waiter.acquire()
                waiter.wait()
                waiter.release()
        return ProcStatus(self._deadlist[pid][0])

    def terminate(self):
        assert not self._reaper_die
        assert threading.get_ident() != self.ident
        self._reaper_die = True
        self.tickle()
        self.join()

    @staticmethod
    def _terminate_world(timeout, signum):
        """
        Attempts to terminate all our children (real or adopted) using the given signal.
        Returns True if all were successfully terminated within the timeout period,
        False otherwise.
        """

        try:
            os.kill(-1, signum)
        except OSError:
            pass

        start_time = time()

        while True:
            try:
                os.waitpid(-1, timeout=0.10)
            except OSError as e:
                if e.errno == errno.ECHILD:
                    return True
                    break
            if time() - start_time > timeout:
                return False


    def killAllProcesses(self):
        "Terminate the reaper, then kill all processes."

        self.terminate()

        info("Killing all processes...")

        if self._terminate_world(signal.SIGTERM, self.KILL_ALL_PROCESSES_TIMEOUT):
            return
        
        warn("Not all processes have exited in {0}secs. Forcing exit.".format(self.KILL_ALL_PROCESSES_TIMEOUT))
        if self._terminate_world(signal.SIGKILL, self.FORCED_KILL_TIMEOUT):
            return

        warn("Processes remain even after forced kill!")


class SubProcess(threading.Thread):

    pid = None

    @classmethod
    def spawn(cls, args):
        sp = cls(args)
        sp.start()
        return sp

    def __init__(self, args):
        self.__args = args
        super(SubProcess, self).__init__()

    def run(self):
        args = self.__args
        info("Running %s... " % " ".join(args))
        self.pid = os.spawnvp(os.P_NOWAIT, args[0], self.__args)
        status = Reaper.sharedInstance().waitForProcess(self.pid)
        info("Process status for pid={0} is '{1}'".format(self.pid, status))

class TopLevelProcess(object):
             
    _cls_singleton = None

    kill_all_on_exit = True
    
    def __init__(self):
        signal.signal(signal.SIGTERM, lambda signum, frame: _ignore_signals_and_raise_keyboard_interrupt('SIGTERM'))
        signal.signal(signal.SIGINT, lambda signum, frame: _ignore_signals_and_raise_keyboard_interrupt('SIGINT'))

    @classmethod
    def sharedInstance(cls):
        "Return a singleton object for this class."
        if not cls._cls_singleton:
            cls._cls_singleton = TopLevelProcess()
        return cls._cls_singleton

    def mainloop(self):
        try:
            self.mainloop_internal()
        except KeyboardInterrupt:
            warn("Init system aborted by KB interrupt.")
            exit(2)
        finally:
            if self.kill_all_on_exit:
                Reaper.sharedInstance().killAllProcesses()

    def run(self, args):
        return SubProcess.spawn(args)
