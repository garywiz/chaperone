"""
Lightweight process and service manager

Usage:
    chaperone [--config=<file_or_dir>]
              [--user=<name> | --create-user=<newuser>] [--default-home=<dir>]
              [--exitkills | --no-exitkills] [--ignore-failures] [--log-level=<level>] [--no-console-log]
              [--debug] [--force] [--disable-services] [--no-defaults] [--version] [--show-dependencies]
              [--task]
              [<command> [<args> ...]]

Options:
    --config=<file_or_dir>   Specifies file or directory for configuration (default is /etc/chaperone.d)
    --create-user=<newuser>  Create a new user with an optional UID (name or name/uid), 
                             then run as if --user was specified.
    --default-home=<dir>     If the --create-user home directory does not exist, then use this
                             directory as the default home directory for the new user instead.
    --debug                  Turn on debugging features (same as --log-level=DEBUG)
    --disable-services       Does not run any services, only the given command (troubleshooting)
    --exitkills              When given command exits, kill the system (default if container running interactive)
    --force                  If chaperone normally refuses, do it anyway and take the risk.
    --ignore-failures        Assumes that "ignore_failures:true" was specified on all services (troubleshooting)
    --log-level=<level>      Specify log level filtering, such as INFO, DEBUG, etc.
    --no-console-log         Disable all logging to stdout and stderr (useful when the container produces non-log output)
    --no-exitkills           When givencommand exits, don't kill the system (default if container running daemon)
    --no-defaults            Ignores any default options in the CHAPERONE_OPTIONS environment variable
    --user=<name>            Start first process as user (else root)
    --show-dependencies      Shows a list of service dependencies then exits
    --task                   Run in task mode (see below).
    --version                Display version and exit

Notes:
  * If a user is specified, then the --config is relative to the user's home directory.
  * Chaperone makes the assumption that an interactive command should shut down the system upon exit,
    but a non-interactive command should not.  You can reverse this assumption with options.
  * --task is used in cases where you wish to execute a script in the container environment
    for utility purposes, such as a script to extract data from the container, etc.  This switch
    is equivalent to "--log err --exitkills --disable-services" and also requires a command
    to be specified as usual.
"""

# perform any patches first
import chaperone.cutil.patches

# regular code begins
import sys
import shlex
import os
import re
import asyncio
import subprocess

from functools import partial
from docopt import docopt

from chaperone.cproc import TopLevelProcess
from chaperone.cproc.version import VERSION_MESSAGE
from chaperone.cutil.config import Configuration, ServiceConfig
from chaperone.cutil.env import ENV_INTERACTIVE, ENV_TASK_MODE, ENV_CHAP_OPTIONS
from chaperone.cutil.misc import maybe_create_user
from chaperone.cutil.logging import warn, info, debug, error

MSG_PID1 = """Normally, chaperone expects to run as PID 1 in the 'init' role.
If you want to go ahead anyway, use --force."""

MSG_NOTHING_TO_DO = """There are no services configured to run, nor is there a command specified
on the command line to run as an application.  You need to do one or the other."""

# We require usernames to start with a letter or underscore.  This is consistent with default Linux
# rules.  Yeah I know, regexes can get complicated, but they can also do a lot of work to make the
# rest of the code simpler.  Note that <file> matches strings like /foo:bar as a path of "/foo" with a
# groupname of bar, but the colon can be escaped if you actualy have a filename that contains
# a colon like "/foo\:bar".

RE_CREATEUSER = re.compile(
   r'''(?P<user>[a-z_][a-z0-9_-]*)           # ALWAYS start with the username
       (?::(?P<file>/(?:\\:|[^:])+))?        # File is next if it's :/path
       (?::(?P<uid>\d*))?                    # Either /uid or :uid introduces a uid (number may be missing)
       (?::(?P<gid>[a-z_][a-z0-9_-]*|\d+)?)? # followed by an optional GID
       $''',
   re.IGNORECASE | re.X)

def main_entry():

   # parse these first since we may disable the environment check
   options = docopt(__doc__, options_first=True, version=VERSION_MESSAGE)

   if options['--task']:
      options['--disable-services'] = True
      options['--no-console-log'] = True
      options['--exitkills'] = True
      os.environ[ENV_TASK_MODE] = '1'

   if not options['--no-defaults']:
      envopts = os.environ.get(ENV_CHAP_OPTIONS)
      if envopts:
         try:
            defaults = docopt(__doc__, argv=(shlex.split(envopts)), options_first=True)
         except SystemExit as ex:
            print("Error occurred in {0} environment variable: {1}".format(ENV_CHAP_OPTIONS, envopts))
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

   cmd = options['<command>']

   if options['--task'] and not cmd:
      error("--task can only be used if a shell command is specified as an argument")
      exit(1)

   # It's possible that BOTH --create-user and --user exist due to the way _CHAP_OPTIONS is overlaid
   # with command line options.  So, in such a case, note that we ignore --user.

   create = options['--create-user']

   if create is None:
      user = options['--user']
   else:
     match = RE_CREATEUSER.match(create)
     if not match:
        print("Invalid format for --create-user argument: {0}".format(create))
        exit(1)
     udata = match.groupdict()
     try:
        maybe_create_user(udata['user'], udata['uid'] or None, udata['gid'] or None, 
                          udata['file'] and udata['file'].replace(r'\:', ':'),
                          options['--default-home'])
     except Exception as ex:
        print("--create-user failure: {0}".format(ex))
        exit(1)
     user = udata['user']

   extras = None
   if options['--ignore-failures']:
      extras = {'ignore_failures': True}
      
   try:
      config = Configuration.configFromCommandSpec(options['--config'], user=user, extra_settings=extras,
                                                   disable_console_log=options['--no-console-log'])
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

   # Now, create the tlp and proceed

   tlp = TopLevelProcess(config)

   if options['--log-level']:
      tlp.force_log_level(options['--log-level'])

   if tlp.debug:
      config.dump()

   # Set proctitle and go

   proctitle = "[" + os.path.basename(sys.argv[0]) + "]"
   if cmd:
      proctitle += " " + cmd

   try:
      from setproctitle import setproctitle
      setproctitle(proctitle)
   except ImportError:
      pass

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
                                             kill_signal=("SIGHUP" if tty else None),
                                             setpgrp=not tty,
                                             exit_kills=kill_switch,
                                             service_groups="IDLE",
                                             ignore_failures=not options['--task'],
                                             stderr='inherit', stdout='inherit')
         extra_services = [cmdsvc]

      yield from tlp.run_services(extra_services, disable_others = options['--disable-services'])

      tlp.signal_ready()

   tlp.run_event_loop(startup_done())
