import os
import asyncio
import shlex
import importlib
from functools import partial

from time import time, sleep

import chaperone.cutil.syslog_info as syslog_info

from chaperone.cutil.env import Environment
from chaperone.cutil.logging import warn, info, debug, error
from chaperone.cutil.misc import lazydict, lookup_user, get_signal_name, executable_path
from chaperone.cutil.errors import ChNotFoundError
from chaperone.cutil.format import TableFormatter

@asyncio.coroutine
def _process_logger(stream, kind, service):
    name = service.name.replace('.service', '')
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
            warn(line, program=name, pid=service.pid, facility=syslog_info.LOG_DAEMON)
        else:
            info(line, program=name, pid=service.pid, facility=syslog_info.LOG_DAEMON)


class SubProcess(object):

    pid = None
    service = None              # service object
    family = None
    process_timeout = 30.0      # process_timeout will be set to this unless it is overridden by 
                                # the service entry
    syslog_facility = None      # specifies any additional syslog facility to use when using
                                # logerror, logdebug, logwarn, etc...

    _proc = None
    _pwrec = None               # the pwrec looked up for execution user/group
    _cond_starting = None       # a condition which, if present, indicates that this service is starting
    _started = False            # true if a start has occurred, either successful or not
    _starts_allowed = 0         # number of starts permitted before we give up
    _prereq_cache = None
    _xenv = None                # expanded environment

    _pending = None             # pending futures
    _note = None

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

        if service.environment:
            # The environment has already been modified to reflect our chosen service uid/gid
            self._xenv = service.environment.expanded()

            uid = service.environment.uid
            gid = service.environment.gid

            if uid is not None:
                self._pwrec = lookup_user(uid, gid)

        if not service.exec_args:
            raise Exception("No command or arguments provided for service")

        # We translate the executable into a valid path now so we can handle optional
        # services

        try:
            service.exec_args[0] = executable_path(service.exec_args[0], self._xenv)
        except FileNotFoundError:
            if service.optional:
                service.enabled = False
                self.loginfo("optional service {0} disabled since '{1}' is not present".format(self.name, service.exec_args[0]))
                return
            raise ChNotFoundError("executable '{0}' not found".format(service.exec_args[0]))

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

    def _get_states(self):
        states = list()
        if self.started:
            states.append('started')
        if self.failed:
            states.append('failed')
        if self.ready:
            states.append('ready')
        if self.running:
            states.append('running')
        return ' '.join(states)

    # Logging methods which may do special things for this service

    def loginfo(self, *args, **kwargs):
        info(*args, facility=self.syslog_facility, **kwargs)

    def logerror(self, *args, **kwargs):
        error(*args, facility=self.syslog_facility, **kwargs)

    def logwarn(self, *args, **kwargs):
        warn(*args, facility=self.syslog_facility, **kwargs)

    def logdebug(self, *args, **kwargs):
        debug(*args, facility=self.syslog_facility, **kwargs)

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
            if rc is None:
                return "running"
            elif rc.normal_exit:
                return "started"
            else:
                return rc.briefly + rs
                    
        if not serv.enabled:
            return "disabled"

        return self.default_status()

    def default_status(self):
        if self.ready:
            return 'ready'
        return None

    @property
    def enabled(self):
        return self.service.enabled
    @enabled.setter
    def enabled(self, val):
        self.service.enabled = bool(val)

    @property
    def running(self):
        "True if this process has started, is running, and has a pid"
        return self._proc and self._proc.returncode is None
        
    @property
    def started(self):
        """
        True if this process has started normally. It may have forked, or executed, or is scheduled.
        """
        return self._started

    @property
    def failed(self):
        "True if this process has failed, either during startup or later."
        return self._started and self._proc and self._proc.returncode is not None and not self._proc.returncode.normal_exit

    @property
    def ready(self):
        """
        True if this process is ready to run, or running.  If not running, To be ready to run, all 
        prerequisites must also be ready.
        """
        if not self.enabled or self.failed:
            return False
        if self.started:
            return True
        if any(p.enabled and not p.ready for p in self.prerequisites):
            return False
        return True

    @property
    def prerequisites(self):
        """
        Return a list of prerequisite objects.  Right now, these must be within our family
        but this may change, so don't refer to the family or the prereq in services.  Use this
        instead.
        """
        if self._prereq_cache is None:
            prereq = (self.family and self.service.prerequisites) or ()
            prereq = self._prereq_cache = tuple(self.family[p] for p in prereq if p in self.family)
        return self._prereq_cache

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
            self.logdebug("service {0} already started.  further starts ignored.", service.name)
            return

        if not service.enabled:
            self.logdebug("service {0} not enabled, will be skipped", service.name)
            return
        else:
            self.logdebug("service {0} enabled, queueing start request", service.name)

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
            prereq = self.prerequisites
            if prereq:
                for p in prereq:
                    yield from p.start()
                self.logdebug("service {0} prerequisites satisfied", service.name)

            if self.family:
                # idle only makes sense for families
                if "IDLE" in service.service_groups and service.idle_delay and not hasattr(self.family, '_idle_hit'):
                    self.family._idle_hit = True
                    self.logdebug("IDLE transition hit.  delaying for {0} seconds", service.idle_delay)
                    yield from asyncio.sleep(service.idle_delay)

                # STOP if the system is no longer alive because a prerequisite failed
                if not self.family.controller.system_alive:
                    return

            try:
                yield from self._start_service()
            except Exception as ex:
                if service.ignore_failures:
                    self.loginfo("service {0} ignoring failures. Exception: {1}", service.name, ex)
                else:
                    raise

        finally:
            self._started = True
            yield from cond_starting.acquire()
            cond_starting.notify_all()
            cond_starting.release()
            self._cond_starting = None
            self.logdebug("{0} notified waiters upon completion", service.name)

    @asyncio.coroutine
    def _start_service(self):
        service = self.service

        self.logdebug("{0} attempting start '{1}'... ".format(service.name, " ".join(service.exec_args)))

        kwargs = dict()

        if service.stdout == 'log':
            kwargs['stdout'] = asyncio.subprocess.PIPE
        if service.stderr == 'log':
            kwargs['stderr'] = asyncio.subprocess.PIPE
        if service.directory:
            kwargs['cwd'] = service.directory

        env = self._xenv or Environment(None)

        yield from self.process_prepare_co(env)

        if env:
            env = env.get_public_environment()

        if service.debug:
            if not env:
                self.logdebug("{0} environment is empty", service.name)
            else:
                self.logdebug("{0} environment:", service.name)
                for k,v in env.items():
                    self.logdebug(" {0} = '{1}'".format(k,v))


        create = asyncio.create_subprocess_exec(*service.exec_args, preexec_fn=self._setup_subprocess,
                                                env=env, **kwargs)
        if service.exit_kills:
            self.logwarn("system wll be killed when '{0}' exits", service.exec_args[0])
            yield from asyncio.sleep(0.2)

        proc = self._proc = yield from create

        self.pid = proc.pid

        if service.stdout == 'log':
            self.add_pending(asyncio.async(_process_logger(proc.stdout, 'stdout', self)))
        if service.stderr == 'log':
            self.add_pending(asyncio.async(_process_logger(proc.stderr, 'stderr', self)))

        if service.exit_kills:
            self.add_pending(asyncio.async(self._wait_kill_on_exit()))

        yield from self.process_started_co()

        self._starts_allowed = self.service.restart_limit

        self.logdebug("{0} successfully started", service.name)

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
            self.logwarn("{0} terminated abnormally with {1}", service.name, code)
            return

        # A disabled service should not do recovery

        if not service.enabled:
            return

        if service.restart and self._starts_allowed > 0:
            controller = self.family.controller
            if controller.system_alive:
                if service.restart_delay:
                    self.loginfo("{0} pausing between restart retries", service.name)
                    yield from asyncio.sleep(service.restart_delay)
            if controller.system_alive:
                yield from self.reset(True)
                #yield from self.start()
                f = asyncio.async(self.start()) # queue it since we will just return here
                f.add_done_callback(self._restart_callback)
            return

        if service.ignore_failures:
            self.logdebug("{0} abnormal process exit ignored due to ignore_failures=true", service.name)
            yield from self.reset()
            return

        self.logerror("{0} terminated abnormally with {1}", service.name, code)

    def _restart_callback(self, fut):
        # Catches a restart result, reporting it as a warning, and either passing back to _abnormal_exit
        # or accepting glorious success.
        ex = fut.exception()
        if ex:
            self.logwarn("{0} restart failed: {1}", self.name, ex)
            asyncio.async(self._abnormal_exit(self._proc and self._proc.returncode))

    def _kill_system(self):
        self.family.controller.kill_system()

    def add_pending(self, future):
        self._pending.add(future)
        future.add_done_callback(lambda f: self._pending.discard(future))

    @asyncio.coroutine
    def reset(self, restart = False, dependents = False, enable = False):
        self.logdebug("{0} received reset", self.name)

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
        
        if enable:
            self.service.enabled = True

        # Reset any non-ready dependents

        if dependents:
            for p in self.prerequisites:
                if not p.ready and (enable or p.enabled):
                    yield from p.reset(restart, dependents, enable)
                
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
                    self.logdebug("using {0} to terminate {1}", get_signal_name(self.kill_signal), self.name)
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
            if not timeout:
                raise asyncio.TimeoutError() # funny situation, but settings can cause this if users attempt it
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
            self.logdebug("{2} exit status for pid={0} is '{1}'".format(proc.pid, proc.returncode, self.name))
        else:
            self.loginfo("{2} exit status for pid={0} is '{1}'".format(proc.pid, proc.returncode, self.name))

        return proc.returncode


