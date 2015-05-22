import os
import pwd
import errno
import asyncio
import shlex
import signal
import logging
from logging.handlers import SysLogHandler

from functools import partial
from time import time, sleep

from chaperone.cutil.logging import warn, info, debug, error, set_python_log_level, enable_syslog_handler
from chaperone.cproc.watcher import InitChildWatcher
from chaperone.cproc.commands import CommandServer
from chaperone.cutil.syslog import SyslogServer
from chaperone.cutil.misc import lazydict, Environment
from chaperone.cproc.version import DISPLAY_VERSION

@asyncio.coroutine
def _process_logger(stream, kind):
    while True:
        data = yield from stream.readline()
        if not data:
            return
        line = data.decode('ascii').rstrip()
        if kind == 'stderr':
            # we map to warning because stderr output is "to be considered" and not strictly
            # erroneous
            warn(line, facility=SysLogHandler.LOG_DAEMON)
        else:
            info(line, facility=SysLogHandler.LOG_DAEMON)

class SubProcess(object):

    pid = None
    name = None

    _user_uid = None
    _user_gid = None
    _user_env = None
    _proc = None
    _stdout = "inherit"
    _stderr = "inherit"

    @classmethod
    @asyncio.coroutine
    def spawn(cls, args=None, user=None, service=None, wait=False, env=None):
        debug("spawn: {0}".format((args, user, service)))
        sp = cls(args, user)
        if service:
            sp.configure(service)
        yield from sp.run(env=env)
        if wait:
            yield from sp.wait()

    def __init__(self, args=None, user=None):
        super().__init__()
        self._prog_args = args
        if user:
            self._setup_user(user)

    def configure(self, service):
        args = None
        self.name = service.name
        self._stdout = service.stdout
        self._stderr = service.stderr

        if service.command:
            assert not (service.command and (service.bin or service.args)), "bin/args and command config are mutually-exclusive"
            args = shlex.split(service.command)
        elif service.bin:
            args = [service.bin] + shlex.split(service.args or '')
        else:
            raise Exception("No command or arguments provided for service")
        self._prog_args = args

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
    def run(self, env=None):
        args = self._prog_args
        assert args, "No arguments provided to SubProcess.run()"
        info("Running %s... " % " ".join(args))
        kwargs = dict()

        if self._stdout == 'log':
            kwargs['stdout'] = asyncio.subprocess.PIPE
        if self._stderr == 'log':
            kwargs['stderr'] = asyncio.subprocess.PIPE

        create = asyncio.create_subprocess_exec(*self._prog_args, preexec_fn=self._setup_subprocess,
                                                env=env, **kwargs)
        proc = self._proc = yield from create

        if self._stdout == 'log':
            asyncio.async(_process_logger(proc.stdout, 'stdout'))
        if self._stderr == 'log':
            asyncio.async(_process_logger(proc.stderr, 'stderr'))

    @asyncio.coroutine
    def wait(self):
        proc = self._proc
        if not proc:
            raise Exception("Process not started, can't wait")
        yield from proc.wait()
        info("Process exit status for pid={0} is '{1}'".format(proc.pid, proc.returncode))

        

class TopLevelProcess(object):
             
    _cls_singleton = None

    exit_when_no_processes = True
    kill_all_timeout = 5
    send_sighup = False

    _ignore_signals = False
    _all_killed = False
    _killing_system = False
    _enable_exit = False
    _syslog = None
    _command = None
    _minimum_syslog_level = None

    def __init__(self):
        policy = asyncio.get_event_loop_policy()
        w = self._watcher = InitChildWatcher()
        policy.set_child_watcher(w)
        w.add_no_processes_handler(self._no_processes)
        self.loop.add_signal_handler(signal.SIGTERM, self.kill_system)
        self.loop.add_signal_handler(signal.SIGINT, self._got_sigint)

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

        levid = getattr(logging, level.upper(), None)
        if not levid:
            raise Exception("Not a valid log level: {0}".format(level))
        set_python_log_level(levid)
        self._minimum_syslog_level = levid
        self.debug = (levid == logging.DEBUG)
        if self._syslog:
            self._syslog.reset_minimum_priority(levid)
        info("Forcing all log output to '{0}' or greater", level)

    def _no_processes(self):
        self._all_killed = True
        if self._enable_exit and (self._killing_system or self.exit_when_no_processes):
            debug("Final termination phase.")
            self._enable_exit = False
            self.loop.call_later(0.5, self._final_stop)

    def _final_stop(self):
        if self._syslog:
            self._syslog.close()
        if self._command:
            self._command.close()
        self.loop.stop()

    def _got_sigint(self):
        print("\nCtrl-C ... killing chaperone.")
        self.kill_system()
        
    def kill_system(self):
        if self._killing_system:
            return

        warn("Request made to kill system.")
        self._killing_system = True

        try:
            os.kill(-1, signal.SIGTERM) # first try a sig term
            if self.send_sighup:
                os.kill(-1, signal.SIGHUP)
        except ProcessLookupError:
            debug("No processes remain when attempting to kill system, just stop.")
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
        return SubProcess.spawn(args, user, wait=wait, env=config.get_environment())

    def _syslog_started(self, f):
        enable_syslog_handler()
        info("Switching all chaperone logging to /dev/log")

    def _system_started(self, f, startup):
        info("chaperone version {0}, ready.", DISPLAY_VERSION)
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
    def run_services(self, config):
        "Run services from the speicified config (an instance of cutil.config.Configuration)"

        # First, determine our overall configuration for the services environment.

        masterenv = config.get_environment()

        slist = [s for s in config.get_services().get_startup_list() if s.enabled]

        for n in range(len(slist)):
            if n == 0:
                info("Service Startup order...")
            info("#{1}. Service {0.name}, ignore_failures={0.ignore_failures}", slist[n], n+1)

        for s in slist:
            debug("Running service: " + str(s))
            subenv = Environment(s, masterenv)
            try:
                yield from SubProcess.spawn(service=s, env=subenv)
            except Exception as ex:
                debug("Process could not be started due to exception: {0}", ex)
                if isinstance(ex, FileNotFoundError) and s.optional:
                    warn("Optional service {0} ignored due to exception: {1}", s.name, ex)
                elif s.ignore_failures:
                    warn("Service {0} ignoring failures.  Not started due to exception: {1}", s.name, ex)
                else:
                    self._enable_exit = True
                    raise

        self._enable_exit = True
