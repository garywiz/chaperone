import asyncio
from functools import partial

class ServerProtocol(asyncio.Protocol):

    @classmethod
    def buildProtocol(cls, parent):
        return partial(cls, parent)

    def __init__(self, parent):
        self.parent = parent
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport

class Server:

    protocol = ServerProtocol

    _server = None

    def run(self):
        loop = asyncio.get_event_loop()
        listen = self._create_server()
        future = asyncio.async(listen)
        future.add_done_callback(self._run_done)
        return future

    def _run_done(self, f):
        # Handle errors here!
        srv = f.result()
        if isinstance(srv, tuple):
            srv = srv[0]        # (transport,protocol) is returned by some
        self._server = srv

    def close(self):
        if self._server:
            self._server.close()
