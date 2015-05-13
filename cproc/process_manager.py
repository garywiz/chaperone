import os
import pwd
import errno
from subprocess import Popen
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
            msg += " exit_status={0}".format(self.exit_status)
        if self.signaled:
            msg += " signal=%d" % self.signal
        if self.stopped:
            msg += " stoppped=%d" % self.signal
        return msg + ">"


class Reaper(threading.Thread):

    # Adjustable constants
    KILL_ALL_PROCESSES_TIMEOUT = 5
    #KILL_HUP_TIMEOUT = 2
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
        lastpid = -1
        while True:
            if lastpid == 0:
                self._trigger.acquire(timeout=self.REAPER_SLEEP_TIMEOUT)
            try:
                lastpid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                lastpid = 0
            if lastpid:
                self._reap(lastpid, status)
            if self._reaper_die:
                return

    def tickle(self, delay = 0.1):
        self._trigger.release()
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
    def _terminate_world(signum, timeout):
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
                stat = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return True
            except OSError as e:
                if e.errno == errno.ECHILD:
                    return True
                    break

            if stat[0] == 0:    # if waiting on processes, delay slightly
                sleep(0.10)
            else:
                info("GOT stat: " + str(stat))

            if time() - start_time > timeout:
                return False


    def killAllProcesses(self):
        "Terminate the reaper, then kill all processes."

        self.terminate()

        info("Killing all processes...")

        if self._terminate_world(signal.SIGTERM, self.KILL_ALL_PROCESSES_TIMEOUT):
            return

        warn("Not all processes have exited in {0}secs. Force quit.".format(self.KILL_ALL_PROCESSES_TIMEOUT))

        if self._terminate_world(signal.SIGKILL, self.FORCED_KILL_TIMEOUT):
            return

        warn("Processes remain even after forced kill!")


class SubProcess(threading.Thread):

    pid = None

    _user_uid = None
    _user_gid = None
    _user_env = None

    @classmethod
    def spawn(cls, args, user=None):
        sp = cls(args, user)
        sp.start()
        return sp

    def __init__(self, args, user=None):
        super(SubProcess, self).__init__()
        self._prog_args = args
        if user:
            self._setup_user(user)

    def _setup_subprocess(self):
        if self._user_uid:
            os.setgid(self._user_gid)
            os.setuid(self._user_uid)
            os.environ.update(self._user_env)

    def _setup_user(self, user):
        """
        Execute set-up for the new process.  NOTE that the absolute minimum here is important, otherwise
        the thread state may lock-up.  See warning about preexec_fn at https://docs.python.org/3.4/library/subprocess.html.
        """
        pwrec = pwd.getpwnam(user)
        self._user_uid = pwrec.pw_uid
        self._user_gid = pwrec.pw_gid
        self._user_env = {
            'HOME':       pwrec.pw_dir,
            'LOGNAME':    user,
            'USER':       user,
        }
            
    def run(self):
        args = self._prog_args
        info("Running %s... " % " ".join(args))
        self._popen = Popen(self._prog_args, preexec_fn=self._setup_subprocess)
        status = Reaper.sharedInstance().waitForProcess(self._popen.pid)
        info("Process status for pid={0} is '{1}'".format(self.pid, status))

class TopLevelProcess(object):
             
    _cls_singleton = None

    kill_all_on_exit = True
    
    _ignore_signals = False

    def _got_SIGTERM(self, signum, frame):
        info("SIGTERM received")
        if self._ignore_signals:
            return
        self._ignore_signals = True
        Reaper.sharedInstance().killAllProcesses()
        os._exit(0)

    def __init__(self):
        signal.signal(signal.SIGTERM, self._got_SIGTERM)

    @classmethod
    def sharedInstance(cls):
        "Return a singleton object for this class."
        if not cls._cls_singleton:
            cls._cls_singleton = TopLevelProcess()
        return cls._cls_singleton

    def run(self, args, user=None):
        return SubProcess.spawn(args, user)
