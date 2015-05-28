"""
Lightweight process and service manager

Usage:
    chaperone [--config=<file_or_dir>] [--user=<name> | --create-user=<newuser>]
              [--nodelay] [--debug] [--force] [--exitkills | --no-exitkills]
              [--log-level=<level>]
              [<command> [<args> ...]]

Options:
    -v                       Provide verbose messages
    --config=<file_or_dir>   Specifies file or directory for configuration [default: /etc/chaperone/config.d]
    --nodelay                Eliminates delay before initial command prompt when there are services.
    --debug                  Turn on debugging features (same as --log-level=DEBUG)
    --log-level=<level>      Specify log level filtering, such as INFO, DEBUG, etc.
    --force                  If chaperone normally refuses, do it anyway and take the risk.
    --exitkills              When given command exits, kill the system (default if container running interactive)
    --no-exitkills           When givencommand exits, don't kill the system (default if container running daemon)
    --user=<name>            Start first process as user (else root)
    --create-user=<newuser>  Create a new user with an optional UID (name or name/uid), then run as if --user
                             was specified.

Notes:
  * If a user is specified, then the --config is relative to the user's home directory.
  * Chaperone makes the assumption that an interactive command should shut down the system upon exit,
    but a non-interactive command should not.  You can reverse this assumption with options.
"""

import sys
import os
import asyncio
import subprocess

from setproctitle import setproctitle
from functools import partial
from docopt import docopt

from chaperone.cutil.config import Configuration
from chaperone.cutil.logging import warn, info, debug, error
from chaperone.cproc import TopLevelProcess

MSG_PID1 = """Normally, chaperone expects to run as PID 1 in the 'init' role.
If you want to go ahead anyway, use --force."""

MSG_NOTHING_TO_DO = """There are no services configured to run, nor is there a command specified
on the command line to run as an application.  You need to do one or the other."""

def main_entry():
   options = docopt(__doc__, options_first=True)

   if options['--debug']:
      options['--log-level'] = "DEBUG"
      print('COMMAND OPTIONS', options)

   force = options['--force']

   if not force and os.getpid() != 1:
      print(MSG_PID1)
      exit(1)

   tty = sys.stdin.isatty()
   os.environ["_CHAPERONE_INTERACTIVE"] = "1" if tty else "0"

   kill_switch = options['--exitkills'] or (False if options['--no-exitkills'] else tty)

   tlp = TopLevelProcess.sharedInstance()
   if options['--log-level']:
      tlp.force_log_level(options['--log-level'])

   cmd = options['<command>']

   user = options['--user']

   if user is None:
      user = options['--create-user']
      if user:
         uargs = user.split('/')
         ucmd = ["useradd"]
         if len(uargs) > 2:
            print("Invalid format for --create-user argument: {0}".format(user))
            exit(1)
         if len(uargs) > 1:
            try:
               uid = int(uargs[1])
            except ValueError:
               print("Specified UID is not a number: {0}".format(user))
               exit(1)
            ucmd += ['-u', str(uid)]
         ucmd += [uargs[0]]
         if subprocess.call(ucmd):
            print("Error executing: {0}".format(' '.join(ucmd)))
            exit(1)
         user = uargs[0]

   config = Configuration.configFromCommandSpec(options['--config'], user=user)

   if not (config.get_services() or cmd):
      print(MSG_NOTHING_TO_DO)
      exit(1)

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
         error(ex, "System services startup cancelled due to error: {0}", ex)
         service_errors = True

      if cmd:
         if service_errors:
            warn("Service startup errors occurred.  Not running initial command: '{0}'", cmd)
         else:
            if not options['--nodelay']:
               yield from asyncio.sleep(2)
            try:
               sproc = tlp.run([cmd] + options['<args>'], user=user, wait=True, config=config)
               if kill_switch:
                  warn("system will be killed when '{0}' exits", cmd)
               yield from sproc
            except Exception as ex:
               error(ex, "Initial startup command ('{0}') did not run: {1}", cmd, ex)

         if kill_switch:
            tlp.kill_system()

   tlp.run_event_loop(config, startup_done())
