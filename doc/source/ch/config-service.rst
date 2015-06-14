.. chapereone documentation
   configuration directives

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

Multiple services can be declared in a single file.  Order within a configuration file is not important,
however, if several configuration files are involved, services in subsequent files (alphabetically) will
replace earlier services defined with the same name.

Each service starts with the environment defined by the :ref:``settings directive <config.settings>`` and
can be tailored separately for each service.

================================================  =============================================================================
service variable                                  meaning
================================================  =============================================================================
:ref:`type <service.type>`                        Defines the service type: 'oneshot', 'simple', forking', 'notify',
                                                  or 'cron'.  Default is 'simple'.
:ref:`command <service.command>`                  Specifies the command to execute.  The command is not processed by a shell,
                                                  but environment variable expansion is supported.
                                                  (See :ref:``config.environment_expansion``)
:ref:`enabled <service.enabled>`                  If 'false', the service will not be started, nor will it be required by
                                                  any dependents.  Default is 'true'.
:ref:`stderr <service.stderr>`                    Either 'log' to write stderr to the syslog, or 'inherit' to write stderr
                                                  to the container's stderr file handle.   Default is 'log'.
:ref:`stdout <service.stdout>`                    Either 'log' to write stdout to the syslog, or 'inherit' to write stdout
                                                  to the container's stdout file handle.   Default is 'log'.

:ref:`after <service.after>`                      A comma-separated list of services or service groups which cannot start
                                                  until after this service has started.
:ref:`before <service.before>`                    A comma-separated list of services or service groups which must start
                                                  before this service.
:ref:`directory <service.directory>`              The directory where the command will be executed.  Otherwise, the account
                                                  home directory will be used.
:ref:`exit_kills <service.exit_kills>`            If 'true' the entire system should be shut down when this service stops.
                                                  Default is 'false'.
:ref:`ignore_failures <service.ignore_failures>`  If 'true', failures of this service will be ignored but logged.
                                                  Dependent services are still allowed to start.
:ref:`interval <service.interval>`                For `type=cron` services, specifies the crontab-compatible interval
                                                  in standard ``M H DOM MON DOW`` format.
:ref:`kill_signal <service.kill_signal>`          The signal used to kill this process.  Default is ``SIGTERM``.
:ref:`optional <service.optional>`                If 'true', then if the command file is not present on the system,
                                                  the service will act as if it were not enabled.
:ref:`process_timeout <service.process_timeout>`  Specifies the amount of time Chaperone will wait for a service to start.
                                                  The default varies for each type of service.
                                                  See :ref:``service types <config.sect.service_types>`` for more
                                                  information.
:ref:`restart <service.restart>`                  If 'true', then chaperone will restart this service if it fails (but
                                                  not if it terminates normally).  Default is 'false'.
:ref:`restart_delay <service.restart_delay>`      The number of seconds to pause between restarts.  Default is 3 seconds.
:ref:`restart_limit <service.restart_limit>`      The maximum number of restart attempts.  Default is 5.
:ref:`service_groups <service.service_groups>`    A comma-separatedlist of service groups this service belongs to.  All
                                                  uppercase services are reserved by the system.
:ref:`setpgrp <service.setpgrp>`                  If 'true', then the service will be isolated in its own process
                                                  group upon startup.  This is the default.
:ref:`startup_pause <service.startup_pause>`      The amount of time Chaperone will wait to see if a service fails
                                                  immediately upon startup.  Defaults is 0.5 seconds.
:ref:`uid <service.uid>`                          The uid (name or number) of the user for this service.
:ref:`gid <service.gid>`                          The gid (name or number) of the group for this service.
================================================  =============================================================================

.. _service.type:

Service Types
-------------

The ``type`` option defines how the service will be treated, when it is considered active, and what happens
when the service terminates either normally, or abnormally.

