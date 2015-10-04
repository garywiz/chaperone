.. chaperone documentation
   configuration directives

.. include:: /includes/defs.rst

.. _config.settings:

Configuration: Global Settings
==============================

Settings Quick Reference
------------------------

Global settings are identified by a configuration file section titled settings, for example::

  settings: {
    ignore_failures: true,
    env_set: {
      'LANG': 'en_US.UTF-8',
      'LC_CTYPE': '$(LANG)',
      'PATH': '$(APPS_DIR)/bin:/usr/local/bin:/bin:/usr/bin:/sbin:/usr/sbin:/usr/local/sbin',
    },
  }

Directives applied in the setting section apply globally and some define defaults to be inherited by
logging or service declarations.

Entries below marked with |ENV| support :ref:`environment variable expansion <env.expansion>`.

.. _table.settings-quick:

.. table:: Global Settings Quick Reference

   =================================================== =============================================================================
   settings variable                                   meaning
   =================================================== =============================================================================
   :ref:`env_inherit <settings.env_inherit>`           An array of patterns which can match one or more
						       environment variables.  Environment variables which
						       do not match any pattern will be excluded.  Default is ``['*']``.
   :ref:`env_set <settings.env_set>`                   Additional environment variables to be set.
   :ref:`env_unset <settings.env_unset>`               Environment variables to be removed.
   :ref:`idle_delay <settings.idle_delay>`             The "grace period" after all services have started before
						       services in the "IDLE" group will begin running.  Default is 1.0 seconds.
   :ref:`ignore_failures <settings.ignore_failures>`   Specifies the ``ignore_failures`` default for services.
   :ref:`process_timeout <settings.process_timeout>`   Specifies the amount of time Chaperone will wait for a service to start.
						       The default varies for each type of service.
						       See :ref:`service process_timeout <service.process_timeout>` for more
						       information.
   :ref:`shutdown_timeout <settings.shutdown_timeout>` The amount of time Chaperone will wait for services to complete shutdown
						       before forcing a kill with SIGKILL.  Default is 8 seconds.
   :ref:`startup_pause <settings.startup_pause>`       Specifies the ``startup_pause`` default for services.
   :ref:`detect_exit <settings.detect_exit>`           If true (the default), then Chaperone tries to intelligently detect
   		     				       when all processes have exit and none are schedule, then terminates.
   :ref:`uid <settings.uid>`                           The default uid (name or number) for all services and logging tasks.
						       Overrides the value specified by :ref:`--user <option.user>` or
						       :ref:`--create-user <option.create-user>`. |ENV|
   :ref:`gid <settings.gid>`                           The default gid (name or number) for all services and logging tasks.
   	     					       |ENV|
   =================================================== =============================================================================

Settings Reference
------------------

.. _settings.env_inherit:

.. describe:: env_inherit [ 'pattern', 'pattern', ... ]

Specifies a list of patterns which define what will be inherited from the environment passed to Chaperone when it
was executed.  Patterns are standard filename "glob" patterns.   By default, all environment variables will be
inherited.

For example::

  settings: {
    env_inherit: [ 'PATH', 'TERM', 'HOST', 'SSH_*' ],
  }

.. _settings.env_set:

.. describe:: env_set { 'NAME': 'value', ... }

Provides a list of name/value pairs for setting or overriding environment variables.  The values may contain
:ref:`variable expansions <env.expansion>`.  Note that variables are not expanded immediately, so you can
refer to variables which may be defined later in services.  For example::

  settings: {
    env_set: {
      'SHELL': '/bin/ksh',
      'PATH': '/services/$(_CHAP_SERVICE)/bin:$(PATH)'
      }
    }

In the above, while the value of ``SHELL`` is known, the value of ``_CHAP_SERVICE`` will not be valid
until a service executes.   However, because variables use "late expansion", you can define variables
such as the above as templates so that they will be available to all services.

.. _settings.env_unset:

