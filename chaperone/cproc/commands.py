import os
import asyncio
import stat
import shlex
from functools import partial
from docopt import docopt

from chaperone.cutil.servers import Server, ServerProtocol
import chaperone.cutil.syslog_info as syslog_info

COMMAND_DOC = """
Usage: telchap status
       telchap shutdown
       telchap loglevel [<level>]
"""

class _BaseCommand(object):

    command_name = "X"

    def match(self, opts):
        return opts.get(self.command_name, False)

    def exec(self, opts, controller):
        try:
            return str(self.do_exec(opts, controller))
        except Exception as ex:
            return "Command error: " + str(ex)


class loglevelCommand(_BaseCommand):

    command_name = "loglevel"

    def do_exec(self, opts, controller):
        lev = opts['<level>']
        if lev is None:
            curlev = controller.force_log_level()
            if curlev is None:
                return "Forced Logging Level: NOT SET"
            try:
                pri = "*." + syslog_info.PRIORITY[curlev]
            except IndexError:
                pri = "Forced Logging Level: UNKNOWN"
            return pri
        if lev.startswith('*.'):
            lev = lev[2:]
        controller.force_log_level(lev)
        return "All logging set to include priorities >= *." + lev.lower()
            
COMMANDS = (
    loglevelCommand(),
)

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
            result = "?"
            for c in COMMANDS:
                if c.match(options):
                    result = c.exec(options, self.parent.controller)
                    break
            result = "RESULT\n" + result
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

    controller = None
    _fifoname = None
    _iserve = None

    def __init__(self, controller, filename = "/dev/chaperone"):
        """
        Creates a new command FIFO and socket.  The controller is the object to which commands and interactions
        will occur, usually a chaperone.cproc.process_manager.TopLevelProcess.
        """
        self.controller = controller
        self._fifoname = filename

    def _run_done(self, f):
        super()._run_done(f)
        self._iserve = _InteractiveServer()
        self._iserve.controller = self.controller # share this with our domain socket
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

