"""
Lightweight process and service manager

Usage:
    chaperone [--config=<file_or_dir>] [--user=<name> | --create-user=<newuser>]
              [--exitkills | --no-exitkills] [--ignore-failures] [--log-level=<level>]
              [--debug] [--force] [--disable-services] [--no-defaults] [--version] [--show-dependencies]
              [<command> [<args> ...]]

Options:
    --config=<file_or_dir>   Specifies file or directory for configuration (default is /etc/chaperone.d)
    --create-user=<newuser>  Create a new user with an optional UID (name or name/uid), 
                             then run as if --user was specified.
    --debug                  Turn on debugging features (same as --log-level=DEBUG)
    --disable-services       Does not run any services, only the given command (troubleshooting)
    --exitkills              When given command exits, kill the system (default if container running interactive)
    --force                  If chaperone normally refuses, do it anyway and take the risk.
    --ignore-failures        Assumes that "ignore_failures:true" was specified on all services (troubleshooting)
    --log-level=<level>      Specify log level filtering, such as INFO, DEBUG, etc.
    --no-exitkills           When givencommand exits, don't kill the system (default if container running daemon)
    --no-defaults            Ignores any default options in the CHAPERONE_OPTIONS environment variable
    --user=<name>            Start first process as user (else root)
    --show-dependencies      Shows a list of service dependencies then exits
    --version                Display version and exit

Notes:
  * If a user is specified, then the --config is relative to the user's home directory.
  * Chaperone makes the assumption that an interactive command should shut down the system upon exit,
    but a non-interactive command should not.  You can reverse this assumption with options.
"""

# perform any patches first
import chaperone.cutil.patches

# regular code begins
import sys
import shlex
import os
import asyncio
import subprocess

from setproctitle import setproctitle
from functools import partial
from docopt import docopt

from chaperone.cproc import TopLevelProcess
from chaperone.cproc.version import VERSION_MESSAGE
from chaperone.cutil.config import Configuration, ServiceConfig
from chaperone.cutil.env import ENV_INTERACTIVE
from chaperone.cutil.logging import warn, info, debug, error

MSG_PID1 = """Normally, chaperone expects to run as PID 1 in the 'init' role.
If you want to go ahead anyway, use --force."""

MSG_NOTHING_TO_DO = """There are no services configured to run, nor is there a command specified
on the command line to run as an application.  You need to do one or the other."""

def main_entry():

   # parse these first since we may disable the environment check
   options = docopt(__doc__, options_first=True, version=VERSION_MESSAGE)

   if not options['--no-defaults']:
      envopts = os.environ.get('CHAPERONE_OPTIONS')
      if envopts:
         try:
            defaults = docopt(__doc__, argv=(shlex.split(envopts)), options_first=True)
         except SystemExit as ex:
            print("Error occurred in CHAPERONE_OPTIONS environment variable: " + envopts)
            raise
         # Replace any "false" command option with the default version.
         options.update({k:defaults[k] for k in options.keys() if not options[k]})

   if options['--config'] is None:
      options['--config'] = '/etc/chaperone.d'

   if options['--debug']:
      options['--log-level'] = "DEBUG"
      print('COMMAND OPTIONS', options)

   force = options['--force']

   if not force and os.getpid() != 1:
      print(MSG_PID1)
      exit(1)

   tty = sys.stdin.isatty()
   os.environ[ENV_INTERACTIVE] = "1" if tty else "0"

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

   extras = None
   if options['--ignore-failures']:
      extras = {'ignore_failures': True}
      
   try:
      config = Configuration.configFromCommandSpec(options['--config'], user=user, extra_settings=extras)
      services = config.get_services()
   except Exception as ex:
      error(ex, "Configuration Error: {0}", ex)
      exit(1)

   if not (services or cmd):
      print(MSG_NOTHING_TO_DO)
      exit(1)

   if options['--show-dependencies']:
      dg = services.get_dependency_graph()
      print("\n".join(dg))
      exit(0)

   if not cmd and options['--disable-services']:
      error("--disable-services not valid without specifying a command to run")
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

      if options['--ignore-failures']:
         warn("ignoring failures on all service startups due to --ignore-failures")

      if options['--disable-services'] and services:
         warn("services will not be configured due to --disable-services")

      extra_services = None
      if cmd:
         cmdsvc = ServiceConfig.createConfig(config=config,
                                             name="CONSOLE",
                                             exec_args=[cmd] + options['<args>'],
                                             uid=user,
                                             setpgrp=not tty,
                                             exit_kills=kill_switch,
                                             service_group="IDLE",
                                             ignore_failures="true",
                                             stderr='inherit', stdout='inherit')
         extra_services = [cmdsvc]

      try:
         yield from tlp.run_services(config, extra_services, extra_only = options['--disable-services'])
      except Exception as ex:
         error(ex, "System startup cancelled due to error: {0}", ex)
         service_errors = True
         tlp.kill_system()

   tlp.run_event_loop(config, startup_done())
