.. chaperone documentation
   configuration directives

.. include:: /includes/defs.rst

.. _service:

Configuration: Service Declarations
===================================

Service Quick Reference
-----------------------

Service configurations are identified by user-defined names and end with the suffix ``.service``.  So,
for example, the following defines a registration script called ``register_my_app`` which runs when all other
services have been launched::

  myreg.service: {
    type: oneshot,
    command: "/usr/local/bin/register_my_app --host central-registry.example.com",
    service_groups: IDLE,
  }

Multiple services can be declared in a single file.  Order within a configuration file is not important.
However, if several configuration files are involved, services in subsequent files (alphabetically) will
replace earlier services defined with the same name.

Each service inherits the environment defined by the :ref:`settings directive <config.settings>` and
can be tailored separately for the needs of each service.  Entries below marked with |ENV| support
:ref:`environment variable expansion <env.expansion>`.

.. _table.service-quick:

.. table::  Service Directives Quick Reference

   ================================================  =============================================================================
   service variable                                  meaning
   ================================================  =============================================================================
   :ref:`type <service.type>`                        Defines the service type: 'oneshot', 'simple', forking', 'notify', 'inetd',
                                                     or 'cron'.  Default is 'simple'.
   :ref:`command <service.command>`                  Specifies the command to execute.  The command is not processed by a shell,
                                                     but environment variable expansion is supported. |ENV|
   :ref:`enabled <service.enabled>`                  If 'false', the service will not be started, nor will it be required by
                                                     any dependents.  Default is 'true'. |ENV|
   :ref:`stderr <service.stderr>`                    Either 'log' to write stderr to the syslog, or 'inherit' to write stderr
                                                     to the container's stderr file handle.   Default is 'log'. |ENV|
   :ref:`stdout <service.stdout>`                    Either 'log' to write stdout to the syslog, or 'inherit' to write stdout
                                                     to the container's stdout file handle.   Default is 'log'. |ENV|
   :ref:`port <service.port>`			     For service type 'inetd', specifies the dynamic port number for 
   	      					     connections.  There is no default. |ENV|
   :ref:`after <service.after>`                      A comma-separated list of services or service groups which must start
                                                     before this service is allowed ot start (dependencies).
   :ref:`before <service.before>`                    A comma-separated list of services or service groups which cannot be
                                                     started until this service starts successfully (dependents).
   :ref:`directory <service.directory>`              The directory where the command will be executed.  Otherwise, the account
                                                     home directory will be used. |ENV|
   :ref:`env_inherit <service.env_inherit>`          An array of patterns which can match one or more
                                                     environment variables.  Environment variables which
                                                     do not match any pattern will be excluded.  Default is ``['*']``.
   :ref:`env_set <service.env_set>`                  Additional environment variables to be set.
   :ref:`env_unset <service.env_unset>`              Environment variables to be removed.
   :ref:`exit_kills <service.exit_kills>`            If 'true' the entire system should be shut down when this service stops.
                                                     Default is 'false'.
   :ref:`ignore_failures <service.ignore_failures>`  If 'true', failures of this service will be ignored but logged.
                                                     Dependent services are still allowed to start.
   :ref:`interval <service.interval>`                For `type=cron` services, specifies the crontab-compatible interval
                                                     in standard ``M H DOM MON DOW`` format. |ENV|
   :ref:`kill_signal <service.kill_signal>`          The signal used to kill this process.  Default is ``SIGTERM``.
   :ref:`optional <service.optional>`                If 'true', then if the command file is not present on the system,
                                                     the service will act as if it were not enabled.
   :ref:`pidfile <service.pidfile>`                  The full path to the file which will contain the process 'pid'
                                                     upon startup. ('forking' and 'simple' types only) |ENV|
   :ref:`process_timeout <service.process_timeout>`  Specifies the amount of time Chaperone will wait for a service to start.
                                                     The default varies for each type of service.
                                                     See :ref:`service types <service.sect.type>` for more
                                                     information.
   :ref:`restart <service.restart>`                  If 'true', then chaperone will restart this service if it fails (but
                                                     not if it terminates normally).  Default is 'false'.
   :ref:`restart_delay <service.restart_delay>`      The number of seconds to pause between restarts.  Default is 3 seconds.
   :ref:`restart_limit <service.restart_limit>`      The maximum number of restart attempts.  Default is 5.
   :ref:`service_groups <service.service_groups>`    A comma-separated list of service groups this service belongs to.  All
                                                     uppercase services are reserved by the system.
   :ref:`setpgrp <service.setpgrp>`                  If 'true', then the service will be isolated in its own process
                                                     group upon startup.  This is the default.
   :ref:`startup_pause <service.startup_pause>`      The amount of time Chaperone will wait to see if a service fails
                                                     immediately upon startup.  Defaults is 0.5 seconds.
   :ref:`uid <service.uid>`                          The uid (name or number) of the user for this service. |ENV|
   :ref:`gid <service.gid>`                          The gid (name or number) of the group for this service. |ENV|
   ================================================  =============================================================================

