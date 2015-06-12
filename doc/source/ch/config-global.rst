.. chapereone documentation
   configuration directives

.. _config.settings:

Configuration: Global Settings
==================================


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

=================  =============================================================================
settings variable  meaning
=================  =============================================================================
env_inherit        An array of patterns which can match one or more
		   environment variables.  Environment variables which
		   do not match any pattern will be excluded.  Default is ``['*']``.
env_set            Additional environment variables to be set.
env_unset          Environment variables to be removed.
idle_delay         The "grace period" after all services have started before
		   services in the "IDLE" group will begin running.  Default is 1.0 seconds.
ignore_failures    Specifies the ``ignore_failures`` default for services.
process_timeout    Specifies the amount of time Chaperone will wait for a service to start.
		   The default varies for each type of service.
		   See :ref:``service types <config.sect.service_types>`` for more
		   information.
startup_pause      Specifies the ``startup_pause`` default for services.
uid                The default uid (name or number) for all services and logging tasks.
		   Overrides the value specified by :option:``--user <chaperone --user>`` or
		   ``--create-user <chaperone --create-user>``.
gid                The default gid (name or number) for all services and logging tasks.
=================  =============================================================================
