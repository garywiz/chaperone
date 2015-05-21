import os
import asyncio
import stat
import shlex
from functools import partial
from docopt import docopt

from chaperone.cutil.servers import Server, ServerProtocol

COMMAND_DOC = """
Usage: telchap status
       telchap shutdown
       telchap help
"""

class CommandProtocol(ServerProtocol):

    interactive = False

    def _interpret_command(self, msg):
        if not msg:
            return
        try:
            options = docopt(COMMAND_DOC, shlex.split(msg), help=False)
        except Exception as ex:
            result = "EXCEPTION\n" + str(ex)
        except SystemExit as ex:
            result = "COMMAND-ERROR\n" + str(ex)
        else:
            result = "RESULT\n" + str(options)
        return result

    def data_received(self, data):
        if self.interactive:
            result = self._interpret_command(data.decode())
            self.transport.write(result.encode())
            self.transport.close()
        else:
            commands = data.decode().split("\n")
            for c in commands:
                self._interpret_command(c)

class _InteractiveServer(Server):

    def _create_server(self):
        return asyncio.get_event_loop().create_unix_server(CommandProtocol.buildProtocol(parent=self,interactive=True), 
                                                           path="/dev/chaperone.sock")

    def _run_done(self, f):
        super()._run_done(f)
        os.chmod("/dev/chaperone.sock", 0o777)

class CommandServer(Server):

    _fifoname = None
    _iserve = None

    def __init__(self, filename = "/dev/chaperone"):
        self._fifoname = filename

    def _run_done(self, f):
        super()._run_done(f)
        self._iserve = _InteractiveServer()
        asyncio.async(self._iserve.run())

    def _open(self):
        name = self._fifoname

        if not os.path.exists(name):
            os.mkfifo(name)

        if not stat.S_ISFIFO(os.stat(name).st_mode):
            raise TypeError("File is not a fifo: " + str(name))

        os.chmod(name, 0o777)

        return open(os.open(name, os.O_RDWR|os.O_NONBLOCK))
            
    def _create_server(self):
        return asyncio.get_event_loop().connect_read_pipe(CommandProtocol.buildProtocol(parent=self), self._open())

    def close(self):
        super().close()
        if self._iserve:
            self._iserve.close()

