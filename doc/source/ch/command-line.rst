.. chapereone documentation n
   command line documentation

Chaperone Command Reference
===========================

Command Quick Reference
-----------------------

Chaperone is usually executed as a container entrypoint and has the following syntax::

  chaperone [options] [initial-command [args...]]

The initial command is optional.  If provided, it will be run as an "IDLE" oneshot service, running after all
other services have been started.

Options are described in the table below, followed by more extensive reference information.

=============================================================  =================================================================================
command-line switch                	       		       function
=============================================================  =================================================================================
:ref:`--config=config-location <option.config>`                Specifies a file or directory where configuration information is found.
                                   	       		       Default is ``/etc/chaperone.d``.
:ref:`--debug <option.debug>`				       Turns debugging features.  (Implies ``--log-level=debug`` as well)
:ref:`--disable-services <option.disable-services>`	       No services will be started.  Only the command-line command will execute.
:ref:`--exitkills <option.exitkills>`			       When the command specified on the command line terminates, the chaperone
                                   	       		       will execute a normal shutdown operation.
:ref:`--no-exitkills <option.no-exitkills>`		       Reverses the effect of ``--exitkills``.  Useful when the ``--exitkills`` is
                                   	       		       implied or specified as a default.
:ref:`--force <option.force>`				       If chaperone refuses to do something, tell it to try anyway.
--help                             	       		       Displays command and option help.
:ref:`--ignore-failures <option.ignore-failures>`	       Run as if :ref:`ignore_failures <config.ignore_failures>` were true for all
                                   	       		       services.
:ref:`--log-level=level <option.log-level>`		       Force the syslog log output level to this value.  (one of 'emerg', 'alert', 'crit',
                                   	       		       'err', 'warn', 'notice', 'info', or 'debug).
:ref:`--no-defaults <option.no-defaults>`		       Ignore the :ref:`_CHAP_OPTIONS <env.CHAP_OPTIONS>` environment variable,
                                   	       		       if present.
:ref:`--user=username <option.user>`			       Run all processes as ``user`` (uid number or name).  The user must exist.
                                   	       		       By default, all processes run as ``root``.
:ref:`--create-user=newuser[/uid/gid] <option.create-user>`    Create a new user upon start-up with optional ``uid`` and ``gid``.  Then
                                   	       		       run as if ``--user=<user>`` was specified.
:ref:`--show-dependencies <option.show-dependencies>`	       Display service dependency graph, then exit.
:ref:`--task <option.task>`				       Run in "task mode".  This implies ``--log-level=err``, ``--disable-services``,
                                   	       		       and ``--exit-kills``.  This switch is useful when the container publishes
                                   	       		       commands which must run in isolation, such as displaying container internal
                                   	       		       information such as version information.
--version                          	       		       Displays the chaperone version number.
=============================================================  =================================================================================
                                                 
Option Reference Information
----------------------------

.. program:: chaperone

.. _option.config:

.. option:: --config <file-or-directory>

   Specifies the full or relative path to the Chaperone's configuration directory or configuration
   file.   For example, assume that ``chaperone.conf`` is a file and ``chaperone.d`` is the name
   of a directory::

     chaperone --config /home/wwwuser/chaperone.conf

   will tell Chaperone to read all configuration directives from the single self-contained
   configuration file specified.  No other directives will be read.  Or,::

     chaperone --config /home/wwwuser/chaperone.d

   specifies that the contents of the directory ``chaperone.d`` should be scanned and any file
   ending with ``.conf`` or ``.yaml`` will be read (in alphabetic order) to create the final
   configuration.   To understand how Chapeone handles directives which occur in multiple
   files, see :ref:`config.sect.files`.

   If not specified, defaults to ``/etc/chaperone.d``, or uses the default option set in
   the ``CHAP_OPTIONS`` (see :ref:`ch.env`) environment variable.

.. _option.debug:

.. option:: --debug

   Enables debugging features.   When debugging is enabled:

   * chaperone will print out a raw dump of all command line options (including those derived from defaults),
     as well as configuration information.
   * Internal debugging messages will be turned on, describing service start-up in more detail.
   * Traceback for internal errors will be enabled, making it easier to report bugs.
   * syslog logging will be forced to output all log levels (the same as using ``filter: '*.debug'`` in all
     logging entries.

.. _option.disable-services:

.. option:: --disable-services

   When set to 'true', then no services will be started or configured, though dependencies and configuration
   syntax will be checked normally.

   This switch can be useful in cases where services do not start correctly, or you want to enter a fresh
   container for inspection or other purposes.  For example::

     chaperone --disable-services /bin/bash

   will run ``bash`` alone as a child of chaperone, or in the case of using chaperone-enabled Docker images::

     docker run -t -i chapdev/chaperone-lamp --disable-services /bin/bash

   creates a fresh LAMP container running only ``bash`` so you can inspect the contents of the container without
   enabling any of the services.


.. _ch.env:

Environment Variables
---------------------

Chaperone uses environment variables in two ways:

1.  When the `chaperone` command first executes, environment variables are read and passed
    to the environment of any running services.  While this is the default, this can be
    changed using the :ref:`config.settings` section.
2.  Chaperone also sets "internal" environment variables which can be used within
    configuration files, but are not passed down to services.  Internal environment
    variables start with an underscore (`_`) character. 

Variables Used at Startup
*************************

.. _env.CHAP_OPTIONS:

.. envvar:: CHAP_OPTIONS

   When Chaperone starts, it reads options both from the command line and from this environment
   variable.  The environment variable provides defaults which should be used if they are 
   not present on the command line.

   For example, in the ``chaperone-baseimage`` image configuration, the default value
   for ``--config`` is set::

	    ENV CHAP_OPTIONS --config apps/chaperone.d
	    ENTRYPOINT ["/usr/local/bin/chaperone"]

Internal Variables
******************

As described above, internal variables are available for use within configuration directives such as
:ref:`config.env_set`, but are not automatically passed down to services.  If you want to make these
available to services, simply define an environment variable which expands to one of the internal variables::

  settings: {
    env_set: {
      # Make the relevant service name available to all processes
      'SERVICE_NAME': '$(_CHAP_SERVICE)',
    }
  }

.. envvar:: _CHAP_CONFIG_DIR

   This is the path to the directory which *contains* the target specified by 
   the :option:`--config <chaperone --config>` option.

   For example, if you start Chaperone with the following command::

     chaperone --config /home/appsuser/firstapp/chaperone.conf

   then this environment variable will be set to ``/home/appsuser/firstapp``.  Note that
   the method is the same *even if a configuration directory is specified*.  Thus, this
   command::

     chaperone --config /home/appsuser/firstapp/chaperone.d

   would set ``_CHAP_CONFIG_DIR`` to exactly the same value even though the target
   is a directory rather than a file.

   One very useful application of this variable is to define "self-relative" execution
   environments where all application files are stored relative to the location of the
   configuration directory.  The ``chaperone-baseimage`` does this with the following
   declaration::

     settings: {
       env_set: {
         'APPS_DIR': '$(_CHAP_CONFIG_DIR:-/)',
       }
     }

   Then, all other files, commands and configurations operate relative to the ``APPS_DIR``
   environment variable.   If this principle is observed carefully you can easily run::

     docker run --config /myapps/prerelease/chaperone.d

   to run an isolated set of applications stored in ``/myapps/prerelease`` and another
   set of isolated applications in the same image like this::

     docker run --config /myapps/stable/chaperone.d


     
