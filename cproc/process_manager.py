import os
import pwd
import errno
import asyncio
from functools import partial

from time import time, sleep

from cutil.logging import warn, info, set_log_level
from cproc.watcher import InitChildWatcher

import signal

class SubProcess(object):

    pid = None

    _user_uid = None
    _user_gid = None
    _user_env = None

    @classmethod
    def spawn(cls, args, user=None):
        sp = cls(args, user)
        f = asyncio.async(sp.run())
        f.add_done_callback(sp._spawn_done)
        return f

    def _spawn_done(self, future):
        print("spawn_done! future={0} returncode={1}".format(future, self._proc.returncode))

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
        Execute set-up for the new process.
        """
        pwrec = pwd.getpwnam(user)
        self._user_uid = pwrec.pw_uid
        self._user_gid = pwrec.pw_gid
        self._user_env = {
            'HOME':       pwrec.pw_dir,
            'LOGNAME':    user,
            'USER':       user,
        }
            
    @asyncio.coroutine
    def run(self):
        args = self._prog_args
        info("Running %s... " % " ".join(args))
        create = asyncio.create_subprocess_exec(*self._prog_args, preexec_fn=self._setup_subprocess)
        proc = self._proc = yield from create
        yield from proc.wait()
        info("Process status for pid={0} is '{1}'".format(proc.pid, proc.returncode))


class TopLevelProcess(object):
             
    _cls_singleton = None

    exit_when_no_processes = True
    kill_all_timeout = 5
    send_sighup = False

    _ignore_signals = False
    _all_killed = False
    _killing_system = False

    def __init__(self):
        policy = asyncio.get_event_loop_policy()
        w = self._watcher = InitChildWatcher()
        policy.set_child_watcher(w)
        w.add_no_processes_handler(self._no_processes)
        self.loop.add_signal_handler(signal.SIGTERM, self.kill_system)

    @classmethod
    def sharedInstance(cls):
        "Return a singleton object for this class."
        if not cls._cls_singleton:
            cls._cls_singleton = TopLevelProcess()
        return cls._cls_singleton

    @property
    def debug(self):
        return asyncio.get_event_loop().get_debug()
    @debug.setter
    def debug(self, val):
        asyncio.get_event_loop().set_debug(val)

    @property
    def loop(self):
        return asyncio.get_event_loop()

    def _no_processes(self):
        print("NO PROCESSES!", self)
        self._all_killed = True
        if self.exit_when_no_processes:
            self.exit_when_no_processes = False # don't do this twice
            self.loop.call_later(0.5, self.loop.stop)

    def kill_system(self):
        if self._killing_system:
            return

        info("KILLING SYSTEM")
        self._killing_system = True

        try:
            os.kill(-1, signal.SIGTERM) # first try a sig term
            if self.send_sighup:
                os.kill(-1, signal.SIGHUP)
        except ProcessLookupError:
            info("No processes remain when attempting to kill system, just stop.")
            self._no_processes()
            return

        self.loop.call_later(self.kill_all_timeout, self._check_kill_all)

    def _check_kill_all(self):
        if self._all_killed:
            return

        info("Some processes remain after {0}secs.  Forcing kill".format(self.kill_all_timeout))

        try:
            os.kill(-1, signal.SIGKILL)
        except ProcessLookupError:
            info("No processes when attempting to force quit")
            self._no_processes()
            return

    def run(self, args, user=None):
        info("IN RUN")
        return SubProcess.spawn(args, user)

    def run_event_loop(self):
        "Sets up the event loop and runs it."

        self.loop.run_forever()
        self.loop.close()
