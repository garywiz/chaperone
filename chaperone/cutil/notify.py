import asyncio
import socket
import os
import re

from chaperone.cutil.servers import Server, ServerProtocol
from chaperone.cutil.misc import maybe_remove

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
        if not self._socket_name.startswith('@'):
            maybe_remove(self._socket_name)


# A lot like a socket server, there are only subtle differences.

class NotifyClient(NotifyListener):

    @property
    def is_client(self):
        return True
