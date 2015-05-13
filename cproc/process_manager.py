import os
import pwd
import errno
import asyncio
from functools import partial

from time import time, sleep

from cutil.logging import warn, info
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

    kill_all_on_exit = True
    
    _ignore_signals = False

    def __init__(self):
        policy = asyncio.get_event_loop_policy()
        w = self._watcher = InitChildWatcher()
        policy.set_child_watcher(w)
        w.add_no_processes_handler(self._no_processes)

    def _got_SIGTERM(self, signum, frame):
        info("SIGTERM received")
        if self._ignore_signals:
            return
        self._ignore_signals = True
        Reaper.sharedInstance().killAllProcesses()
        os._exit(0)

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
        print("NO PROCESSES!")
        loop = asyncio.get_event_loop()
        loop.call_later(0.5, loop.stop)

    def run(self, args, user=None):
        info("IN RUN")
        return SubProcess.spawn(args, user)

    def run_event_loop(self):
        "Sets up the event loop and runs it."

        loop = asyncio.get_event_loop()
        loop.run_forever()
        loop.close()
