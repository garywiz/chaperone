import sys
import os
import socket
import asyncio

from time import time, localtime, strftime

from chaperone.cutil.misc import lazydict, open_foruser
from chaperone.cutil.syslog_info import get_syslog_info

_our_hostname = socket.gethostname()

class LogOutput:
    name = None
    config_match = lambda c: False

    _cls_handlers = lazydict()
    _cls_reghandlers = list()

    @classmethod
    def register(cls, handlercls):
        cls._cls_reghandlers.append(handlercls)

    @classmethod
    def getOutputHandlers(cls, config):
        return list(filter(None, [h.getHandler(config) for h in cls._cls_reghandlers]))

    @classmethod
    def getName(cls, config):
        return cls.name

    @classmethod
    def matchesConfig(cls, config):
        return config.enabled and cls.config_match(config)

    @classmethod
    def getHandler(cls, config):
        if not cls.matchesConfig(config):
            return None
        name = cls.getName(config)
        if name is None:
            return None
        return cls._cls_handlers.setdefault(name, lambda: cls(config))

    def __init__(self, config):
        self.name = config.name
        self.config = config

    def close(self):
        pass

    def writeLog(self, logattrs, priority, facility):
        if logattrs.get('format_error'):
            msg = "??" + logattrs['raw']
        else:
            # Note that 'rest' always starts with a ':', '[' or ' '.
            msg = (logattrs['date'] + ' ' + 
                   (self.config.logrec_hostname or logattrs['host'] or _our_hostname) + ' ' + 
                   logattrs['tag'] + logattrs['rest'])
        if self.config.extended:
            msg = get_syslog_info(facility, priority) + " " + msg
        self.write(msg)

    def write(self, data):
        h = self.handle
        h.write(data)
        h.write("\n")
        h.flush()
                         

class StdoutHandler(LogOutput):

    name = "sys:stdout"
    handle = sys.stdout
    config_match = lambda c: c.stdout

LogOutput.register(StdoutHandler)


class StderrHandler(LogOutput):

    name = "sys:stderr"
    handle = sys.stderr
    config_match = lambda c: c.stderr

LogOutput.register(StderrHandler)


class RemoteClientProtocol:
    def __init__(self, loop):
        self.loop = loop
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def send(self, message):
        self.transport.sendto(message.encode())

    def datagram_received(self, data, addr):
        pass

    def error_received(self, exc):
        pass

    def connection_lost(self, exc):
        self.transport = None

    def close(self):
        if self.transport:
            self.transport.close()


class RemoteHandler(LogOutput):

    config_match = lambda c: c.syslog_host is not None

    _pending = None             # a pending future to setup this handler
    _protocol = None            # protocol for this logger

    @classmethod
    def getName(cls, config):
        return "syslog_host:" + config.syslog_host

    @asyncio.coroutine
    def setup_handler(self):
        loop = asyncio.get_event_loop()
        connect = loop.create_datagram_endpoint(lambda: RemoteClientProtocol(loop),
                                                remote_addr=(self.config.syslog_host, 514))
        (transport, protocol) = yield from connect
        self._pending = None
        self._protocol = protocol

    def __init__(self, config):
        super().__init__(config)
        self._pending = asyncio.async(self.setup_handler())

    def write(self, data):
        if self._protocol:
            self._protocol.send(data)

    def close(self):
        if self._pending:
            if not self._pending.cancelled():
                self._pending.cancel()
            self._pending = None
        if self._protocol:
            self._protocol.close()
            self._protocol = None

LogOutput.register(RemoteHandler)


class FileHandler(LogOutput):

    config_match = lambda c: c.file is not None

    CHECK_INTERVAL = 60

    _orig_filename = None
    _cur_filename = None
    _next_check = 0
    _stat = None

    @classmethod
    def getName(cls, config):
        return 'file:' + config.file

    def __init__(self, config):
        super().__init__(config)
        self._orig_filename = os.path.abspath(config.file)
        self._maybe_reopen()

    def _maybe_reopen(self):
        new_filename = strftime(self.config.file, localtime())
        if new_filename != self._cur_filename or not self._stat:
            reopen = True
        else:
            try:
                newstat = os.stat(new_filename)
            except FileNotFoundError:
                newstat = None
            reopen = not newstat or (newstat.st_dev != self._stat.st_dev or
                                     newstat.st_ino != self._stat.st_ino)

        if not reopen:
            return

        if self._stat:
            self.handle.flush()
            self.handle.close()
            self.handle = self._stat = None

        env = self.config.environment
        self._cur_filename = new_filename

        self.handle = open_foruser(new_filename, 'w' if self.config.overwrite else 'a', env.uid, env.gid)
        self._stat = os.fstat(self.handle.fileno())

    def close(self):
        if self._stat:
            self.handle.close()
            self._stat = None
            self._next_check = 0
            self._cur_filename = None

    def write(self, data):
        if self._next_check <= time():
            self._maybe_reopen()
            self._next_check = time() + self.CHECK_INTERVAL
        super().write(data)

LogOutput.register(FileHandler)