class SubProcessFamily(lazydict):

    controller = None           # top level system controller
    services_config = None

    def __init__(self, controller, services_config):
        """
        Given a pre-analyzed list of processes, complete with prerequisites, build a process
        family.
        """
        super().__init__()

        self.controller = controller
        self.services_config = services_config

        for s in services_config.get_startup_list():
            self[s.name] = SubProcess(s, family = self)

    def get_status_formatter(self):
        df = TableFormatter('pid', 'name', 'enabled', 'status', 'note', sort='name')
        df.add_rows(self.values())
        return df
    
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
    def start(self, service_names, force = False, wait = False, enable = False):
        slist = self._lookup_services(service_names)

        not_enab = [s for s in slist if not s.enabled]

        if not force:
            if not_enab and not enable:
                raise Exception("can only start services which have been enabled: " + ", ".join([s.shortname for s in not_enab]))
            started = [s for s in slist if s.started]
            if started:
                raise Exception("can't restart services without stop/reset: " + ", ".join([s.shortname for s in started]))
            notready = [s for s in slist if not s.ready and (s.enabled and not enable)]
            if notready:
                raise Exception("services or their prerequisites are not ready: " + ", ".join([s.shortname for s in notready]))

        resets = ()

        if not_enab and enable:
            resets = not_enab

        # If forcing, then reset all services, as well as any non-ready dependents.

        if force:
            resets = [s for s in slist if (not s.ready or s.started)]

        for s in resets:
            yield from s.reset(dependents=True, enable=enable)

        if not wait:
            asyncio.async(self._queued_start(slist, service_names))
        else:
            yield from self.run(slist)

    @asyncio.coroutine
    def _queued_start(self, slist, names):
        try:
            yield from self.run(slist)
        except Exception as ex:
            error("queued start (for {0}) failed: {1}", names, ex)
            
    @asyncio.coroutine
    def stop(self, service_names, force = False, wait = False, disable = False):
        slist = self._lookup_services(service_names)
        started = [s for s in slist if s.started]

        if not force:
            if len(started) != len(slist):
                raise Exception("can't stop services which aren't started: " + 
                                ", ".join([s.shortname for s in slist if not s.started]))

        if not wait:
            asyncio.async(self._queued_stop(slist, service_names, disable))
        else:
            for s in slist:
                yield from s.stop()
                if disable:
                    s.enabled = False

    @asyncio.coroutine
    def _queued_stop(self, slist, names, disable):
        try:
            for s in slist:
                yield from s.stop()
                if disable:
                    s.enabled = False
        except Exception as ex:
            error("queued stop (for {0}) failed: {1}", names, ex)

    @asyncio.coroutine
    def reset(self, service_names, force = False, wait = False):
        slist = self._lookup_services(service_names)

        if not force:
            running = [s for s in slist if s.running]
            if running:
                raise Exception("can't reset services which are running: " + ", ".join([s.shortname for s in running]))

        if not wait:
            asyncio.async(self._queued_reset(slist, service_names))
        else:
            for s in slist:
                yield from s.reset()

    @asyncio.coroutine
    def _queued_reset(self, slist, names):
        try:
            for s in slist:
                yield from s.reset()
        except Exception as ex:
            error("queued reset (for {0}) failed: {1}", names, ex)

    @asyncio.coroutine
    def enable(self, service_names):
        slist = self._lookup_services(service_names)
        for s in slist:
            s.enabled = True

    @asyncio.coroutine
    def disable(self, service_names):
        slist = self._lookup_services(service_names)
        for s in slist:
            s.enabled = False
