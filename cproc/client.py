import asyncio

class CommandClient(asyncio.Protocol):

    @classmethod
    def sendCommand(cls, cmd):
        loop = asyncio.get_event_loop()
        coro = loop.create_unix_connection(lambda: CommandClient(cmd, loop), path = "/dev/chaperone.sock")
        loop.run_until_complete(coro)
        loop.run_forever()
        loop.close()

    def __init__(self, message, loop):
        self.message = message
        self.loop = loop

    def connection_made(self, transport):
        transport.write(self.message.encode())

    def data_received(self, data):
        msg = data.decode()
        print("GOT DATA", msg)

    def connection_lost(self, exc):
        self.loop.stop()

