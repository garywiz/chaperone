import os
import asyncio
import shlex

from time import time, sleep

import chaperone.cutil.syslog_info as syslog_info

from chaperone.cutil.logging import warn, info, debug, error
from chaperone.cutil.misc import lazydict, Environment, lookup_user


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
    _maybe_run_tried = False    # True if we've already been started

    @classmethod
    @asyncio.coroutine
    def spawn(cls, service, args=None, wait=False):
        sp = cls(service, args)
        yield from sp.maybe_run()
        if wait:
            yield from sp.wait()

    def __init__(self, service, args=None, family=None):

        self.service = service
        self.family = family

        #print("SERVICE USER", service.user)

        # The environment has already been modified to reflect our chosen service uid/gid
        uid = service.environment.uid
        gid = service.environment.gid

        if uid is not None:
            self._pwrec = lookup_user(uid, gid)

        if args is None:
          if service.command:
              assert not (service.command and (service.bin or service.args)), "bin/args and command config are mutually-exclusive"
              args = shlex.split(service.command)
          elif service.bin:
              args = [service.bin] + shlex.split(service.args or '')
          else:
              raise Exception("No command or arguments provided for service")

        self._prog_args = args

    def _setup_subprocess(self):
        if self._pwrec:
            os.setgid(self._pwrec.pw_gid)
            os.setuid(self._pwrec.pw_uid)
            try:
                os.chdir(self._pwrec.pw_dir)
            except Exception as ex:
                pass

    @asyncio.coroutine
    def maybe_run(self):
        """
        Runs this service if it is enabled and has not already been started.
        """

        if self._maybe_run_tried:
            return True
        self._maybe_run_tried = True

        service = self.service

        if not service.enabled:
            debug("service {0} not enabled, will be skipped", service.name)
            return

        if self.family and service.prerequisites:
            prereq = [self.family.get(p) for p in service.prerequisites]
            for p in prereq:
                if p:
                    yield from p.maybe_run()

        try:
            yield from self._start_service()
        except Exception as ex:
            if isinstance(ex, FileNotFoundError) and service.optional:
                warn("optional service {0} ignored due to exception: {1}", service.name, ex)
            elif service.ignore_failures:
                warn("service {0} ignoring failures.  Not started due to exception: {1}", service.name, ex)
            else:
                raise

    @asyncio.coroutine
    def _start_service(self):
        args = self._prog_args
        assert args, "No arguments provided to SubProcess._start_service()"

        service = self.service

        debug("{0} attempting start '{1}'... ".format(service.name, " ".join(args)))

        kwargs = dict()

        if service.stdout == 'log':
            kwargs['stdout'] = asyncio.subprocess.PIPE
        if service.stderr == 'log':
            kwargs['stderr'] = asyncio.subprocess.PIPE

        env = service.environment
        if env:
            env = env.get_public_environment()

        #print("ENV", env)

        if service.debug:
            if not env:
                debug("{0} environment is empty", service.name)
            else:
                debug("{0} environment:", service.name)
                for k,v in env.items():
                    debug(" {0} = '{1}'".format(k,v))

        create = asyncio.create_subprocess_exec(*self._prog_args, preexec_fn=self._setup_subprocess,
                                                env=env, **kwargs)
        proc = self._proc = yield from create

        if service.stdout == 'log':
            asyncio.async(_process_logger(proc.stdout, 'stdout'))
        if service.stderr == 'log':
            asyncio.async(_process_logger(proc.stderr, 'stderr'))

        print("SERVICE STARTED", self.service.name)

        if service.type == 'oneshot' or service.type == 'forking':
            ret = yield from self.timed_wait(service.process_timeout, self._exit_timeout)
            print("RET FROM TIMED_WAIT", ret)

        print("EXITING SERVICE", self.service.name)

    def _exit_timeout(self):
        service = self.service
        if service.type == 'oneshot':
            message = "{0} service '{1}' did not exit after {2} second(s), {3}".format(
                service.type,
                service.name, service.process_timeout, 
                "proceeding due to 'ignore_failures=True'" if service.ignore_failures else
                "terminating due to 'ignore_failures=False'")
            if not service.ignore_failures:
                self._proc.terminate()
            raise Exception(message)

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
            raise Exception("Process not started, can't wait")
        yield from proc.wait()
        info("Process exit status for pid={0} is '{1}'".format(proc.pid, proc.returncode))


class SubProcessFamily(lazydict):

    def __init__(self, startup_list):
        """
        Given a pre-analyzed list of processes, complete with prerequisites, build a process
        family.
        """
        super().__init__()

        for s in startup_list:
            self[s.name] = SubProcess(s, family = self)

    @asyncio.coroutine
    def run(self):
        """
        Runs the family, starting up services in dependency order.  If any problems
        occur, an exception is raised.
        """

        for s in self.values():
            yield from s.maybe_run()