.. _service.sect.type:

Service Types
-------------

The ``type`` option defines how the service will be treated, when it is considered active, and what happens
when the service terminates either normally, or abnormally.

Valid service types are: *simple* (the default), *oneshot*, *forking*, *notify*, and *cron*.   These service types
are patterned loosely after service types defined by `systemd <http://www.freedesktop.org/software/systemd/man/systemd.service.html>`_,
but there are important differences [#f1]_ , so this section should be read carefully before making any assumptions.

As shown in :numref:`table.service-types`, each service type has a different behavior.   In the event the service's process reports
an error, it is either a *system failure* or *service failure*.  A system failure results in an immediate, orderly shutdown of
any services which have been started, along with logging an error report and termination of the system.  A service failure is
an isolated situation affecting only the service itself.

.. _table.service-types:

.. table::  Service Types

   ================  ==========================================================  ========================= =========================
   type              behavior                                                    system failure            service failure
   ================  ==========================================================  ========================= =========================
   simple            This is the default type.  Chaperone considers a service    Service terminates        Service terminates
                     "started" as soon as the startup grace period               abnormally during grace   abnormally later despite
                     (defined by :ref:`startup_pause <service.startup_pause>`)   period or pidfile not     retries.
                     elapses.							 found (if specified) 	   
                     If the service terminates normally at any time, the	 before process timeout. 
                     service is considered "started" until reset.
   forking           A forking service is expected to set up all                 Service terminates        Service terminates
                     communications channels and assure that the service         abnormally during the     abnormally later despite
                     is ready for application use, then exit normally            process timeout, or       retries (only if pidfile
                     before the                                                  the pidfile cannot be     specified).  Otherwise,
                     :ref:`process_timeout <service.process_timeout>`            found (if specified)      never. [#f2]_
                     expires.  *Note*: The default process timeout for           during the timeout
                     forking services is 300 seconds.                            period.
   oneshot           A oneshot service is designed to execute scripts which      Service terminates        Service terminates
                     complete an operation and are considered started once       abnormally during         abnormally during a
                     they run successfully.  *Note*: The default process         the process timeout.      manual "start"
                     timeout for oneshot services is 60 seconds.                                           operation.
   notify            A notify service is expected to establish communication     Service terminates        Service sends a
                     with chaperone using the *sd_notify* protcol.  The          abnormally during the     failure notification.
                     :ref:`NOTIFY_SOCKET <env.NOTIFY_SOCKET>`                    process timeout.
                     environment variable will be set, and chaperone will
                     consider the service started only when notified
                     appropriately. *Note*: The default process timeout
                     for a notify service is 30 seconds.
   inetd             The "inetd" type listens for TCP connections on the port    Service executable        Never.  Services
   		     specified by the 	      	      		                 is missing or invalid,    which fail are logged
		     :ref:`port <service.port>` parameter.  When a connection	 or TCP port is invalid	   but new connections
		     is received, chaperone will start a service connecting	 or already in use.	   will still be
		     `stdin`, `stdout` and `stderr` of the inbound socket				   accepted.
		     to the specified command.
   cron              The cron type schedules a script or program for periodic    Service executable        Never.  Failures of
                     execution.  The service is considered started once          is missing or invalid     isolated executions
                     successfully scheduled.  Both scheduling parameters         but not optional.         do not constitute
                     (specified using :ref:`interval <service.interval>`)                                  a permanent service
                     as well as the presence of the executable specified                                   failure.
                     in :ref:`command <service.command>` will be checked
                     before scheduling is considered successful.  Cron
                     services which are declared as
                     :ref:`optional <service.optional>` will not be
                     scheduled and will be treated as if they were disabled.
   ================  ==========================================================  ========================= =========================

Note: Unlike ``systemd``, Chaperone does not have an "idle" service type.  This is accomplished instead using a special
system-defined service group called "IDLE", thereby permitting any service type to be activated when startup is
complete.   See :ref:`service_groups <service.service_groups>` for more information.


Service Config Reference
------------------------

.. _service.type:

.. describe:: type: ( simple | forking | oneshot | notify | inetd | cron )

   The ``type`` option defines how the service will be treated, when it is considered active, and what happens
   when the service terminates either normally, or abnormally.  See the :ref:`separate section on service types <service.sect.type>` for
   a full description of what chaperone service types are and how they behave.

   This setting is optional.  If omitted, the default is "simple".

.. _service.command:

.. describe:: command: "executable args ..."

   The ``command`` option defines the command and arguments which will be executed when the service is started.  Both
   :ref:`environment variable expansion <env.expansion>` and "tilde" expansion for user names are supported, though
   "tilde" expansion is supported only on the command name itself, not on arguments.

   Note that the command line is *not* passed to a shell, so other shell meta-characters or shell environment variable
   syntax not supported.

   The first token on the command line must be an executable program available in the ``PATH``.  If it is not found,
   it will be considered an error.  However, if :ref:`optional <service.optional>`
   is set to 'true', then the service will be disabled in such cases.  This makes it easy to define configurations
   for programs which may or may not be installed.  *Note*: If the executable is present, but permissions deny
   access, it is considered an error regardless of whether the service is declared optional.

   In all cases, the environment that is used for ``PATH`` and expansions is the same environment that would be
   passed to the service.  If the executable is not available in the service's ``PATH`` then a fully qualified
   pathname should be used.

.. _service.enabled:

.. describe:: enabled: ( true | false )

   If enabled is 'true' (the default), then the service will start normally as per its type.  If it is
   set to 'false', then the service will be ignored upon start-up, and any dependencies will
   be considered satisfied.

   Services can be enabled and disabled dynamically while Chaperone is running using the
   :ref:`telchap command <ref.telchap>`.

   Since you can use environment variable expansions, it can be useful to make service startup conditional
   based upon some environment variable setting, such as::

     mysql.service: {
       type: simple,
       enabled: "$(ENABLE_MYSQL:+true)",
       ...
     }

.. _service.env_inherit:

.. describe:: env_inherit [ 'pattern', 'pattern', ... ]

Specifies a list of patterns which define what will be inherited from the environment defined by the
:ref:`global settings <config.settings>`  Patterns are standard filename "glob" patterns.
By default, all environment variables will be inherited from the settings environment.

For example::

  sample.service: {
    command: '/opt/app/bin/do_the_stuff',
    env_inherit: [ 'PATH', 'TERM', 'HOST', 'SSH_*' ],
  }

.. _service.env_set:

.. describe:: env_set { 'NAME': 'value', ... }

Provides a list of name/value pairs for setting or overriding environment variables.  The values may contain
:ref:`variable expansions <env.expansion>`.    The inherited environment will be the one configured
using similar settings directives such as :ref:`settings env_set <settings.env_set>`.

.. _service.env_unset:

.. describe:: env_unset [ 'pattern, 'pattern', ... ]

Removes the environment variables which match any of the given patterns from the environment.
Patterns are standard filename 'glob' patterns.

.. _service.stdout:

.. describe:: stdout: ( 'log' | 'inherit' )

   Can be set to 'log' to output service `stdout` to syslog (the default) or 'inherit' to output service messages
   directly to the container's stdout.   While it may be tempting to use 'inherit', we suggest you use the syslog
   service instead, then tailor :ref:`logging <logging>` entries accordingly if console output desired.
   This will provide much more flexibility.

   Messages from the process `stdout` will be logged as syslog facility and severity of `daemon.info`. [#f3]_

.. _service.stderr:

.. describe:: stderr: ( 'log' | 'inherit' )

   Can be set to 'log' to output service `stderr` to syslog (the default) or 'inherit' to output service messages
   directly to the container's stderr.   While it may be tempting to use 'inherit', we suggest you use the syslog
   service instead, then tailor :ref:`logging <logging>` entries accordingly if console output desired.
   This will provide much more flexibility.

   Messages from the process `stderr` will be logged as syslog facility and severity of `daemon.warn`. [#f3]_

.. _service.port:

.. describe:: port: tcp-port-number

   Specifies the TCP port number associated with an 'inetd' service, and must be specified when the
   type is 'inetd'.   When this service is started, Chaperone will bind to the specified TCP port and
   listen for incoming connections.  When a connection is received, Chaperone will start the service
   specified by the given :ref:`command <service.command>` parameter.

   The service will be started with `stdin`, `stdout`, and `stderr` connected to the started process.
   For example, the following script would initiate a simple "echo" service which would terminate
   when a blank line is sent::

     #!/usr/bin/python3
     import sys
     while True:
        result = input("echo:")
	if not result or result.strip() == "":
	   exit(0)
	print("echoed ->", result)
	sys.stdout.flush()

   Note the ``sys.stdout.flush()`` command.  Generally, such a command (or equivalent) will be necessary
   to assure that the program flushes it's output buffer.

   Commands can be simple informational services, or long-running servers.  If Chaperone receives multiple
   socket connections, it will start up as many processes as are needed to satisfy each request.  In other words,
   a single command invocation is responsible for a single client connection.

   If the script needs to do logging, it will need to do so via ``/dev/log``, or an equivalent syslog facility
   within the language, since `stderr` also is connected to the remote socket.

   There are many use-cases for creating simple port-triggerable services, especially in environments
   like Docker where containers contain only one or two processes, but auxilliary features may be
   desired without committing a long-running daemon to the task.

   For example, here is a blog post which
   describes `Service Monitoring with xinetd <http://www.softwareprojects.com/resources/programming/t-monitoring-services-with-xinetd-2082.html>`_.
   The same type of scripts work identically with Chaperone.

.. _service.after:

.. describe:: after: "service-or-group, ..."

   Specifies one or more services or service groups which must be started successfully before this service
   will start.

   The value specified is a comma-separated list of services or service groups.  Services are always
   identified with a ``.service`` suffix.  Otherwise, the reference is to a service group.  Thus::

     some.service: { after: "one.service, setup", command: "echo some" }

   defines a service which will start only after the service "one.service" and all services which
   are members of the "setup" group.

   For more information see :ref:`service_groups <service.service_groups>`.

.. _service.before:

.. describe:: before: "service-or-group, ..."

   Specifies one or more services or service groups which will not be started until this service starts
   successfully.

   The value specified is a comma-separated list of services or service groups.  Services are always
   identified with a ``.service`` suffix.  Otherwise, the reference is to a service group.  Thus::

     some.service: { before: "one.service, application", command: "echo some" }

   defines a service which will start before "one.service" and any services which
   are members of the "application" group.

   For more information see :ref:`service_groups <service.service_groups>`.

.. _service.directory:

.. describe:: directory: "directory-path"

   Specifies the start-up directory for this service.  If not provided, then the start-up directory is
   the home directory for the user under which the service will run.

.. _service.exit_kills:

.. describe:: exit_kills ( false | true )

   If set to 'true', then when this service terminates, Chaperone will initiate an orderly system shutdown.
   This is useful in cases where the lifetime of a controlling service, such as a shell or main application should
   dictate the lifetime of the container.

.. _service.ignore_failures:

.. describe:: ignore_failures ( false | true )

   If set to 'true', then any failure by the service will be logged but ignored.  Service failures are logged
   using syslog facility `local5.info` (`local5` is the facility used for all messages that originate from
   Chaperone itself.

.. _service.interval:

.. describe:: interval: "cron-interval-spec"

   This is required for service ``type=cron`` and contains the cron specification which indicates the interval
   for period execution.  Nearly all features documented in `this crontab man page <http://unixhelp.ed.ac.uk/CGI/man-cgi?crontab+5>`_
   are supported, including extensions for ranges and special keywords such as ``@hourly`` which can be specified
   with or without the leading ``@``.  So, a simple hourly cron service can be defined like this::

     cleanup_cookies.service: {
       type: cron,
       interval: hourly,
       command: "/opt/superapp/bin/clean_temp_cookies --silent",
     }

   which is equivalent to::

     cleanup_cookies.service: {
       type: cron,
       interval: "0 * * * *",
       command: "/opt/superapp/bin/clean_temp_cookies --silent",
     }

   Chaperone also supports an optional sixth field [#f4]_ for seconds so that seconds can be provided, so the following runs
   every 15 seconds::

     pingit.service: {
       type: cron,
       interval: "* * * * * * */15"
       command: "/opt/superapp/bin/ping_central_hub",
     }

   Note that the ``@reboot`` special nickname is not supported, since Chaperone provides similar features using
   the ``INIT`` service group.

.. _service.kill_signal:

.. describe:: kill_signal: ( name | number )

   Specifies the signal which is sent to the process for normal termination.  By default, Chaperone sends ``SIGTERM``.

.. _service.optional:

.. describe:: optional: ( false | true )

   If 'true', then this service is considered optional and will be disabled upon start-up if the executable is not
   found.   Only a "file not found" error triggers optional service behavior.  If the executable file exists,
   but permissions are incorrect, it is still considered a failure.

   Optional services may be started manually later if, for example, the executable should become available after
   system start-up.

.. _service.pidfile:

.. describe:: pidfile: file-path

   This setting specifies the "PID file" which the service will create upon startup to indicate it's controlling
   process ID.   This is valid only for 'simple', and 'forking' services.  The appearance of the pidfile is an
   indication that the service has been activated.

   When the ``pidfile`` directive exists:

   1. Chaperone start the service command normally.
   2. If the executable runs without error, Chaperone will watch for the appearance
      of the file specified in the ``pidfile`` directive.
   3. If the PID file does not appear within the timeframe given by the :ref:`process_timeout <service.process_timeout>`,
      then it is considered a failure.

   If the ``pidfile`` is seen, and contains a valid integer process ID *which denotes a running process*, then
   Chaperone will monitor the status of that process for failures to determine the disposition of the service.

   For 'simple' service types, it is possible (and likely) that the PID value will be the same as the PID of the
   originally running process, since 'simple' types are not expected to exit for the duration of their activity.

.. _service.process_timeout:

.. describe:: process_timeout: seconds

   When Chaperone is waiting for a service to start, it will wait for this number of seconds before it considers that
   the service has failed.   This value is meaningful for process types `oneshot`, `forking`, and `notify` only
   and is ignored for other types:

   For `oneshot` services:
      Chaperone assumes that a oneshot service is only started once it completes its task successfully, and
      therefore waits ``process_timeout`` seconds before allowing dependent services ot start.  For oneshot
      services the default process timeout is *60 seconds*.

   For `forking` services:
      Chaperone assumes a forking service does set-up, then proceeds to launch subprocesses to provide
      services.   The default process timeout for a forking service is *30 seconds*.

   For `notify` services:
      Since a notify service has an explicit means to tell chaperone about it's status, the process timeout
      defaults to *300 seconds* to provide the service with a greater amount of startup time.

.. _service.restart:

.. describe:: restart: ( false | true )

   By default, chaperone will not restart a service once it has failed.  Setting this to 'true' will tell chaperone
   to wait :ref:`restart_delay <service.restart_delay>` seconds after a failure, then restart the service until the
   :ref:`restart_limit <service.restart_limit>` is reached.   If all restarts fail, the chaperone considers
   the service to be failed.

   Note that restarts do *not* happen during system startup.  If a service fails during system startup, the
   failure is considered a system failure (unless :ref:`ignore_failures <service.ignore_failures>` is 'true')

.. _service.restart_delay:

.. describe:: restart_delay: seconds

   When a service fails and is about to be restarted, chaperone delays for this interval before attempting
   restart.   By default, this value is *0.5 seconds*.

   Consider increasing the restart delay for services which may fail because of network issues, since network
   issues may be transient (such as routers rebooting).

.. _service.restart_limit:

.. describe:: restart_limit: number-of-retries

   This value indicate the number of restarts which will be performed when a service fails.  Once the service
   starts successfully, the restart counter is reset.

.. _service.service_groups:

.. describe:: service_groups: "group[,group,...]"

   This directive declares that the service has membership in one or more service groups.  If not specified,
   all services have membership in the group "default".

   There are also two system-defined groups which have special meaning:

   ``INIT``
     This group will be started first, before any other service that is *not a member of the INIT group* itself.
     The order in which services will start within the INIT group is unspecified unless services make explicit
     :ref:`before <service.before>` or :ref:`after <service.after>` declarations.

   ``IDLE``
     This group will be started after all other services that are *not a member of the IDLE group* itself.
     The order in which services will start within the IDLE group is unspecified unless services make explicit
     :ref:`before <service.before>` or :ref:`after <service.after>` declarations.

   User-defined groups can be defined and used for any purpose, but must not have names which are all
   uppercase, as these are reserved for system groups.

   Group membership does *not* imply that the group will be started as a unit, or that the entire group
   will complete startup before other groups start.  For example, consider these service declarations::

     one.service:    { service_group: "setup", command: "echo one" }
     two.service:    { service_group: "setup", command: "echo two" }
     three.service:  { service_group: "sanity_checks", command: "echo three" }
     four.service:   { service_group: "sanity_checks", command: "echo four" }

   Chaperone does not consider members of the same group to be related in any way, and will start them
   randomly in parallel at start-up.  Assuring a sequence of start-up operations *must* be done using
   :ref:`before <service.before>` or :ref:`after <service.after>`, as follows::

     one.service:    { service_group: "setup", command: "echo one" }
     two.service:    { service_group: "setup", command: "echo two" }
     three.service:  { service_group: "sanity_checks", after: "setup" command: "echo three" }
     four.service:   { service_group: "sanity_checks", command: "echo four" }

   The "after" declaration assures that "three.service" will start only once all services in the "setup"
   group have successfully started.  *But*, "four.service" is still independent and can start at any time.

   So, for "four.service" there are two options.  By declaring "four.service" like this::

     four.service:   { service_group: "sanity_checks", after: "setup", command: "echo four" }

   it will also wait for all "setup" services, *but* it will start in parallel with "three.service",
   whereas the declaration::

     four.service:   { service_group: "sanity_checks", after: "three.service", command: "echo four" }

   achieves two goals: it assures the "four.service" starts after "three.service" but also assures
   all "setup" services will be completed, since "three.service" already expresses such a dependency.

   .. note::
      In all cases, references to a service group operate identically to explicit references to all
      group members.  Group references are merely a shortcut.  Therefore::

        four.service:   { service_group: "sanity_checks",
                          after: "setup",
                          command: "echo four" }

      is functionally identical to::

        four.service:   { service_group: "sanity_checks",
                          after: "one.service,two.service,three.service",
                          command: "echo four" }


.. _service.setpgrp:

.. describe:: setpgrp ( true | false )

   By default, chaperone makes each newly created service the parent of it's own process group.  This has the advantage
   of providing partial isolation for the service, and assures that if signals are sent to the group, no other processes
   are affected.  It also provides a poor man's method of tracking service groupings. [#f5]_

   While this is a reasonable default, some interactive processes (such as shells like ``/bin/bash``) should be executed with
   ``setpgrp: false``, since they use process groups extensively themselves and will want to set up process groups
   according to their job control strategy.


.. _service.startup_pause:

.. describe:: startup_pause seconds

   When Chaperone starts a service, it waits a short time to determine whether the service fails immediately.  This
   is the "startup_pause" and defaults to 0.5 seconds.

   Currently, Chaperone only uses this technique for ``type=simple`` and ``type=notify`` services, so
   it will have no impact on other service types.  Because "simple" services are considered started as soon as 
   process execution begins, the this short pause catches errors which occur within the first few moments of 
   process initialization (such as unexpected permission problems) rather than allowing dependent 
   services to start immediately.

.. _service.uid:

.. describe:: uid user-name-or-number

   Chaperone will run the service as the user specified by ``uid``.  If ``uid`` is not specified for the service,
   the :ref:`settings uid <settings.uid>` will be used, and finally the user specified on the command
   line with :option:`--user <chaperone --user>` or :option:`--create-user <chaperone --create-user>`.

   When Chaperone is told to use a particular user account, it also sets the ``HOME``, ``USER``, and
   ``LOGNAME`` environment variables to reflect those associated with the user.

   If none of the above are specified, the Chaperone runs the service normally under its own account
   without specifying a new user.

   Specifying a user requires root privileges.  Within containers like Docker, chaperone usually runs
   as root, so service configurations can specify alternate users even if they are run under a
   different user account.

   For example, if Chaperone were run from docker
   using the `chaperone-baseimage <https://hub.docker.com/r/chapdev/chaperone-baseimage/>`_ image like this::

     docker run -d chapdev/chaperone-baseimage \
                 --user wwwuser --config /home/wwwuser/chaperone.conf

   there is no reason that ``chaperone.conf`` could not contain the following service definitions::

     mysql.service: {
       uid: root, command: "/etc/init.d/mysql start"
     }
     myapp.service: {
       command: "~/bin/my_application"
     }

   In this case, "myapp.service" would run as user "wwwuser" becaues no ``uid`` was specified.  However
   because Docker runs chaperone as root, it is perfectly valid for the configuration file to tell
   Chaperone to run the "mysql" startup command as root.

.. _service.gid:

.. describe:: gid group-name-or-number

   When :ref:`uid <service.uid>` is specified (either explicitly or implicitly inherited), the ``gid``
   directive can be used to specify an alternate group to be used for execution.  If not specified,
   then the user's primary group will be used.

   As with :ref:`uid <service.uid>` specifying a group requires root priviliges.

.. rubric:: Notes

.. [#f1]

   Making chaperone's service types similar to ``systemd`` service types is a blessing and a curse.  The blessing is that ``systemd``
   is rapidly becoming the new standard for init daemons, so over time, there will be a good general knowledge of what various
   service types mean.  The downside is that chaperone is significantly simpler than ``systemd`` and there will be subtle
   (and probably to some, annoying) differences.  However, we took the risk of choosing a similar model, which we believe will
   benefit from the standardization of important process management techniques like
   `sd_notify <http://www.freedesktop.org/software/systemd/man/sd_notify.html>`_ as well as making it easier for those
   familiar with ``systemd`` to use their knowledge in defining chaperone configurations.

.. [#f2]

   Chaperone does not attempt "PID guessing" as ``systemd`` and some other process managers attempt to do.  The assumption
   is that "notify" will be the preferred means to determine if a service has started successfully, and to know what
   it's PID is in case of a crash or internal notification.

.. [#f3] Syslog facilities and severity levels are documented `on Wikipedia <https://en.wikipedia.org/wiki/Syslog>`_.

.. [#f4]

   Yes, the seconds field appears at the *end*.  This is inherited from the `croniter package <https://github.com/kiorky/croniter>`_
   which we use to parse and manage the internal cron intervals.  We considered not documenting it because it seems
   a bit non-standard, then figured... hey, could be useful.

.. [#f5]

   There is really only one bulletproof way to manage isolated groups of processes:
   `control groups (or cgroups) <https://en.wikipedia.org/wiki/Cgroups>`_.  Chaperone intentionally avoids using
   control groups for a number of reasons, but mostly because they require privileges which make containers
   less secure.  In addition, despite their power and utility, control groups are have become a contentious
   feature right now, being used extensively, and often in incompatible ways, by
   both `Docker <docker.com>`_  and `systemd <http://www.freedesktop.org/software/systemd/man/systemd.service.html>`_.  Chaperone
   is intended to be lean, simple and compatible with containers.  For now, avoiding cgroups we believe will
   keep Chaperone a more useful and simple accessory.
