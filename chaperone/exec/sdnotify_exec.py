"""
Systemd notify exec shell (compatible with systemd-notify)
Runs a program and either proxies or simulates sd-notify functionality.

Usage:
    sdnotify-exec [options] COMMAND [ARGS ...]

Options:
    --noproxy             Ignores NOTIFY_SOCKET if inherited in the environment
                          and does not proxy messages.  Useful with --wait-xxx options..
    --wait-ready          If COMMAND exits normally, wait until either READY=1 or ERRNO=n, 
                          are sent to the notify socket, then return the exit
                          value from the command.
    --wait-stop           Will continue running even if COMMAND exits, continuing 
                          proxy services until ERRNO=n or STOPPING=1 are detected.
                          MAINPID notifications will be blocked, since the proxy
                          will continue to be the main program.  Overrides --wait-ready.
    --timeout secs        Specifies the timeout  before the lack of response triggers
                          an error exit.  COMMAND may continue to run.
                          (no effect without --wait-ready or --wait-stop)
    --socket name         Name of socket file created.  By default, a unique
                          socket name will be chosen automatically.
    --template value      Sets %{SOCKET_ARGS} template to 'value'.
    --verbose             Provide information about activity

Environment variables (one of which is SOCKET_ARGS) can be used anywhere in the
command by using the syntax %{VAR}.   The default SOCKET_ARGS template is designed 
for Docker and is set to:
  '--env NOTIFY_SOCKET=/tmp/notify-%{PID}.sock -v %{NOTIFY_SOCKET}:/tmp/notify-%{PID}.sock'

Thus, you can easily use "docker run" like this:

  sdnotify-exec docker run %{SOCKET_ARGS} some-image

Environment variables that can be useful:

  NOTIFY_SOCKET       Newly created notification socket
  ORIG_NOTIFY_SOCKET  Original notify socket (if any) passed to this program
  PID                 PID of the running sdnotify-exec program
  SOCKET_ARGS         Argument template

Only "NOTIFY_SOCKET" itself is passed to the created process, though all are available
for command and argument expansion.

"""

# perform any patches first
import chaperone.cutil.patches

# regular code begins
import sys
import os
import re
import signal
import asyncio
import shlex
from functools import partial
from docopt import docopt

from chaperone.cproc.version import VERSION_MESSAGE
from chaperone.cutil.notify import NotifyListener, NotifyClient
from chaperone.cutil.env import Environment

DEFAULT_TEMPLATE='--env NOTIFY_SOCKET=/tmp/notify-%{PID}.sock -v %{NOTIFY_SOCKET}:/tmp/notify-%{PID}.sock'

loop = asyncio.get_event_loop()
parent_socket = os.environ.get("NOTIFY_SOCKET")

RE_FIND_UNSAFE = re.compile(r'[^{}\w@%+=:,./-]', re.ASCII).search

def maybe_quote(s):
    if RE_FIND_UNSAFE(s) is None:
        return s
    return shlex.quote(s)

