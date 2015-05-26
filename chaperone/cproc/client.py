import asyncio

class CommandClient(asyncio.Protocol):

    @classmethod
    def sendCommand(cls, cmd):
        loop = asyncio.get_event_loop()
        coro = loop.create_unix_connection(lambda: CommandClient(cmd, loop), path = "/dev/chaperone.sock")
        (transport, protocol) = loop.run_until_complete(coro)
        loop.run_forever()
        loop.close()
        return protocol.result

    def __init__(self, message, loop):
        self.message = message
        self.loop = loop
        self.result = None

    def connection_made(self, transport):
        transport.write(self.message.encode())

    def data_received(self, data):
        msg = data.decode()
        lines = msg.split("\n")
        error = None

        if lines[0] in {'COMMAND-ERROR', 'RESULT'}:
            self.result = "\n".join(lines[1:])
        else:
            error = "Unexpected response from chaperone: " + str(msg)

        if error:
            raise Exception(error)

    def connection_lost(self, exc):
        self.loop.stop()