.. describe:: env_unset [ 'pattern, 'pattern', ... ]

Removes the environment variables which match any of the given patterns from the environment.  These variables
will not be passed down to services or logging directives.  Patterns are standard filename 'glob' patterns.

.. _settings.idle_delay:

.. describe:: idle_delay seconds

Specifies the number of seconds Chaperone will pause before tasks in the :ref:`IDLE service group <service.service_groups>`
will be started.  May contain fractional values such as "0.1".  Defaults to 1 second.

This delay is useful in at least two common situations:

1. When service startup may cause log messages to appear at the console,
   the console program (usually a shell) may have its prompt interleaved with console messages.
   This delay decreases the likelihood of this happening.

2. When services of type :ref:`simple <service.sect.type>` are used, there is no real way to determine
   if services have fully started.  However, the idle delay does nothing except add a "fudge factor",
   which, while useful, would be better implemented using proper 'notify', or 'forking' services.


.. _settings.ignore_failures:

.. describe:: ignore_failures ( false | true )

   If set to 'true', then any the default for the service's :ref:`ignore_failures <service.ignore_failures>` will be
   'true' rather than the normal 'false' default.   Any setting by a service overrides this value.

   Primarily, this is useful for debugging and has similar utility as the command-line switch
   :ref:`--ignore-failures <option.ignore-failures>` since it allows you to bypass normal system failure
   checks and allow services to start even though dependencies may have failed.

.. _settings.process_timeout:

.. describe:: process_timeout: seconds

   This allows you to set the global default for service :ref:`process_timeout <service.process_timeout>`.
   Normally the process timeout value is determined by the :ref:`service type <service.sect.type>`.  Setting
   this value globally will cause *all* processes to use the same process timeout as their defaults.

   If a service specifies its own value, it will always take precedence over this default.

.. _settings.shutdown_timeout:

.. describe:: shutdown_timeout

   When Chaperone receives a shutdown request (usually ``SIGTERM``), it goes through an orderly shutdown,
   telling each service to stop.  If there are still services running after the shutdown timeout, 
   Chaperone will force all processes to quit using ``SIGKILL``.  The default for this value is
   10 seconds.

.. _settings.startup_pause:

.. describe:: startup_pause

   This allows you to set the global default for the service :ref:`startup_pause <service.startup_pause>` value.
   If not specified, the service default will be used.

   If a service specifies its own value, it will always take precedence over this default.

.. _settings.detect_exit:

.. describe:: detect_exit

   When 'true' (the default), then Chaperone intelligently watches the process environment to determine
   whether it should automatically exit.   Chaperone will exit when:

   * All processes have exited, and ...
   * There are no pending ``inetd`` or ``cron`` services which are configured and active.

   Generally, this behavior is desirable, but there are situations where disabling this can be useful.
   For example, if a container contains a set of dormant (disabled) services, and they are manually
   enabled or disabled during runtime, setting this to 'false' will cause Chaperone to remain running
   even if there are no active services and all work has completed.

   If set to 'false', then Chaperone will only exit whenever it is explicitly killed with ``SIGTERM``,
   or when a service exits whose :ref:`exit_kills <service.exit_kills>` configuration value is set to 'true'.

.. _settings.uid:

.. describe:: uid user-name-or-number

   This sets the default user account which will be used by services and logging directives.
   If the ``uid`` setting is not specified, the default will the user specified on the command
   line with :option:`--user <chaperone --user>` or :option:`--create-user <chaperone --create-user>`.

   If none of the above are specified, the Chaperone runs the service normally under its own account
   without specifying a new user.

   Services and logging are affected differently by user credentials:

   * See :ref:`service uid <service.uid>`, or ...
   * :ref:`logging uid <logging.uid>` for more details.

.. _settings.gid:

.. describe:: gid group-name-or-number

   When :ref:`uid <settings.uid>` is specified (either explicitly or implicitly inherited), the ``gid``
   directive can be used to specify an alternate group to be used for logging or services.  
