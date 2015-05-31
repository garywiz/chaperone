import os
import asyncio
import shlex
import importlib

from time import time, sleep

import chaperone.cutil.syslog_info as syslog_info

from chaperone.cutil.logging import warn, info, debug, error
from chaperone.cutil.misc import lazydict, Environment, lookup_user
from chaperone.cutil.format import TableFormatter

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
            warn(line, facility=syslog_info.LOG_DAEMON)
        else:
            info(line, facility=syslog_info.LOG_DAEMON)


class SubProcess(object):

    pid = None
    service = None              # service object
    family = None

    _proc = None
    _pwrec = None               # the pwrec looked up for execution user/group
    _started = False            # TRUE if the process is started, or disabled but start was attempted

    _starts_allowed = 0         # number of starts permitted before we give up

    _pending = None             # pending futures

    # Class variables
    _cls_ptdict = lazydict()    # dictionary of process types

    def __new__(cls, service, family=None):
        """
        New Subprocesses are managed by subclasses derived from SubProcess so that 
        complex process behavior can be isolated and loaded only when needed.  That
        keeps this basic superclass logic less convoluted.
        """
        # If we are trying to create a subclass, just inherit __new__ simply
        if cls is not SubProcess:
            return super(SubProcess, cls).__new__(cls)

        # Lookup and cache the class object used to create this type.
        stype = service.type
        ptcls = SubProcess._cls_ptdict.get(stype)
        if not ptcls:
            mod = importlib.import_module('chaperone.cproc.pt.' + stype)
            ptcls = SubProcess._cls_ptdict[stype] = getattr(mod, stype.capitalize() + 'Process')
            assert issubclass(ptcls, cls)

        return ptcls(service, family)
            
    def __init__(self, service, family=None):

        self.service = service
        self.family = family

        self._pending = set()

        # We manage restart counts so that multiple attempts to reset or restart
        # don't result in constant resets.  We allow one extra for the initial start.
        self._starts_allowed = self.service.restart_limit + 1

        # The environment has already been modified to reflect our chosen service uid/gid
        uid = service.environment.uid
        gid = service.environment.gid

        if uid is not None:
            self._pwrec = lookup_user(uid, gid)

        if not service.exec_args:
            raise Exception("No command or arguments provided for service")

    def __getattr__(self, name):
        "Proxies value from the service description if we don't override them."
        return getattr(self.service, name)

    def _setup_subprocess(self):
        if self._pwrec:
            os.setgid(self._pwrec.pw_gid)
            os.setuid(self._pwrec.pw_uid)
            try:
                os.chdir(self._pwrec.pw_dir)
            except Exception as ex:
                pass
        return

    @property
    def status(self):
        serv = self.service
        proc = self._proc

        rs = ""
        if serv.restart and self._starts_allowed > 0:
            rs = "+r#" + str(self._starts_allowed)

        if self._started:
            if proc:
                rc = proc.returncode
                if proc.returncode is None:
                    return "running"
                else:
                    return proc.returncode.briefly + rs
                    
        if not serv.enabled:
            return "disabled"

        if rs:
            return rs

        return None

    @asyncio.coroutine
    def start(self, enable = True):
        """
        Runs this service if it is enabled and has not already been started.  Starts
        prerequisite services first.  A service is considered started if
           a) It is enabled, and started up normally.
           b) It is disabled, and an attempt was made to start it.
           c) An error occurred, it did not start, but failures we an acceptable
              outcome and the service has not been reset since the errors occurred.
        """

        service = self.service

        if enable and not service.enabled:
            if enable:
                service.enabled = True
                if not self._proc:
                    self._started = False
                debug("service {0} enabled upon start", service.name)

        if self._started:
            return
        self._started = True

        if not service.enabled:
            debug("service {0} not enabled, will be skipped", service.name)
            return

        if self.family:
            if service.prerequisites:
                prereq = [self.family.get(p) for p in service.prerequisites]
                for p in prereq:
                    if p:
                        yield from p.start(enable)
            # idle only makes sense for families
            if service.service_group == 'IDLE' and service.idle_delay and not hasattr(self.family, '_idle_hit'):
                self.family._idle_hit = True
                debug("IDLE transition hit.  delaying for {0} seconds", service.idle_delay)
                yield from asyncio.sleep(service.idle_delay)

        try:
            yield from self._start_service()
        except Exception as ex:
            if isinstance(ex, FileNotFoundError) and service.optional:
                info("optional service {0} ignored due to exception: {1}", service.name, ex)
            elif service.ignore_failures:
                info("service {0} ignoring failures. Exception: {1}", service.name, ex)
            else:
                raise

    @asyncio.coroutine
    def _start_service(self):
        service = self.service

        debug("{0} attempting start '{1}'... ".format(service.name, " ".join(service.exec_args)))

        kwargs = dict()

        if service.stdout == 'log':
            kwargs['stdout'] = asyncio.subprocess.PIPE
        if service.stderr == 'log':
            kwargs['stderr'] = asyncio.subprocess.PIPE

        env = service.environment
        if env:
            env = env.get_public_environment()

        if service.debug:
            if not env:
                debug("{0} environment is empty", service.name)
            else:
                debug("{0} environment:", service.name)
                for k,v in env.items():
                    debug(" {0} = '{1}'".format(k,v))


        create = asyncio.create_subprocess_exec(*service.exec_args, preexec_fn=self._setup_subprocess,
                                                env=env, **kwargs)
        if service.exit_kills:
            warn("system wll be killed when '{0}' exits", " ".join(service.exec_args))
            yield from asyncio.sleep(0.2)

        proc = self._proc = yield from create

        self.pid = proc.pid

        if service.stdout == 'log':
            self.add_pending(asyncio.async(_process_logger(proc.stdout, 'stdout')))
        if service.stderr == 'log':
            self.add_pending(asyncio.async(_process_logger(proc.stderr, 'stderr')))

        if service.exit_kills:
            self.add_pending(asyncio.async(self._wait_kill_on_exit()))

        yield from self.process_started_co()

    @asyncio.coroutine
    def _wait_kill_on_exit(self):
        yield from self.wait()
        self._kill_system()

    @asyncio.coroutine
    def _abnormal_exit(self, code):
        service = self.service

        if service.exit_kills:
            warn("{0} terminated abnormally with {1}", service.name, code)
            return

        # A disabled service should not do recovery

        if not service.enabled:
            return

        if service.restart and self._starts_allowed > 0:
            controller = self.family.controller
            if controller.system_alive:
                if service.restart_delay:
                    info("{0} pausing between restart retries", service.name)
                    yield from asyncio.sleep(service.restart_delay)
            if controller.system_alive:
                yield from self.reset(True)
                yield from self.start(False)
            return

        if service.ignore_failures:
            debug("{0} abnormal process exit ignored due to ignore_failures=true", service.name)
            return

        error("{0} terminated abnormally with {1}", service.name, code)
        self._kill_system()

    def _kill_system(self):
        self.family.controller.kill_system()

    def add_pending(self, future):
        self._pending.add(future)
        future.add_done_callback(lambda f: self._pending.discard(future))

    @asyncio.coroutine
    def reset(self, restart = False):
        if self._proc:
            if self._proc.returncode is None:
                self.terminate()
                yield from self.wait()
                self._proc = None
                self.pid = None

        self._started = False

        if restart:
            self._starts_allowed -= 1
        else:
            self._starts_allowed = self.service.restart_limit + 1
        
    @asyncio.coroutine
    def stop(self):
        if not (self._proc and self._proc.returncode is None):
            return

        self.service.enabled = False
        self._starts_allowed = 0
        yield from self.reset()
        
    @asyncio.coroutine
    def final_stop(self):
        "Called when the whole system is killed, but before drastic measures are taken."
        for p in list(self._pending):
            if not p.cancelled():
                p.cancel()

    def terminate(self):
        self._proc and self._proc.terminate()

    @asyncio.coroutine
    def timed_wait(self, timeout, func = None):
        """
        Timed wait waits for process completion.  If process completion occurs normally, None is returned.

        Upon timeout either:
        1.  asyncio.TimeoutError is raised if 'func' is not provided, or...
        2.  func is called and the result is returned from timed_wait().
        """
        try:
            yield from asyncio.wait_for(asyncio.shield(self.wait()), timeout)
        except asyncio.TimeoutError:
            if not func:
                raise
            return func()

    @asyncio.coroutine
    def wait(self):
        proc = self._proc
        if not proc:
            raise Exception("Process not running, can't wait")
        yield from proc.wait()
        info("Process exit status for pid={0} is '{1}'".format(proc.pid, proc.returncode))
        return proc.returncode


class SubProcessFamily(lazydict):

    controller = None           # top level system controller

    def __init__(self, controller, startup_list):
        """
        Given a pre-analyzed list of processes, complete with prerequisites, build a process
        family.
        """
        super().__init__()

        self.controller = controller

        for s in startup_list:
            self[s.name] = SubProcess(s, family = self)

    @asyncio.coroutine
    def run(self):
        """
        Runs the family, starting up services in dependency order.  If any problems
        occur, an exception is raised.
        """

        for s in self.values():
            yield from s.start(False)

    def get_status_formatter(self):
        df = TableFormatter('pid', 'name', 'enabled', 'status', sort='name')
        df.add_rows(self.values())
        return df