Valid service types are: *simple* (the default), *oneshot*, *forking*, *notify*, and *cron*.   These service types
are patterned loosely after service types defined by `systemd <http://www.freedesktop.org/software/systemd/man/systemd.service.html>`_,
but there are important differences [#f1]_ , so this section should be read carefully before making any assumptions.

Here is a summary of the behavior of different types:

================  ==========================================================  ========================= =========================
type              behavior                                                    system failure            service failure
================  ==========================================================  ========================= =========================
simple            This is the default type.  Chaperone considers a service    Service terminates        Service terminates
		  "started" as soon as the startup grace period               abnormally during grace   abnormally later despite
		  (defined by :ref:`startup_pause <service.startup_pause>`)   period.                   retries.
		  elapses.                                                 
		  If the service terminates normally at any time, the      
		  service is considered "started" until reset.	      
forking           A forking service is expected to set up all	              Service terminates	Never. [#f2]_
		  communications channels and assure that the service         abnormally during the
		  is ready for application use, then exit normally            process timeout.
		  before the
		  :ref:`process_timeout <service.process_timeout>`
		  expires.  *Note*: The default process timeout for
		  forking services is 30 seconds.
oneshot           A oneshot service is designed to execute scripts which      Service terminates        Service terminates
		  complete an operation and are considered started once       abnormally during         abnormally during a
		  they run successfully.  *Note*: The default process         the process timeout.      manual "start"
		  timeout for oneshot services is 60 seconds.                                           operation.
notify            A notify service is expected to establish communication     Service terminates	Service sends a
		  with chaperone using the *sd_notify* protcol.  The	      abnormally during the     failure notification.
		  :ref:`NOTIFY_SOCKET <env.NOTIFY_SOCKET>`	    	      process timeout
		  environment variable will be set, and chaperone will
		  consider the service started only when notified
		  appropriately. *Note*: The default process timeout
		  for a notify service is 30 seconds.
cron              The cron type schedules a script or program for periodic    Service executable	Never.  Failures of
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

"considered started"
"system failure"
"service faiure"
"sd_notify protocol"
"idle service"


Service Config Reference
------------------------

.. describe:: type: ( simple | forking | oneshot | notify | cron )

   The ``type`` option defines how the service will be treated, when it is considered active, and what happens
   when the service terminates either normally, or abnormally.  See the :ref:`separate section on service types <service.type>` for
   a full description of what chaperone service types are and how they behave.

   This setting is optional.  If omitted, the default is "simple".

.. _service.command:

.. describe:: command: "executable args ..."

   The ``command`` option defines the command and arguments which will be executed when the service is started.  Both
   :ref:`environment variable expansion <env.expansion>` and "tilde" expansion for user names are supported, though
   "tilde" expansion is supported only on the command name itself, not on arguments.

   Note that the command line is *not* passed to a shell, so other shell metacharacters or shell environment variable
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
   :ref:`telchap command <telchap>`.

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

.. _service.after:

.. describe:: after: "service-or-group, ..."

   Specifies one or more services or service groups which will not be started until this service starts
   successfully.  For more information XXX.

.. _service.before:

.. describe:: before: "service-or-group, ..."

   Specifies one or more services or service groups which must be started sucessfully before this service
   will start.  For more information XXX.

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

.. _service.process_timeout:

.. describe:: process_timeout: seconds

   When Chaperone is waiting for a service to start, it will wait for this number of seconds before it considers that
   the service has failed.   This value is meaningful for process types `oneshot`, `forking`, and `notify` only
   and is ignored for other types:

   for `forking` services:
      this happens

   for `oneshot` services:
      that happens

   for `notify` services:
      these happen

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
   it's PID is in case of a crash or internal notification.  However, it's likely that a future version of chaperone
   will introduce a "pid_file" directive to allow forking services a way to provide information about their 
   controlling PID.

.. [#f3] Syslog facilities and severity levels are documented `on Wikipedia <https://en.wikipedia.org/wiki/Syslog>`_.

.. [#f4] 

   Yes, the seconds field appears at the *end*.  This is inherited from the `croniter package <https://github.com/kiorky/croniter>`_
   which we use to parse and manage the internal cron intervals.  We considered not documenting it because it seems
   a bit non-standard, then figured... hey, could be useful.
