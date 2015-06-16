.. chapereone documentation
   configuration directives

.. |ENV| replace:: :kbd:`$ENV`

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

Directives applied in the setting section apply globally and may be inherited by
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
						       before forcing a kill with SIGKILL.  Default is 10 seconds.
   :ref:`startup_pause <settings.startup_pause>`       Specifies the ``startup_pause`` default for services.
   :ref:`uid <settings.uid>`                           The default uid (name or number) for all services and logging tasks.
						       Overrides the value specified by :ref:`--user <option.user>` or
						       :ref:`--create-user <option.create-user>`. |ENV|
   :ref:`gid <settings.gid>`                           The default gid (name or number) for all services and logging tasks.
   	     					       |ENV|
   =================================================== =============================================================================
