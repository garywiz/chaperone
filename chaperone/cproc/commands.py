import os
import asyncio
import stat
import shlex
from functools import partial
from docopt import docopt

from chaperone.cutil.servers import Server, ServerProtocol
from chaperone.cutil.misc import maybe_remove
import chaperone.cutil.syslog_info as syslog_info

COMMAND_DOC = """
Usage: telchap status
       telchap shutdown
       telchap loglevel [<level>]
       telchap service <servname> stop
       telchap service <servname> start
       telchap service <servname> status
"""

CHAP_FIFO = "/dev/chaperone"
CHAP_SOCK = "/dev/chaperone.sock"

class _BaseCommand(object):

    command_name = "X"
    interactive_only = False

    def match(self, opts):
        if isinstance(self.command_name, tuple):
            return all(opts.get(name, False) for name in self.command_name)
        return opts.get(self.command_name, False)

    @asyncio.coroutine
    def exec(self, opts, controller):
        try:
            result = yield from self.do_exec(opts, controller)
            return str(result)
        except Exception as ex:
            return "Command error: " + str(ex)


STMSG = """
Running:           {0.version}
Uptime:            {0.uptime}
Managed processes: {1} ({2} enabled)
"""

class statusCommand(_BaseCommand):

    command_name = "status"
    interactive_only = True

    @asyncio.coroutine
    def do_exec(self, opts, controller):
        serv = controller.services
        msg = STMSG.format(controller, len(serv), len([s for s in serv.values() if s.enabled]))
        msg += "\nServices:\n\n" + str(serv.get_status_formatter().get_formatted_data()) + "\n"
        return msg

class serviceCommandBase(_BaseCommand):

    @asyncio.coroutine
    def do_exec(self, opts, controller):
        servname = opts['<servname>']
        serv = controller.services.get(servname)
        if not serv:
            serv = controller.services.get(servname + ".service")
        if not serv:
            raise Exception("no such service: " + servname)
        result = yield from self.do_service_command(serv)
        return result

class serviceStop(serviceCommandBase):

    command_name = ('service', 'stop')

    @asyncio.coroutine
    def do_service_command(self, serv):
        yield from serv.stop()
        return "service {0} stopped".format(serv.name)

class serviceStart(serviceCommandBase):

    command_name = ('service', 'start')

    @asyncio.coroutine
    def do_service_command(self, serv):
        yield from serv.start()
        return "service {0} started".format(serv.name)

class loglevelCommand(_BaseCommand):

    command_name = "loglevel"

    @asyncio.coroutine
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
            
##
## Register all commands here
##

COMMANDS = (
    loglevelCommand(),
    statusCommand(),
    serviceStop(),
    serviceStart(),
)

class CommandProtocol(ServerProtocol):

    interactive = False

    @asyncio.coroutine
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
                if c.match(options) and (not c.interactive_only or self.interactive):
                    result = yield from c.exec(options, self.parent.controller)
                    break
            result = "RESULT\n" + result
        return result

    @asyncio.coroutine
    def _command_task(self, cmd, interactive = False):
        result = yield from self._interpret_command(cmd)
        if interactive:
            self.transport.write(result.encode())
            self.transport.close()

    def data_received(self, data):
        if self.interactive:
            asyncio.async(self._command_task(data.decode(), True))
        else:
            commands = data.decode().split("\n")
            for c in commands:
                asyncio.async(self._command_task(c))

class _InteractiveServer(Server):

    def _create_server(self):
        maybe_remove(CHAP_SOCK)
        return asyncio.get_event_loop().create_unix_server(CommandProtocol.buildProtocol(parent=self,interactive=True), 
                                                           path=CHAP_SOCK)

    def _run_done(self, f):
        super()._run_done(f)
        os.chmod(CHAP_SOCK, 0o777)

    def close(self):
        super().close()
        maybe_remove(CHAP_SOCK)

class CommandServer(Server):

    controller = None
    _fifoname = None
    _iserve = None

    def __init__(self, controller, filename = CHAP_FIFO):
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

        maybe_remove(name)
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
        maybe_remove(CHAP_FIFO)
        if self._iserve:
            self._iserve.close()

