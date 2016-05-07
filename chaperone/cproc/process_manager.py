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
from chaperone.cutil.env import Environment
from chaperone.cutil.notify import NotifySink
from chaperone.cutil.logging import warn, info, debug, error, set_log_level
from chaperone.cutil.misc import lazydict, objectplus
from chaperone.cutil.syslog import SyslogServer
from chaperone.cutil.errors import get_errno_from_exception

class CustomEventLoop(asyncio.SelectorEventLoop):
    def _make_socket_transport(self, sock, protocol, waiter=None, *,
                               extra=None, server=None):
        """
        Supports a special protocol method 'acquire_socket' which acceps only a socket.
        If it returns True, then the passed socket has been detached and no further
        action will be taken.  This is to support inetd-style processes.
        """
        if hasattr(protocol, 'acquire_socket') and protocol.acquire_socket(sock):
            if waiter:
                waiter.set_result(None)
            return None
        return super()._make_socket_transport(sock, protocol, waiter, extra=extra, server=server)

asyncio.DefaultEventLoopPolicy._loop_factory = CustomEventLoop


class TopLevelProcess(objectplus):
             
    send_sighup = False
    detect_exit = True

    _shutdown_timeout = None
    _ignore_signals = False
    _services_started = False
    _syslog = None
    _command = None
    _minimum_syslog_level = None
    _start_time = None
    _status_interval = None
    _family = None
    _exitcode = None

    _all_killed = False
    _killing_system = False
    _kill_future = None
    _config = None
    _pending = None

    _notify_enabled = False
    notify = None

    def __init__(self, config):
        self._config = config
        self._start_time = time()
        self._pending = set()

        self.notify = NotifySink() # whether or not we actually have a notify socket

        # wait at least 0.5 seconds, zero is totally pointless
        settings = config.get_settings()
        self._shutdown_timeout = settings.get('shutdown_timeout', 8) or 0.5

        self.detect_exit = settings.get('detect_exit', True)
        self.enable_syslog = settings.get('enable_syslog', True)

        policy = asyncio.get_event_loop_policy()
        w = self._watcher = InitChildWatcher(onNoProcesses = self._queue_no_processes)
        policy.set_child_watcher(w)
        self.loop.add_signal_handler(signal.SIGTERM, self.kill_system)
        self.loop.add_signal_handler(signal.SIGINT, self._got_sigint)

        self._status_interval = settings.get('status_interval', 30)

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

    def _queue_no_processes(self):
        # Any output from dead processes won't get queued into the logs if we
        # don't return to the event loop.
        self.loop.call_later(0.05, self._no_processes)

    def _no_processes(self, ignore_service_state = False):
        if not (ignore_service_state or self._services_started):
            return    # do not react during system initialization

        self._all_killed = True

        if not self._killing_system:
            if not self.detect_exit:
                return
            if self._family:
                ss = self._family.get_scheduled_services()
                if ss:
                    warn("system will remain active since there are scheduled services: " + ", ".join(s.name for s in ss))
                    return

        # Passed all checks, now kill system

        self.notify.stopping()

        debug("Final termination phase.")

        self._services_started = False
        if self._kill_future and not self._kill_future.cancelled():
            self._kill_future.cancel()
        self.activate(self._final_system_stop())

    @asyncio.coroutine
    def _final_system_stop(self):
        yield from asyncio.sleep(0.1)
        if self._syslog:
            self._syslog.close()
        if self._command:
            self._command.close()

        self._cancel_pending()
        self.loop.stop()

    def _got_sigint(self):
        print("\nCtrl-C ... killing chaperone.")
        self.kill_system(4, True)
        
    def signal_ready(self):
        """
        Tells any notify listener that the system is ready.  Does nothing if the system
        is dying due to errors, or if a kill is in progress.
        """
        if not self._services_started or self._killing_system:
            return
        self.notify.ready()

        # This is the time to set up the status monitor

        if self._status_interval and self._family and self._notify_enabled:
            self.activate(self._report_status())

    @asyncio.coroutine
    def _report_status(self):
        while self._status_interval:
            if self._family:
                self.notify.status(self._family.get_status())
                yield from asyncio.sleep(self._status_interval)

    def kill_system(self, errno = None, force = False):
        """
        Systematically shuts down the system.  With the 'force' argument set to true,
        does so even if a kill is already in progress.
        """
        if force:
            self._services_started = True
        elif self._killing_system:
            return

        if self._exitcode is None and errno is not None:
            self._exitcode = 1   # default exit for an error
            self.notify.error(errno)

        warn("Request made to kill system." + ((force and " (forced)") or ""))
        self._killing_system = True
        self._kill_future = asyncio.async(self._kill_system_co())

    def _cancel_pending(self):
        "Cancel any pending activated tasks"

        for p in list(self._pending):
            if not p.cancelled():
                p.cancel()

    @asyncio.coroutine
    def _kill_system_co(self):

        self.notify.stopping()

        self._cancel_pending()

        # Tell the family it's been nice.  It's unlikely we won't have a process family, but
        # it's optional, so we should handle the situation.

        wait_done = False       # indicates if shutdown_timeout has expired

        if self._family:
            for f in self._family.values():
                yield from f.final_stop()
            # let normal shutdown happen
            if self._watcher.number_of_waiters > 0 and self._shutdown_timeout:
                debug("still have {0} waiting, sleeping for shutdown_timeout={1}".format(self._watcher.number_of_waiters, self._shutdown_timeout))
                yield from asyncio.sleep(self._shutdown_timeout)
                wait_done = True

        try:
            os.kill(-1, signal.SIGTERM) # first try a sig term
            if self.send_sighup:
                os.kill(-1, signal.SIGHUP)
        except ProcessLookupError:
            debug("No processes remain when attempting to kill system, just stop.")
            self._no_processes(True)
            return

        if wait_done:                   # give a short wait just so the signals fire
            yield from asyncio.sleep(1) # these processes are unknowns
        else:
            yield from asyncio.sleep(self._shutdown_timeout)
            
        if self._all_killed:
            return

        info("Some processes remain after {0}secs.  Forcing kill".format(self._shutdown_timeout))

        try:
            os.kill(-1, signal.SIGKILL)
        except ProcessLookupError:
            debug("No processes when attempting to force quit")
            self._no_processes(True)
            return

    def activate_result(self, future):
        self._pending.discard(future)

    def activate(self, cr):
       future = asyncio.async(cr)
       future.add_done_callback(self.activate_result)
       self._pending.add(future)
       return future

    def _system_coro_check(self, f):
        if f.exception():
            error("system startup cancelled due to error: {0}".format(f.exception()))
            self.kill_system(get_errno_from_exception(f.exception()))

    def _system_started(self, startup, future=None):
        if future and not future.cancelled() and future.exception():
            self._system_coro_check(future)
            return
        info(self.version + ", ready.")
        if startup:
            future = self.activate(startup)
            future.add_done_callback(self._system_coro_check)

    @asyncio.coroutine
    def _start_system_services(self):

        self._notify_enabled = yield from self.notify.connect()

        if self.enable_syslog:
            self._syslog = SyslogServer()
            self._syslog.configure(self._config, self._minimum_syslog_level)

            try:
                yield from self._syslog.run()
            except PermissionError as ex:
                self._syslog = None
                warn("syslog service cannot be started: {0}", ex)
            else:
                self._syslog.capture_python_logging()
                info("Switching all chaperone logging to /dev/log")

        self._command = CommandServer(self)

        try:
            yield from self._command.run()
        except PermissionError as ex:
            self._command = None
            warn("command service cannot be started: {0}", ex)

    def run_event_loop(self, startup_coro = None, exit_when_done = True):
        """
        Sets up the event loop and runs it, setting up basic services such as syslog
        as well as the command services sockets.   Then, calls the startup coroutine (if any)
        to tailor the environment and start up other services as needed.
        """

        initfuture = asyncio.async(self._start_system_services())
        initfuture.add_done_callback(lambda f: self._system_started(startup_coro, f))

        self.loop.run_forever()
        self.loop.close()

        if exit_when_done:
            exit(self._exitcode or 0)

    @asyncio.coroutine
    def run_services(self, extra_services, disable_others = False):
        "Run all services."

        # First, determine our overall configuration for the services environment.

        services = self._config.get_services()

        if extra_services:
            services = services.deepcopy()
            if disable_others:
                for s in services.values():
                    s.enabled = False
            for s in extra_services:
                services.add(s)

        family = self._family = SubProcessFamily(self, services)
        tried_any = False
        errno = None

        try:
            tried_any = yield from family.run()
        except asyncio.CancelledError:
            pass
        finally:
            self._services_started = True

        if self.detect_exit:
            if not tried_any:
                warn("No service startups attempted (all disabled?) - exiting due to 'detect_exit=true'")
                self.kill_system()
            else:
                self._watcher.check_processes()
