import os
import asyncio
import shlex
import importlib
import signal
import errno
from functools import partial

from time import time, sleep

import chaperone.cutil.syslog_info as syslog_info

from chaperone.cutil.env import Environment, ENV_SERIAL, ENV_SERVTIME
from chaperone.cutil.logging import warn, info, debug, error
from chaperone.cutil.proc import ProcStatus
from chaperone.cutil.misc import lazydict, lookup_user, get_signal_name, executable_path
from chaperone.cutil.errors import ChNotFoundError, ChProcessError, ChParameterError
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

    service = None              # service object
    family = None
    process_timeout = 30.0      # process_timeout will be set to this unless it is overridden by 
                                # the service entry
    syslog_facility = None      # specifies any additional syslog facility to use when using
                                # logerror, logdebug, logwarn, etc...
    start_attempted = False     # used to determine if a service is truly dormant

    error_count = 0             # counts errors for informational purposes

    _proc = None
    _pid = None                 # the pid, often associated with _proc, but not necessarily in the
                                # case of notify processes
    _returncode = None          # an alternate returncode, set with returncode property
    _exit_event = None          # an event to be fired if an exit occurs, in the case of an
                                # attached PID
    _orig_executable = None     # original unexpanded exec_args[0]

    _pwrec = None               # the pwrec looked up for execution user/group
    _cond_starting = None       # a condition which, if present, indicates that this service is starting
    _cond_exception = None      # exception which was raised during startup (for other waiters)

    _started = False            # true if a start has occurred, either successful or not
    _restarts_allowed = 0       # number of starts permitted before we give up (if None then restarts allowed according to service def)
    _prereq_cache = None
    _procenv = None             # process environment ready to be expanded

    _pending = None             # pending futures
    _note = None

    # Class variables
    _cls_ptdict = lazydict()    # dictionary of process types
    _cls_serial = 0             # serial number for process creation

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
        self._restarts_allowed = 0

        if not service.environment:
            self._procenv = Environment()
        else:
            self._procenv = service.environment

            uid = service.environment.uid
            gid = service.environment.gid

            if uid is not None:
                self._pwrec = lookup_user(uid, gid)

        if not service.exec_args:
            raise ChParameterError("No command or arguments provided for service")

        # If the service is enabled, assure we check for the presence of the executable now.  This is
        # to catch any start-up situations (such as cron jobs without their executables being present).
        # However, we don't check this if a service is disabled.

        self._orig_executable = service.exec_args[0]

        if service.enabled:
            self._try_to_enable()

    def __getattr__(self, name):
        "Proxies value from the service description if we don't override them."
        return getattr(self.service, name)

    def __setattr__(self, name, value):
        """
        Any service object attribute supercedes our own except for privates or those we
        keep separately, in which case there is a distinction.
        """
        if name[0:0] != '_' and hasattr(self.service, name) and not hasattr(self, name):
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

    # pid and returncode management

    @property
    def pid(self):
        return self._pid

    @pid.setter
    def pid(self, newpid):
        if self._pid is not None and newpid is not None and self._pid is not newpid:
            self.logdebug("{0} changing PID to {1} (from {2})", self.name, newpid, self._pid)
            try:
                pgid = os.getpgid(newpid)
            except ProcessLookupError as ex:
                raise ChProcessError("{0} attempted to attach the process with PID={1} but there is no such process".
                                     format(self.name, newpid), errno = ex.errno)
            self._attach_pid(newpid)
        self._pid = newpid

    @property
    def returncode(self):
        if self._returncode is not None:
            return self._returncode
        return self._proc and self._proc.returncode

    @returncode.setter
    def returncode(self, val):
        self._returncode = ProcStatus(val)
        self.logdebug("{0} got explicit return code '{1}'", self.name, self._returncode)

    # Logging methods which may do special things for this service

    def loginfo(self, *args, **kwargs):
        info(*args, facility=self.syslog_facility, **kwargs)

    def logerror(self, *args, **kwargs):
        self.error_count += 1
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
        if serv.restart and self._restarts_allowed is not None and self._restarts_allowed > 0:
            rs = "+r#" + str(self._restarts_allowed)

        if self._cond_starting:
            return "starting"

        if proc:
            rc = self._returncode if self._returncode is not None else proc.returncode
            if rc is None:
                return "running"
            elif rc.normal_exit and self._started:
                return "started"
            elif rc:
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
        if val and not self.service.enabled:
            self._try_to_enable()
        else:
            self.service.enabled = False

    def _try_to_enable(self):
        service = self.service
        if self._orig_executable:
            try:
                service.exec_args[0] = executable_path(self._orig_executable, service.environment.expanded())
            except FileNotFoundError:
                if service.optional:
                    service.enabled = False
                    self.loginfo("optional service {0} disabled since '{1}' is not present".format(self.name, self._orig_executable))
                    return
                raise ChNotFoundError("executable '{0}' not found".format(service.exec_args[0]))
        service.enabled = True

    @property
    def scheduled(self):
        """
        True if this is a process which WILL fire up a process in the future.
        A "scheduled" process does not include one which will be started manually,
        nor does it include proceses which will be started due to dependencies.
        Processes like "cron" and "inetd" return True if they are active and 
        may start processes in the future.
        """
        return False

    @property
    def kill_signal(self):
        ksig = self.service.kill_signal
        if ksig is not None:
            return ksig
        return signal.SIGTERM

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
    def stoppable(self):
        """
        True if this process can be stopped.  By default, returns True if the service is started,
        but some job types such as cron and inetd may be stoppable even when processes themselves
        are not running.
        """
        return self.started

    @property
    def failed(self):
        "True if this process has failed, either during startup or later."
        return ((self._returncode is not None and not self._returncode.normal_exit) or 
                self._proc and (self._proc.returncode is not None and not self._proc.returncode.normal_exit))

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
            # This is an odd situation.  Since every waiter expects start() to succeed, or
            # raise an exception, we need to be sure we raise the exception that happened
            # in the original start() request.
            if self._cond_exception:
                raise self._cond_exception
            return

        cond_starting = self._cond_starting = asyncio.Condition()
        self._cond_exception = None

        # Now we can procede

        self.start_attempted = True

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
                if not self.family.system_alive:
                    return

            try:
                yield from self.start_subprocess()
            except Exception as ex:
                if service.ignore_failures:
                    self.loginfo("service {0} ignoring failures. Exception: {1}", service.name, ex)
                else:
                    self._cond_exception = ex
                    self.logdebug("{0} received exception during attempted start. Exception: {1}", service.name, ex)
                    raise

        finally:
            self._started = True

            yield from cond_starting.acquire()
            cond_starting.notify_all()
            cond_starting.release()
            self._cond_starting = None
            self.logdebug("{0} notified waiters upon completion", service.name)

    def get_expanded_environment(self):
        SubProcess._cls_serial += 1
        penv = self._procenv
        penv[ENV_SERIAL] = str(SubProcess._cls_serial)
        penv[ENV_SERVTIME] = str(int(time()))
        return penv.expanded()

    @asyncio.coroutine
    def start_subprocess(self):
        service = self.service

        self.logdebug("{0} attempting start '{1}'... ".format(service.name, " ".join(service.exec_args)))

        kwargs = dict()

        if service.stdout == 'log':
            kwargs['stdout'] = asyncio.subprocess.PIPE
        if service.stderr == 'log':
            kwargs['stderr'] = asyncio.subprocess.PIPE
        if service.directory:
            kwargs['cwd'] = service.directory

        env = self.get_expanded_environment()

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
            self.logwarn("system will be killed when '{0}' exits", service.exec_args[0])
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

        self._restarts_allowed = None # allow restarts if we fail

        self.logdebug("{0} successfully started", service.name)

    @asyncio.coroutine
    def process_prepare_co(self, environment):
        pass

    @asyncio.coroutine
    def process_started_co(self):
        pass

    @asyncio.coroutine
    def wait_for_pidfile(self):
        """
        If the pidfile option was specified, then wait until we find a valid pidfile,
        and register the new PID.  This is not done automatically, but is implemented
        here as a utility for process types that need it.
        """
        if not self.pidfile:
            return

        self.logdebug("{0} waiting for PID file: {1}".format(self.name, self.pidfile))

        pidsleep = 0.02         # work incrementally up to no more than process_timeout
        minsleep = 3
        expires = time() + self.process_timeout

        while time() < expires:
            if not self.family.system_alive:
                return
            yield from asyncio.sleep(pidsleep)
            # ramp up until we hit the minsleep ceiling
            pidsleep = min(pidsleep*2, minsleep)
            try:
                newpid = int(open(self.pidfile, 'r').read().strip())
            except FileNotFoundError:
                continue
            except Exception as ex:
                raise ChProcessErrorr("{0} found pid file '{1}' but contents did not contain an integer".format(
                                      self.name, self.pidfile), errno = errno.EINVAL)
            self.pid = newpid
            return

        raise ChProcessError("{0} did not find pid file '{1}' before {2}sec process_timeout expired".format(
                             self.name, self.pidfile, self.process_timeout), errno = error.ENOENT)
        
    @asyncio.coroutine
    def _wait_kill_on_exit(self):
        yield from self.wait()
        self._kill_system()

    def _attach_pid(self, newpid):
        """
        Attach this process to a new PID, creating a condition which will be used by 
        the child watcher to determine when the PID has exited.
        """
        with asyncio.get_child_watcher() as watcher:
            watcher.add_child_handler(newpid, self._child_watcher_callback)

        self._exit_event = asyncio.Event()
        
    def _child_watcher_callback(self, pid, returncode):
        asyncio.get_event_loop().call_soon_threadsafe(self.process_exit, returncode)

    def process_exit(self, code):
        self.returncode = code

        if self._exit_event:
            self._exit_event.set()
            self._exit_event = None

        if code.normal_exit or self.kill_signal == code.signal:
            return

        asyncio.async(self._abnormal_exit(code))
    
    @asyncio.coroutine
    def _abnormal_exit(self, code):
        service = self.service

        if service.exit_kills:
            self.logwarn("{0} terminated abnormally with {1}", service.name, code)
            return

        # A disabled service should not do recovery

        if not service.enabled:
            return

        if self._started and service.restart:
            if self._restarts_allowed is None:
                self._restarts_allowed = service.restart_limit
            if self._restarts_allowed > 0:
                self._restarts_allowed -= 1
                controller = self.family.controller
                if controller.system_alive:
                    if service.restart_delay:
                        self.loginfo("{0} pausing between restart retries", service.name)
                        yield from asyncio.sleep(service.restart_delay)
                if controller.system_alive:
                    yield from self.reset()
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
        if not ex:
            self._restarts_allowed = None
        else:
            self.logwarn("{0} restart failed: {1}", self.name, ex)
            asyncio.async(self._abnormal_exit(self._proc and self._proc.returncode))

    def _kill_system(self):
        self.family.controller.kill_system()

    def add_pending(self, future):
        self._pending.add(future)
        future.add_done_callback(lambda f: self._pending.discard(future))

    @asyncio.coroutine
    def reset(self, dependents = False, enable = False):
        self.logdebug("{0} received reset", self.name)

        if self._exit_event:
            self.terminate()
        elif self._proc:
            if self._proc.returncode is None:
                self.terminate()
                yield from self.wait()
            self.pid = None
            self._proc = None

        self._started = False
        
        if enable:
            self.service.enabled = True

        # If there is a pidfile, then remove it

        if self.pidfile:
            try:
                os.remove(self.pidfile)
            except Exception:
                pass

        # Reset any non-ready dependents

        if dependents:
            for p in self.prerequisites:
                if not p.ready and (enable or p.enabled):
                    yield from p.reset(dependents, enable)
                
    @asyncio.coroutine
    def stop(self):
        self._restarts_allowed = 0
        yield from self.reset()
        
    @asyncio.coroutine
    def final_stop(self):
        "Called when the whole system is killed, but before drastic measures are taken."
        self._exit_event = None
        self.terminate()
        for p in list(self._pending):
            if not p.cancelled():
                p.cancel()

    def terminate(self):
        proc = self._proc
        otherpid = self.pid

        if proc:
            if otherpid == proc.pid:
                otherpid = None
            if proc.returncode is None:
                if self.service.kill_signal is not None: # explicitly check service
                    self.logdebug("using {0} to terminate {1}", get_signal_name(self.kill_signal), self.name)
                    proc.send_signal(self.kill_signal)
                else:
                    proc.terminate()

        if otherpid:
            self.logdebug("using {0} to terminate {1}", get_signal_name(self.kill_signal), self.name)
            try:
                os.kill(otherpid, self.kill_signal)
            except Exception as ex:
                warn("{0} could not be killed using PID={1}: ".format(ex, otherpid))

        self._pid = None
        
    @asyncio.coroutine
    def do_startup_pause(self):
        """
        Wait a short time just to see if the process errors out immediately.  This avoids a retry loop
        and catches any immediate failures now.  Can be used by process implementations if needed.
        """

        if not self.startup_pause:
            return

        try:
            result = yield from self.timed_wait(self.startup_pause)
        except asyncio.TimeoutError:
            result = None
        if result is not None and not result.normal_exit:
            if self.ignore_failures:
                warn("{0} (ignored) failure on start-up with result '{1}'".format(self.name, result))
            else:
                raise ChProcessError("{0} failed on start-up with result '{1}'".format(self.name, result),
                                     resultcode = result)

    @asyncio.coroutine
    def timed_wait(self, timeout, func = None):
        """
        Timed wait waits for process completion.  If process completion occurs normally, the
        returncode for process startup is returned.

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
        except asyncio.CancelledError:
            result = self.returncode

        return result

    @asyncio.coroutine
    def wait(self):
        proc = self._proc

        if self._exit_event:
            yield from self._exit_event.wait()
        elif proc:
            yield from proc.wait()
        else:
            raise Exception("Process not running (or attached), can't wait")

        if proc.returncode is not None and proc.returncode.normal_exit:
            self.logdebug("{2} exit status for pid={0} is '{1}'".format(proc.pid, proc.returncode, self.name))
        else:
            self.loginfo("{2} exit status for pid={0} is '{1}'".format(proc.pid, proc.returncode, self.name))

        return proc.returncode


class SubProcessFamily(lazydict):

    controller = None           # top level system controller
    services_config = None

    _start_time = None

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
    
    @property
    def system_alive(self):
        return self.controller.system_alive

    def get_scheduled_services(self):
        return [s for s in self.values() if s.scheduled]

    def get_status(self):
        if not self._start_time:
            return "Not yet started"

        secs = time() - self._start_time

        total = len(self.values())
        scheduled = started = failed = errors = 0

        for s in self.values():
            if s.scheduled:
                scheduled += 1
            if s.started:
                started += 1
            if s.failed:
                failed += 1
            errors += s.error_count

        m,s = divmod(int(secs), 60)
        h,m = divmod(m, 60)

        msg = "Uptime {0:02}:{1:02}:{2:02}; {3} service{4} started".format(h, m, s, started or "No", started != 1 and 's' or '')
        if scheduled:
            msg += "; {0} scheduled".format(scheduled)
        if failed:
            msg += "; {0} failed".format(failed)
        if errors:
            msg += "; {0} total errors".format(errors)

        return msg

    @asyncio.coroutine
    def run(self, servicelist = None):
        """
        Runs the family, starting up services in dependency order.  If any problems
        occur, an exception is raised.  Returns True if any attempts were made to
        start services, otherwize False if the configuration contained no services
        that were enabled and ready to run.
        """
        # Note that all tasks are started simultaneously, but they resolve their
        # interdependencies themselves.
        if not servicelist:
            servicelist = self.values()
        yield from asyncio.gather(*[s.start() for s in servicelist])

        self._start_time = time()

        # Indicate if any attempts were made
        return any(s.start_attempted for s in servicelist)

    def _lookup_services(self, names):
        result = set()
        for name in names:
            serv = self.get(name)
            if not serv:
                serv = self.get(name + ".service")
            if not serv:
                raise ChParameterError("no such service: " + name)
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
        started = [s for s in slist if s.stoppable]

        if not force:
            if len(started) != len(slist):
                raise Exception("can't stop services which aren't started: " + 
                                ", ".join([s.shortname for s in slist if not s.stoppable]))

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
