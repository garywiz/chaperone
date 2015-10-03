import asyncio
import socket
import os
import re

from chaperone.cutil.servers import Server, ServerProtocol
from chaperone.cutil.misc import maybe_remove
from chaperone.cutil.logging import debug

_RE_NOTIFY = re.compile(r'^([A-Za-z]+)=(.+)$')

class NotifyProtocol(ServerProtocol):

    def datagram_received(self, data, addr):
        lines = data.decode().split("\n")
        for line in lines:
            m = _RE_NOTIFY.match(line)
            if m:
                self.events.onNotify(self.owner, m.group(1), m.group(2))


class NotifyListener(Server):

    def _create_server(self):
        loop = asyncio.get_event_loop()
        return loop.create_datagram_endpoint(NotifyProtocol.buildProtocol(self), family=socket.AF_UNIX)

    @property
    def is_client(self):
        return False

    @property
    def socket_name(self):
        return self._socket_name

    @property
    def bind_name(self):
        if self._socket_name.startswith('@'):
            return self._socket_name.replace('@', "\0")
        return self._socket_name

    def __init__(self, socket_name, **kwargs):
        super().__init__(**kwargs)
        self._socket_name = socket_name
        
    @asyncio.coroutine
    def send(self, message):
        if not self.server:
            yield from self.run()

        self.server[0].sendto(message.encode(), self.bind_name)

    @asyncio.coroutine
    def server_running(self):
        (transport, protocol) = self.server

        bindname = self.bind_name

        # Clients connect to an existing socket
        if self.is_client:
            loop = asyncio.get_event_loop()
            yield from loop.sock_connect(transport._sock, bindname)
            return

        # Servers set up a binding to a new one
        transport._sock.bind(bindname)

        if not bindname.startswith("\0"): # if not abstract socket
            os.chmod(bindname, 0o777)

    def close(self):
        super().close()
        if not (self.is_client or self._socket_name.startswith('@')):
            maybe_remove(self._socket_name)


# A lot like a socket server, there are only subtle differences.

class NotifyClient(NotifyListener):

    @property
    def is_client(self):
        return True

# A sink to specific notify messages.  Can operate with or without a client,
# and has multiple levels of support.

class NotifySink:

    NSLEV = 0       # level 0: nothing
    NSLEV = 1       # level 1: only READY notifications
    NSLEV = 2       # level 2: READY and STATUS
    NSLEV = 3       # level 3: adds ERRNO, STARTING and STOPPING messages

    _LEVS = [
        set(),
        {'READY'},
        {'READY', 'STATUS'},
        {'READY', 'STATUS', 'ERRNO', 'STOPPING'},
    ]

    _client = None
    _lev = None
    _sent = None

    def __init__(self):
        self.level = 99
        self._sent = set()

    @property
    def level(self):
        try:
            return self._LEVS.index(self._lev)
        except ValueError:
            return None

    @level.setter
    def level(self, val):
        if val > len(self._LEVS):
            val = len(self._LEVS) - 1
        self._lev = self._LEVS[val].copy()

    def enable(self, ntype):
        self._lev.add(ntype.upper())

    def disable(self, ntype):
        self._lev.discard(ntype.upper())

    def error(self, val):
        if not self.sent("ERRNO"):
            self.send("ERRNO", int(val))

    def stopping(self):
        if not self.sent("STOPPING"):
            self.send("STOPPING", 1)

    def ready(self):
        if not self.sent("READY"):
            self.send("READY", 1)

    def status(self, statmsg):
        self.send("STATUS", statmsg)

    def mainpid(self):
        self.send("MAINPID", os.getpid())

    def sent(self, name):
        return name in self._sent

    def send(self, name, val):
        if name not in self._lev:
            return
        self._sent.add(name)
        if self._client:
            debug("queueing '{0}={1}' to notify socket '{2}'".format(name, val, self._client.socket_name))
            asyncio.async(self._do_send("{0}={1}".format(name, val)))

    @asyncio.coroutine
    def _do_send(self, msg):
        if self._client:
            yield from self._client.send(msg)

    @asyncio.coroutine
    def connect(self, socket = None):
        """
        Connects to the notify socket.  However, if we can't, it's not considered an error.
        We just return False.
        """

        self.close()

        if socket is None:
            if "NOTIFY_SOCKET" not in os.environ:
                return False
            socket = os.environ["NOTIFY_SOCKET"]
        
        self._client = NotifyClient(socket, 
                                    onClose = lambda which,exc: self.close(),
                                    onError = lambda which,exc: debug("{0} error, notifications disabled".format(socket)))

        try:
            yield from self._client.run()
        except OSError as ex:
            debug("could not connect to notify socket '{0} ({1})".format(socket, ex))
            self.close()
            return False

        return True
        
    def close(self):
        if not self._client:
            return
        self._client.close()
        self._client = None
