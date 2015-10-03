import os
import asyncio
import stat
import shlex
from functools import partial
from docopt import docopt

from chaperone.cutil.servers import Server, ServerProtocol
from chaperone.cutil.misc import maybe_remove
from chaperone.cutil.logging import debug, warn, info
import chaperone.cutil.syslog_info as syslog_info

COMMAND_DOC = """
Usage: telchap status
       telchap loglevel [<level>]
       telchap stop [--force] [--wait] [--disable] [<servname> ...]
       telchap start [--force] [--wait] [--enable] [<servname> ...]
       telchap reset [--force] [--wait] [<servname> ...]
       telchap enable [<servname> ...]
       telchap disable [<servname> ...]
       telchap dependencies
       telchap shutdown [<delay>]
"""

CHAP_FIFO = "/dev/chaperone"
CHAP_SOCK = "/dev/chaperone.sock"

class _BaseCommand(object):

    command_name = "X"
    interactive_only = False
    interactive = False

    def match(self, opts):
        if isinstance(self.command_name, tuple):
            return all(opts.get(name, False) for name in self.command_name)
        return opts.get(self.command_name, False)

    @asyncio.coroutine
    def exec(self, opts, protocol):
        #result = yield from self.do_exec(opts, controller)
        #return str(result)
        self.interactive = protocol.interactive
        try:
            result = yield from self.do_exec(opts, protocol.owner.controller)
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

class dependenciesCommand(_BaseCommand):

    command_name = "dependencies"
    interactive_only = True

    @asyncio.coroutine
    def do_exec(self, opts, controller):
        graph = controller.services.services_config.get_dependency_graph()
        return "\n".join(graph)

class serviceReset(_BaseCommand):

    command_name = 'reset'

    @asyncio.coroutine
    def do_exec(self, opts, controller):
        wait = opts['--wait'] and self.interactive
        yield from controller.services.reset(opts['<servname>'], force = opts['--force'], wait = wait)
        return "services reset."

class serviceEnable(_BaseCommand):

    command_name = 'enable'

    @asyncio.coroutine
    def do_exec(self, opts, controller):
        yield from controller.services.enable(opts['<servname>'])
        return "services enabled."

class serviceDisable(_BaseCommand):

    command_name = 'disable'

    @asyncio.coroutine
    def do_exec(self, opts, controller):
        yield from controller.services.disable(opts['<servname>'])
        return "services disabled."

class serviceStart(_BaseCommand):

    command_name = 'start'

    @asyncio.coroutine
    def do_exec(self, opts, controller):
        wait = opts['--wait'] and self.interactive
        yield from controller.services.start(opts['<servname>'], force = opts['--force'],
                                             wait = wait,
                                             enable = opts['--enable'])
        if wait:
            return "services started."
        return "service start-up queued."

class serviceStop(_BaseCommand):

    command_name = 'stop'

    @asyncio.coroutine
    def do_exec(self, opts, controller):
        wait = opts['--wait'] and self.interactive
        yield from controller.services.stop(opts['<servname>'], force = opts['--force'], 
                                            wait = wait,
                                            disable = opts['--disable'])
        if wait:
            return "services stopped."
        return "services stopping."

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
            
class shutdownCommand(_BaseCommand):

    command_name = "shutdown"

    @asyncio.coroutine
    def do_exec(self, opts, controller):
        delay = opts['<delay>']

        if delay is None or delay.lower() == "now":
            delay = 0.1
            message = "Shutting down now"
        else:
            try:
                delay = float(delay)
            except ValueError:
                return "Specified delay is not a valid decimal number: " + str(delay)
            message = "Shutting down in {0} seconds".format(delay)

        info("requested shutdown scheduled to occur in {0} seconds".format(delay))
        asyncio.get_event_loop().call_later(delay, controller.kill_system)

        return message
            
##
## Register all commands here
##

COMMANDS = (
    loglevelCommand(),
    shutdownCommand(),
    statusCommand(),
    serviceStop(),
    serviceStart(),
    serviceReset(),
    serviceEnable(),
    serviceDisable(),
    dependenciesCommand(),
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
                    result = yield from c.exec(options, self)
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
        return asyncio.get_event_loop().create_unix_server(CommandProtocol.buildProtocol(self, interactive=True), 
                                                           path=CHAP_SOCK)

    @asyncio.coroutine
    def server_running(self):
        os.chmod(CHAP_SOCK, 0o777)

    def close(self):
        super().close()
        maybe_remove(CHAP_SOCK)


class CommandServer(Server):

    controller = None
    _fifoname = None
    _iserve = None

    def __init__(self, controller, filename = CHAP_FIFO, **kwargs):
        """
        Creates a new command FIFO and socket.  The controller is the object to which commands and interactions
        will occur, usually a chaperone.cproc.process_manager.TopLevelProcess.
        """
        super().__init__(**kwargs)

        self.controller = controller
        self._fifoname = filename

    @asyncio.coroutine
    def server_running(self):
        self._iserve = _InteractiveServer()
        self._iserve.controller = self.controller # share this with our domain socket
        yield from self._iserve.run()

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
        return asyncio.get_event_loop().connect_read_pipe(CommandProtocol.buildProtocol(self), self._open())

    def close(self):
        super().close()
        maybe_remove(CHAP_FIFO)
        if self._iserve:
            self._iserve.close()

