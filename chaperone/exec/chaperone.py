"""
Lightweight process and service manager

Usage:
    chaperone [--user=<name>]
              [--config=<file_or_dir>] 
              [--shutdown_on_exit] [--nodelay] [--debug]
              [--log-level=<level>]
              [<command> [<args> ...]]

Options:
    -v                       Provide verbose messages
    --user=<name>            Start first process as user (else root)
    --config=<file_or_dir>   Specifies file or directory for configuration [default: /etc/chaperone.d]
    --shutdown_on_exit       If set, then the entire system will be shutdown when the given command (if any)
                             terminates.
    --nodelay                Eliminates delay before initial command prompt when there are services.
    --debug                  Turn on debugging features (same as --log-level=DEBUG)
    --log-level=<level>      Specify log level filtering, such as INFO, DEBUG, etc.

If a user is specified, then the basename of file_or_dir is searched in the user's directory, and it
must be owned by the user to take effect.
"""

import sys
import os
import asyncio
import logging
from setproctitle import setproctitle
from functools import partial
from docopt import docopt

from chaperone.cproc import TopLevelProcess
from chaperone.cutil.config import Configuration
from chaperone.cutil.logging import warn, info, debug, error

def main_entry():
    options = docopt(__doc__, options_first=True)

    if options['--debug']:
       options['--log-level'] = "DEBUG"
       print('COMMAND OPTIONS', options)

    tlp = TopLevelProcess.sharedInstance()
    if options['--log-level']:
       tlp.force_log_level(options['--log-level'])

    cmd = options['<command>']

    config = Configuration.configFromCommandSpec(options['--config'], user=options['--user'])

    if tlp.debug:
       config.dump()

    proctitle = "[" + os.path.basename(sys.argv[0]) + "]"
    if cmd:
       proctitle += " " + cmd  + " " + " ".join(options['<args>'])
    setproctitle(proctitle)

    # Define here so we can share scope

    @asyncio.coroutine
    def startup_done():

       service_errors = False

       try:
          yield from tlp.run_services(config)
       except Exception as ex:
          error("System services startup cancelled due to error: {0}", ex)
          service_errors = True

       if cmd:
          if service_errors:
             warn("Service startup errors occurred.  Not running initial command: '{0}'", cmd)
          else:
            if not options['--nodelay']:
               yield from asyncio.sleep(2)
            try:
               sproc = tlp.run([cmd] + options['<args>'], user=(options.get('--user')), wait=True, config=config)
               yield from sproc
            except Exception as ex:
               error("Initial startup command ('{0}') did not run: {1}", cmd, ex)

          if options['--shutdown_on_exit']:
             tlp.kill_system()

    tlp.run_event_loop(config, startup_done())
