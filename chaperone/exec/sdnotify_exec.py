"""
Systemd notify exec shell (compatible with systemd-notify)
Runs a program and either proxies or simulates sd-notify functionality.

Usage:
    sdnotify-exec [options] COMMAND [ARGS ...]

Options:
    --noproxy             Ignores NOTIFY_SOCKET if inherited in the environment
                          and does not proxy messages.  Useful with --wait.
    --wait                Waits until COMMAND signals either READY=1 or ERRNO=n, 
                          which will be returned as the exit code.
    --timeout secs        If waiting for process completion specifies the timeout 
                          before the lack of response triggers and error exit.
    --socket name         Name of socket file created.  By default, a unique
                          socket name will be chosen automatically.
    --template value      Sets %{SOCKET_ARGS} template to 'value'.

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

    parent_client = None
    proxy_enabled = True

    def __init__(self, options):
        self.sockname = options['--socket']
        if not self.sockname:
            self.sockname = "/tmp/sdnotify-proxy-{0}.sock".format(os.getpid())

        self.proxy_enabled = not options['--noproxy']

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

    def _got_sig(self):
        self.kill_program()

    def kill_program(self):
        self.listener.close()
        loop.stop()

    def _parent_closed(self, which, ex):
        if which == self.parent_client:
            print("Parent closed due to " + str(ex))
            self.proxy_enabled = False
            self.parent_client = None
        elif which == self.listener:
            print("Listener closed due to " + str(ex))

    @asyncio.coroutine
    def _do_proxy_send(self, name, value):
        if not (parent_socket and self.proxy_enabled):
            return

        if not self.parent_client:
            self.parent_client = NotifyClient(parent_socket, onClose = self._parent_closed)
            yield from self.parent_client.run()

        print("_do_proxy_send", name, value)
        yield from self.parent_client.send("{0}={1}".format(name, value))

    def send_to_proxy(self, name, value):
        asyncio.async(self._do_proxy_send(name, value))

    def notify_received(self, which, name, value):
        print("got notify", os.getpid(), name, value, which)
        self.send_to_proxy(name, value)

    @asyncio.coroutine
    def _run_process(self):
        create = asyncio.create_subprocess_exec(*self.proc_args)
        proc = yield from create
        self.exitcode = yield from proc.wait()

    @asyncio.coroutine
    def run(self):
        try:
            yield from self.listener.run()
        except ValueError as ex:
            print("Error while trying to create socket: " + str(ex))
        else:
            try:
                yield from self._run_process()
            except Exception as ex:
                print("Error running command: " + str(ex))
            
        loop.call_soon(self.kill_program)

def main_entry():
    options = docopt(__doc__, options_first=True, version=VERSION_MESSAGE)

    mainclass = SDNotifyExec(options)
    asyncio.async(mainclass.run())

    loop.run_forever()
    loop.close()

    exit(mainclass.exitcode)
