.. chapereone documentation
   configuration directives

Configuration: Service Declarations
===================================

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

=================  =============================================================================
service variable   meaning
=================  =============================================================================
type               Defines the service type: 'oneshot', 'simple', forking', 'notify',
		   or 'cron'.  Default is 'simple'.
command		   Specifies the command to execute.  The command is not processed by a shell,
		   but environment variable expansion is supported.
		   (See :ref:``config.environment_expansion``)
enabled		   If 'false', the service will not be started, nor will it be required by
		   any dependents.  Default is 'true'.
stderr		   Either 'log' to write stderr to the syslog, or 'inherit' to write stderr
		   to the container's stderr file handle.   Default is 'log'.
stdout		   Either 'log' to write stdout to the syslog, or 'inherit' to write stdout
		   to the container's stdout file handle.   Default is 'log'.

after		   A comma-separated list of services or service groups which cannot start
		   until after this service has started.
before		   A comma-separated list of services or service groups which must start
		   before this service.
directory	   The directory where the command will be executed.  Otherwise, the account
		   home directory will be used.
exit_kills	   If 'true' the entire system should be shut down when this service stops.
		   Default is 'false'.
ignore_failures	   If 'true', failures of this service will be ignored but logged. 
		   Dependent services are still allowed to start.
interval	   For `type=cron` services, specifies the crontab-compatible interval
		   in standard ``M H DOM MON DOW`` format.
kill_signal	   The signal used to kill this process.  Default is ``SIGTERM``.
optional	   If 'true', then if the command file is not present on the system,
		   the service will act as if it were not enabled.
process_timeout    Specifies the amount of time Chaperone will wait for a service to start.
		   The default varies for each type of service.
		   See :ref:``service types <config.sect.service_types>`` for more
		   information.
restart		   If 'true', then chaperone will restart this service if it fails (but
		   not if it terminates normally).  Default is 'false'.
restart_delay	   The number of seconds to pause between restarts.  Default is 3 seconds.
restart_limit	   The maximum number of restart attempts.  Default is 5.
service_groups	   A comma-separatedlist of service groups this service belongs to.  All
		   uppercase services are reserved by the system.
setpgrp		   If 'true', then the service will be isolated in its own process
		   group upon startup.  This is the default.
startup_pause      The amount of time Chaperone will wait to see if a service fails
		   immediately upon startup.  Defaults is 0.5 seconds.
uid		   The uid (name or number) of the user for this service.
gid		   The gid (name or number) of the group for this service.
=================  =============================================================================
