import asyncio
from functools import partial
from chaperone.cutil.events import EventSource

class ServerProtocol(asyncio.Protocol):

    @classmethod
    def buildProtocol(cls, owner, **kwargs):
        return partial(cls, owner, **kwargs)

    def __init__(self, owner, **kwargs):
        """
        Copy keywords directly into attributes when each protocol is created.
        This creates flexibility so that various servers can pass information to protocols.
        """
        
        super().__init__()

        self.owner = owner
        self.events = self.owner.events

        for k,v in kwargs.items():
            setattr(self, k, v)

    def connection_made(self, transport):
        self.transport = transport
        self.events.onConnection(self.owner)

    def error_received(self, exc):
        self.events.onError(self.owner, exc)
        self.events.onClose(self.owner, exc)

    def connection_lost(self, exc):
        self.events.onClose(self.owner, exc)

class Server:

    server = None

    def __init__(self, **kwargs):
        self.events = EventSource(**kwargs)

    @asyncio.coroutine
    def run(self):
        self.loop = asyncio.get_event_loop()
        self.server = yield from self._create_server()
        yield from self.server_running()

    @asyncio.coroutine
    def server_running(self):
        pass

    def close(self):
        s = self.server
        if s:
            if isinstance(s, tuple):
                s = s[0]
            s.close()
