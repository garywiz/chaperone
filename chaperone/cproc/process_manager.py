import os
import pwd
import errno
import asyncio
import shlex
import signal
import datetime

from functools import partial
from time import time, sleep

import chaperone.cutil.syslog_info as syslog_info

from chaperone.cproc.commands import CommandServer
from chaperone.cproc.version import DISPLAY_VERSION
from chaperone.cproc.watcher import InitChildWatcher
from chaperone.cproc.subproc import SubProcess, SubProcessFamily
from chaperone.cutil.config import ServiceConfig
from chaperone.cutil.logging import warn, info, debug, error, set_log_level, enable_syslog_handler
from chaperone.cutil.misc import lazydict, Environment, objectplus
from chaperone.cutil.syslog import SyslogServer

class TopLevelProcess(objectplus):
             
    exit_when_no_processes = True
    kill_all_timeout = 5
    send_sighup = False

    _ignore_signals = False
    _enable_exit = False
    _syslog = None
    _command = None
    _minimum_syslog_level = None
    _start_time = None
    _family = None

    _all_killed = False
    _killing_system = False
    _kill_future = None

    def __init__(self):
        self._start_time = time()
        policy = asyncio.get_event_loop_policy()
        w = self._watcher = InitChildWatcher()
        policy.set_child_watcher(w)
        w.add_no_processes_handler(self._no_processes)
        self.loop.add_signal_handler(signal.SIGTERM, self.kill_system)
        self.loop.add_signal_handler(signal.SIGINT, self._got_sigint)

    @property
    def debug(self):
        return asyncio.get_event_loop().get_debug()
    @debug.setter
    def debug(self, val):
        asyncio.get_event_loop().set_debug(val)

    @property
    def loop(self):
        return asyncio.get_event_loop()

    @property
    def system_alive(self):
        """
        Returns true if the system is considered "alive" and new processes, restarts, and other
        normal operations should proceed.   Generally, the system is alive until it is killed,
        but the process of shutting down the system may be complex and time consuming, and
        in the future there may be other factors which cause us to suspend
        normal system operation.
        """
        return not self._killing_system

    @property
    def version(self):
        "Returns version identifier"
        return "chaperone version {0}".format(DISPLAY_VERSION)

    @property
    def uptime(self):
        return datetime.timedelta(seconds = time() - self._start_time)

    @property
    def services(self):
        return self._family

    def force_log_level(self, level = None):
        """
        Specifies the *minimum* logging level that will be applied to all syslog entries.
        This is primarily useful for debugging, where you want to override any limitations
        imposed on log file entries.

        As a (convenient) side-effect, if the level is DEBUG, then debug features of both
        asyncio as well as chaperone will be enabled.

        If level is not provided, then returns the current setting.
        """
        if level is None:
            return self._minimum_syslog_level

        levid = syslog_info.PRIORITY_DICT.get(level.lower(), None)
        if not levid:
            raise Exception("Not a valid log level: {0}".format(level))
        set_log_level(levid)
        self._minimum_syslog_level = levid
        self.debug = (levid == syslog_info.LOG_DEBUG)
        if self._syslog:
            self._syslog.reset_minimum_priority(levid)
        info("Forcing all log output to '{0}' or greater", level)

    def _no_processes(self):
        self._all_killed = True
        if self._enable_exit and (self._killing_system or self.exit_when_no_processes):
            debug("Final termination phase.")
            self._enable_exit = False
            if self._kill_future and not self._kill_future.cancelled():
                self._kill_future.cancel()
            self.loop.call_later(0.1, self._final_stop)

    def _final_stop(self):
        if self._syslog:
            enable_syslog_handler(False)
            self._syslog.close()
        if self._command:
            self._command.close()
        self.loop.stop()

    def _got_sigint(self):
        print("\nCtrl-C ... killing chaperone.")
        self.kill_system(True)
        
    def kill_system(self, force = False):
        if force:
            self._enable_exit = True
        elif self._killing_system:
            return

        warn("Request made to kill system." + ((force and " (forced)") or ""))
        self._killing_system = True
        self._kill_future = asyncio.async(self._kill_system_co())

    @asyncio.coroutine
    def _kill_system_co(self):

        if self._family:
            for f in self._family.values():
                yield from f.final_stop()

        try:
            os.kill(-1, signal.SIGTERM) # first try a sig term
            if self.send_sighup:
                os.kill(-1, signal.SIGHUP)
        except ProcessLookupError:
            debug("No processes remain when attempting to kill system, just stop.")
            self._no_processes()
            return

        yield from asyncio.sleep(self.kill_all_timeout)
        if self._all_killed:
            return

        info("Some processes remain after {0}secs.  Forcing kill".format(self.kill_all_timeout))

        try:
            os.kill(-1, signal.SIGKILL)
        except ProcessLookupError:
            debug("No processes when attempting to force quit")
            self._no_processes()
            return

    def activate_result(self, future):
        debug("DISPATCH RESULT", future)

    def activate(self, cr):
       future = asyncio.async(cr)
       future.add_done_callback(self.activate_result)
       return future

    def run(self, args, user=None, wait=False, config=None):
        sdict = {'stdout': 'inherit',
                 'stderr': 'inherit'}
        env = config.get_environment()
        # Specifying a user overrides both the environment user as well
        # as the exec user.
        if user:
            env = Environment(env, uid = user)
        serv = ServiceConfig(sdict, env = env)
        return SubProcess.spawn(serv, args, wait=wait)

    def _syslog_started(self, f):
        enable_syslog_handler()
        info("Switching all chaperone logging to /dev/log")

    def _system_started(self, f, startup):
        info(self.version + ", ready.")
        if startup:
            self.activate(startup)

    def run_event_loop(self, config, startup_coro = None):
        """
        Sets up the event loop and runs it, setting up basic services such as syslog
        as well as the command services sockets.   Then, calls the startup coroutine (if any)
        to tailor the environment and start up other services as needed.
        """

        self._syslog = SyslogServer()
        self._syslog.configure(config, self._minimum_syslog_level)

        syf = self._syslog.run()
        syf.add_done_callback(self._syslog_started)

        self._command = CommandServer(self)
        cmdf = self._command.run()

        f = asyncio.gather(syf, cmdf)
        f.add_done_callback(lambda f: self._system_started(f, startup_coro))

        self.loop.run_forever()
        self.loop.close()

    @asyncio.coroutine
    def run_services(self, config, extra_services):
        "Run services from the speicified config (an instance of cutil.config.Configuration)"

        # First, determine our overall configuration for the services environment.

        services = config.get_services()

        if extra_services:
            services = services.deepcopy()
            for s in extra_services:
                services.add(s)

        family = self._family = SubProcessFamily(self, services.get_startup_list())
        try:
            yield from family.run()
        finally:
            self._enable_exit = True
