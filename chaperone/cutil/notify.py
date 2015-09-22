import asyncio
import socket
import re
from functools import partial

from chaperone.cutil.errors import ChProcessError
from chaperone.cutil.servers import Server, ServerProtocol
from chaperone.cutil.proc import ProcStatus
from chaperone.cproc.subproc import SubProcess

_RE_NOTIFY = re.compile(r'^([A-Za-z]+)=(.+)$')

class NotifyProtocol(ServerProtocol):

    notify_function = None

    def datagram_received(self, data, addr):
        lines = data.decode().split("\n")
        for line in lines:
            m = _RE_NOTIFY.match(line)
            if m and self.notify_function:
                self.notify_function(m.group(1), m.group(2))

    
class NotifyListener(Server):

    def _create_server(self):
        loop = asyncio.get_event_loop()
        return loop.create_datagram_endpoint(NotifyProtocol.buildProtocol(notify_function = self._notify_function), 
                                             family=socket.AF_UNIX)

    @property
    def socket_name(self):
        return "@" + self._socket_basename

    def __init__(self, socket_basename, notify_function):
        super().__init__()
        self._socket_basename = socket_basename
        self._notify_function = notify_function
        
    def server_running(self):
        (transport, protocol) = self.server
        transport._sock.bind("\0" + self._socket_basename)
