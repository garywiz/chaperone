import os
import asyncio
import shlex
import importlib

from time import time, sleep

import chaperone.cutil.syslog_info as syslog_info

from chaperone.cutil.env import Environment
from chaperone.cutil.logging import warn, info, debug, error
from chaperone.cutil.misc import lazydict, lookup_user, get_signal_name
from chaperone.cutil.format import TableFormatter

@asyncio.coroutine
def _process_logger(stream, kind, name):
    name = name.replace('.service', '')
    while True:
        data = yield from stream.readline()
        if not data:
            return
        line = data.decode('ascii', 'ignore').rstrip()
        if not line:
            continue            # ignore blank lines in stdout/stderr
        if kind == 'stderr':
            # we map to warning because stderr output is "to be considered" and not strictly
            # erroneous
            warn("({0}) {1}".format(name, line), facility=syslog_info.LOG_DAEMON)
        else:
            info("({0}) {1}".format(name, line), facility=syslog_info.LOG_DAEMON)


class SubProcess(object):

    pid = None
    service = None              # service object
    family = None
    process_timeout = 30.0      # process_timeout will be set to this unless it is overridden by 
                                # the service entry

    _proc = None
    _pwrec = None               # the pwrec looked up for execution user/group
    _cond_starting = None       # a condition which, if present, indicates that this service is starting
    _started = False            # true if a start has occurred, either successful or not
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

        if service.process_timeout is not None:
            self.process_timeout = service.process_timeout

        # Allow no auto-starts
        self._starts_allowed = 0

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

    def __setattr__(self, name, value):
        "Any service object attribute supercedes our own except for privates."
        if name[0:0] != '_' and hasattr(self.service, name):
            setattr(self.service, name, value)
        else:
            object.__setattr__(self, name, value)

    def _setup_subprocess(self):
        if self._pwrec:
            os.setgid(self._pwrec.pw_gid)
            os.setuid(self._pwrec.pw_uid)
            if self.setpgrp:
                os.setpgrp()
            if not self.directory:
                try:
                    os.chdir(self._pwrec.pw_dir)
                except Exception as ex:
                    pass
        return

    @property
    def note(self):
        return self._note
    @note.setter
    def note(self, value):
        self._note = value

    @property
    def status(self):
        serv = self.service
        proc = self._proc

        rs = ""
        if serv.restart and self._starts_allowed > 0:
            rs = "+r#" + str(self._starts_allowed)

        if self._cond_starting:
            return "starting"

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

        return self.default_status()

    def default_status(self):
        return None

    @property
    def running(self):
        return self._proc and self._proc.returncode is None
        
    @property
    def started(self):
        return self._started

    @asyncio.coroutine
    def start(self):
        """
        Runs this service if it is enabled and has not already been started.  Starts
        prerequisite services first.  A service is considered started if
           a) It is enabled, and started up normally.
           b) It is disabled, and an attempt was made to start it.
           c) An error occurred, it did not start, but failures we an acceptable
              outcome and the service has not been reset since the errors occurred.
        """

        service = self.service

        if self._started:
            debug("service {0} started.  further starts ignored.", service.name)
            return

        if not service.enabled:
            debug("service {0} not enabled, will be skipped", service.name)
            return
        else:
            debug("service {0} enabled, recieved start request", service.name)

        # If this service is already starting, then just wait until it completes.

        cond_starting = self._cond_starting

        if cond_starting:
            yield from cond_starting.acquire()
            yield from cond_starting.wait()
            cond_starting.release()
            return

        cond_starting = self._cond_starting = asyncio.Condition()

        # Now we can procede

        try:

            if self.family:
                if service.prerequisites:
                    prereq = [self.family.get(p) for p in service.prerequisites]
                    for p in prereq:
                        if p:
                            yield from p.start()
                    debug("service {0} prerequisites satisfied", service.name)

                # idle only makes sense for families
                if service.service_group == 'IDLE' and service.idle_delay and not hasattr(self.family, '_idle_hit'):
                    self.family._idle_hit = True
                    debug("IDLE transition hit.  delaying for {0} seconds", service.idle_delay)
                    yield from asyncio.sleep(service.idle_delay)

                # STOP if the system is no longer alive because a prerequisite failed
                if not self.family.controller.system_alive:
                    return

            try:
                yield from self._start_service()
            except Exception as ex:
                if isinstance(ex, FileNotFoundError) and service.optional:
                    info("optional service {0} ignored due to exception: {1}", service.name, ex)
                elif service.ignore_failures:
                    info("service {0} ignoring failures. Exception: {1}", service.name, ex)
                else:
                    raise

        finally:
            self._started = True
            yield from cond_starting.acquire()
            cond_starting.notify_all()
            cond_starting.release()
            self._cond_starting = None
            debug("{0} notified waiters upon completion", service.name)

    @asyncio.coroutine
    def _start_service(self):
        service = self.service

        debug("{0} attempting start '{1}'... ".format(service.name, " ".join(service.exec_args)))

        kwargs = dict()

        if service.stdout == 'log':
            kwargs['stdout'] = asyncio.subprocess.PIPE
        if service.stderr == 'log':
            kwargs['stderr'] = asyncio.subprocess.PIPE
        if service.directory:
            kwargs['cwd'] = service.directory

        env = service.environment
        if env:
            env = env.get_public_environment()

        yield from self.process_prepare_co(env)

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
            self.add_pending(asyncio.async(_process_logger(proc.stdout, 'stdout', self.name)))
        if service.stderr == 'log':
            self.add_pending(asyncio.async(_process_logger(proc.stderr, 'stderr', self.name)))

        if service.exit_kills:
            self.add_pending(asyncio.async(self._wait_kill_on_exit()))

        yield from self.process_started_co()

        self._starts_allowed = self.service.restart_limit

        debug("{0} successfully started", service.name)

    @asyncio.coroutine
    def process_prepare_co(self, environment):
        pass

    @asyncio.coroutine
    def process_started_co(self):
        pass

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
                yield from self.start()
            return

        if service.ignore_failures:
            debug("{0} abnormal process exit ignored due to ignore_failures=true", service.name)
            yield from self.reset()
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
        debug("{0} receieved reset", self.name)

        if self._proc:
            if self._proc.returncode is None:
                self.terminate()
                yield from self.wait()
            self.pid = None
            self._proc = None

        if restart:
            self._starts_allowed -= 1
        else:
            self._starts_allowed = self.service.restart_limit + 1

        self._started = False
        
    @asyncio.coroutine
    def stop(self):
        self._starts_allowed = 0
        yield from self.reset()
        
    @asyncio.coroutine
    def final_stop(self):
        "Called when the whole system is killed, but before drastic measures are taken."
        for p in list(self._pending):
            if not p.cancelled():
                p.cancel()

    def terminate(self):
        proc = self._proc
        if proc:
            if proc.returncode is None:
                if self.kill_signal is not None:
                    debug("using {0} to terminate {1}", get_signal_name(self.kill_signal), self.name)
                    proc.send_signal(self.kill_signal)
                else:
                    proc.terminate()

    @asyncio.coroutine
    def timed_wait(self, timeout, func = None):
        """
        Timed wait waits for process completion.  If process completion occurs normally, the
        resultcode for process startup is returned.

        Upon timeout either:
        1.  asyncio.TimeoutError is raised if 'func' is not provided, or...
        2.  func is called and the result is returned from timed_wait().
        """
        try:
            result =  yield from asyncio.wait_for(asyncio.shield(self.wait()), timeout)
        except asyncio.TimeoutError:
            if not func:
                raise
            result = func()
        return result

    @asyncio.coroutine
    def wait(self):
        proc = self._proc

        if not proc:
            raise Exception("Process not running, can't wait")
        yield from proc.wait()

        if proc.returncode is not None and proc.returncode.normal_exit:
            debug("{2} exit status for pid={0} is '{1}'".format(proc.pid, proc.returncode, self.name))
        else:
            info("{2} exit status for pid={0} is '{1}'".format(proc.pid, proc.returncode, self.name))

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
    def run(self, servicelist = None):
        """
        Runs the family, starting up services in dependency order.  If any problems
        occur, an exception is raised.
        """
        # Note that all tasks are started simultaneously, but they resolve their
        # interdependencies themselves.
        yield from asyncio.gather(*[s.start() for s in servicelist or self.values()])

    def _lookup_services(self, names):
        result = set()
        for name in names:
            serv = self.get(name)
            if not serv:
                serv = self.get(name + ".service")
            if not serv:
                raise Exception("no such service: " + name)
            result.add(serv)
        return result

    @asyncio.coroutine
    def start(self, service_names, ignore_errors = False, wait = False, enable = False):
        slist = self._lookup_services(service_names)

        not_enab = [s for s in slist if not s.enabled]

        if not ignore_errors:
            if not_enab and not enable:
                raise Exception("can only start services which have been enabled: " + ", ".join([s.name for s in not_enab]))
            started = [s for s in slist if s.started]
            if started:
                raise Exception("can't restart services without stop/reset: " + ", ".join([s.name for s in started]))

        if not_enab and enable:
            for s in not_enab:
                s.enable()

        if not wait:
            asyncio.async(self.run(slist))
        else:
            yield from self.run(slist)

    @asyncio.coroutine
    def stop(self, service_names, ignore_errors = False, wait = False):
        slist = self._lookup_services(service_names)
        started = [s for s in slist if s.started]

        if not ignore_errors:
            if len(started) != len(slist):
                raise Exception("can't stop services which aren't started: " + 
                                ", ".join([s.name for s in slist if not s.started]))

        for s in slist:
            if not wait:
                asyncio.async(s.stop())
            else:
                yield from s.stop()

    def get_status_formatter(self):
        df = TableFormatter('pid', 'name', 'enabled', 'status', 'note', sort='name')
        df.add_rows(self.values())
        return df
    
