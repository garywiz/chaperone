import os
import asyncio
from copy import copy
from chaperone.cutil.logging import error, warn, debug, info
from chaperone.cproc.subproc import SubProcess
from chaperone.cutil.syslog_info import LOG_DAEMON
from chaperone.cutil.errors import ChParameterError
from chaperone.cutil.servers import Server, ServerProtocol

class InetdServiceProtocol(ServerProtocol):

    _fd = None

    def acquire_socket(self, sock):
        # Prepare the socket so it's inheritable
        sock.setblocking(True)
        self._fd = sock.detach()
        sock.close()

        future = asyncio.async(self.start_socket_process(self._fd))
        future.add_done_callback(self._done)

        self.process.counter += 1

        return True

    def _done(self, f):
        # Close the socket regardless
        if self._fd is not None:
            os.close(self._fd)

    @asyncio.coroutine
    def start_socket_process(self, fd):
        process = self.process
        service = process.service

        if not process.family.system_alive:
            process.logdebug("{0} received connection on port {1}; ignored, system no longer alive".format(service.name, service.port))
            return

        process.logdebug("{0} received connection on port {2}; attempting start '{1}'... ".format(service.name, " ".join(service.exec_args),
                         service.port))

        kwargs = {'stdout': fd,
                  'stderr': fd,
                  'stdin': fd}

        if service.directory:
            kwargs['cwd'] = service.directory

        env = process.get_expanded_environment().get_public_environment()

        if service.debug:
            if not env:
                process.logdebug("{0} environment is empty", service.name)
            else:
                process.logdebug("{0} environment:", service.name)
                for k,v in env.items():
                    process.logdebug(" {0} = '{1}'".format(k,v))

        create = asyncio.create_subprocess_exec(*service.exec_args, preexec_fn=process._setup_subprocess,
                                                env=env, **kwargs)

        proc = self._proc = yield from create
        self.pid = proc.pid

        process.logdebug("{0} instance connected to port {1}", service.name, service.port)

        process.add_process(proc)
        yield from proc.wait()
        process.remove_process(proc)

        if not proc.returncode.normal_exit:
            self.logerror("{2} exit status for pid={0} is '{1}'".format(proc.pid, proc.returncode, service.name))


class InetdService(Server):
    
    def __init__(self, process):
        super().__init__()
        self.process = process

    def _create_server(self):
        return asyncio.get_event_loop().create_server(InetdServiceProtocol.buildProtocol(self, process=self.process),
                                                      '0.0.0.0',
                                                      self.process.port)

class InetdProcess(SubProcess):

    syslog_facility = LOG_DAEMON
    server = None
    counter = 0

    def __init__(self, service, family=None):
        super().__init__(service, family)
        self._proclist = set()

        if not service.port:
            raise ChParameterError("inetd-type service {0} requires 'port=' parameter".format(self.name))

    def add_process(self, proc):
        self._proclist.add(proc)

    def remove_process(self, proc):
        self._proclist.discard(proc)

    @property
    def scheduled(self):
        return self.server is not None

    @property
    def note(self):
        if self.server:
            msg = "waiting on port " + str(self.port)
            if self.counter:
                msg += "; req recvd = " + str(self.counter)
            if len(self._proclist):
                msg += "; running = " + str(len(self._proclist))
            return msg

    @asyncio.coroutine
    def start_subprocess(self):
        """
        Takes over process startup and sets up our own server socket.
        """
        
        self.server = InetdService(self)
        yield from self.server.run()

        self.loginfo("inetd service {0} listening on port {1}".format(self.name, self.port))

    @asyncio.coroutine
    def reset(self, dependents = False, enable = False):
        if self.server:
            self.server.close()
            self.server = None
        plist = copy(self._proclist)
        if plist:
            self.logwarn("{0} terminating {1} processes on port {2} that are still running".format(self.name, len(plist), self.port))
            for p in plist:
                p.terminate()
        yield from super().reset(dependents, enable)

    @asyncio.coroutine
    def final_stop(self):
        yield from self.reset()