class SDNotifyExec:

    exitcode = 0
    sockname = None
    listener = None
    parent = None
    timeout = None
    wait_mode = None
    verbose = False

    parent_client = None
    proxy_enabled = True

    INFO_MESSAGE = {
        'READY': "READY={1}{2}",
        'MAINPID': "Process PID (={1}) notification{2}",
        'ERRNO': "Process ERROR (={1}) notification{2}",
        'STATUS': "Status message = '{1}'{2}",
        'default': "{0}={1}{2}",
    }

    def __init__(self, options):
        self.sockname = options['--socket']
        if not self.sockname:
            self.sockname = "/tmp/sdnotify-proxy-{0}.sock".format(os.getpid())

        self.proxy_enabled = parent_socket and not options['--noproxy']
        if options['--wait-stop']:
            self.wait_mode = 'stop'
        elif options['--wait-ready']:
            self.wait_mode = 'ready'

        if options['--timeout'] and self.wait_mode:
            self.timeout = float(options['--timeout'])

        self.verbose = options['--verbose']

        # Modify original environment

        os.environ['NOTIFY_SOCKET'] = self.sockname

        # Set up the environment, reparse the options, build the final command
        Environment.set_parse_parameters('%', '{')
        env = Environment()

        env['PID'] = str(os.getpid())
        env['SOCKET_ARGS'] = options['--template'] or DEFAULT_TEMPLATE
        if parent_socket:
            env['ORIG_NOTIFY_SOCKET'] = parent_socket
        
        env = env.expanded()

        self.proc_args = shlex.split(env.expand(' '.join(maybe_quote(arg) 
                                                         for arg in [options['COMMAND']] + options['ARGS'])))

        self.listener = NotifyListener(self.sockname, 
                                       onNotify = self.notify_received,
                                       onClose = self._parent_closed)
        loop.add_signal_handler(signal.SIGTERM, self._got_sig)
        loop.add_signal_handler(signal.SIGINT, self._got_sig)

        proctitle = '[sdnotify-exec]'

        try:
            from setproctitle import setproctitle
            setproctitle(proctitle)
        except ImportError:
            pass

    def info(self, msg):
        if self.verbose:
            print("info: " + msg)

    def _got_sig(self):
        self.kill_program()

    def kill_program(self, exitcode = None):
        if exitcode is not None:
            self.exitcode = exitcode
        loop.call_soon(self._really_kill)

    def _really_kill(self):
        self.listener.close()
        loop.stop()

    def _parent_closed(self, which, ex):
        if which == self.parent_client:
            self.proxy_enabled = False
            self.parent_client = None

    @asyncio.coroutine
    def _do_proxy_send(self, name, value):
        if not (parent_socket and self.proxy_enabled):
            return

        if not self.parent_client:
            self.parent_client = NotifyClient(parent_socket, onClose = self._parent_closed)
            yield from self.parent_client.run()

        yield from self.parent_client.send("{0}={1}".format(name, value))

    def send_to_proxy(self, name, value):
        asyncio.async(self._do_proxy_send(name, value))

    def notify_received(self, which, name, value):
        self.send_to_proxy(name, value)

        sent_info = False

        if self.wait_mode:
            if name == "READY" and value == "1":
                if self.wait_mode == 'ready':
                    sent_info = True
                    self.info("ready notification received (will exit)")
                    self.kill_program(0)
            elif name == "ERRNO":
                sent_info = True
                self.info("error notification ({0}) received from {1}".format(value, self.proc_args[0]))
                self.kill_program(int(value))
            elif name == "STOPPING" and value == "1":
                sent_info = True
                self.info("STOP notification received from {0} (will exit)".format(self.proc_args[0]))
                self.kill_program()

        if not sent_info:
            self.info(self.INFO_MESSAGE.get(name, self.INFO_MESSAGE['default']).
                      format(name, value, ' (ignored but passed on)' if self.proxy_enabled else ' (ignored)'))
                                                                                  
    @asyncio.coroutine
    def _notify_timeout(self):
        self.info("waiting {0} seconds for notification".format(self.timeout))
        yield from asyncio.sleep(self.timeout)
        print("ERROR: Timeout exceeded while waiting for notification from '{0}'".format(self.proc_args[0]))
        self.kill_program(1)

    @asyncio.coroutine
    def _run_process(self):

        self.info('running: {0}'.format(self.proc_args[0]))

        create = asyncio.create_subprocess_exec(*self.proc_args, start_new_session=bool(self.wait_mode))
        proc = yield from create

        if self.timeout:
            asyncio.async(self._notify_timeout())

        exitcode = yield from proc.wait()
        if not self.exitcode:   # may have arrived from ERRNO
            self.exitcode = exitcode

    @asyncio.coroutine
    def run(self):

        try:
            yield from self.listener.run()
        except ValueError as ex:
            print("Error while trying to create socket: " + str(ex))
            self.kill_program()
        else:
            try:
                yield from self._run_process()
            except Exception as ex:
                print("Error running command: " + str(ex))
                self.kill_program()

        # Command has executed, now determine our exit and proxy disposition

        if not self.wait_mode:
            self.info("program {0} exit({1}), terminating since --wait not specified".format(self.proc_args[0], self.exitcode))
            self.kill_program()

def main_entry():
    options = docopt(__doc__, options_first=True, version=VERSION_MESSAGE)

    mainclass = SDNotifyExec(options)
    asyncio.async(mainclass.run())

    loop.run_forever()
    loop.close()

    exit(mainclass.exitcode)
