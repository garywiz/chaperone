.. chaperone documentation n
   command line documentation

.. _ref.chaperone:

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
:ref:`--ignore-failures <option.ignore-failures>`	       Run as if :ref:`ignore_failures <service.ignore_failures>` were true for all
                                   	       		       services.
:ref:`--log-level=level <option.log-level>`		       Force the syslog log output level to this value.  (one of 'emerg', 'alert', 'crit',
                                   	       		       'err', 'warn', 'notice', 'info', or 'debug).
:ref:`--no-console-log <option.no-console-log>`                Forces 'stderr' and 'stdout' to *false* for all logging services.
:ref:`--no-defaults <option.no-defaults>`		       Ignore the :ref:`_CHAP_OPTIONS <env._CHAP_OPTIONS>` environment variable,
                                   	       		       if present.
:ref:`--user=username <option.user>`			       Run all processes as ``user`` (uid number or name).  The user must exist.
                                   	       		       By default, all processes run as ``root``.
:ref:`--create-user=newuser[:uid:gid] <option.create-user>`    Create a new user upon start-up with optional ``uid`` and ``gid``.  Then
                                   	       		       run as if ``--user=<user>`` was specified.
:ref:`--default-home=directory <option.default-home>`          If :ref:`--create-user <option.create-user>` specifies a user whose
			       				       home directory does not exist, then create the new user account with this
							       directory as the user's home directory.
:ref:`--show-dependencies <option.show-dependencies>`	       Display service dependency graph, then exit.
:ref:`--task <option.task>`				       Run in "task mode".  This implies ``--log-level=err``, ``--disable-services``,
                                   	       		       and ``--exitkills``.  This switch is useful when the container publishes
                                   	       		       commands which must run in isolation, such as displaying container internal
                                   	       		       information such as version information.
--version                          	       		       Displays the chaperone version number.
=============================================================  =================================================================================
                                                 
Chaperone Command Execution
---------------------------

Chaperone goes through a set of startup phases in order to establish a working environment.

1.  Chaperone first examines the environment looking for the :ref:`_CHAP_OPTIONS <env._CHAP_OPTIONS>` variable.
    If found, Chaperone uses it to establish default values.  The remaining environment variables will be passed to
    running services depending upon the both global and per-service settings.

2.  Command line options are read and combined with any default options to form the final command option set.
    Configuration information is optional, and if no configuration is found, it is not considered an error.

3.  Once configuration information is present, chaperone proceeds to start it's internal ``syslog`` service,
    creating sockets such as ``/dev/log`` and starts it's internal command processor which accepts
    commands at ``/dev/chaperone`` or interactive commands (via :ref:`telchap <ref.telchap>`) at
    ``/dev/chaperone.sock``.  Chaperone also sets up utility environment variables such as
    :ref:`_CHAP_INTERACTIVE <env._CHAP_INTERACTIVE>` so that they can be used in service configurations.

4.  If a command and arguments are provided on the command line, an "IDLE" oneshot service is configured
    so that it runs after all other services are started.  If chaperone is running interactively,
    :option:`--exitkills <chaperone --exitkills>` is implied, otherwise, termination of this service
    will leave the system running just as if any other oneshot service exited normally.

5.  Services in the "INIT" service group (if any) are executed and must start successfully before other services
    are started.

6.  All other services are started in dependency order.  Failures during startup comprise a system
    failure unless :option:`--ignore-failures <chaperone --ignore-failures>` is used on the command line, or
    the service is declared with :ref:`ignore_failures <service.ignore_failures>` set to "true".

7.  Services in the "IDLE" service group (if any) are executed (which includes any command specified on the
    command line).

Once started, Chaperone monitors all services, performs logging, and cleans up zombie processes when
they exit.   When it receives a ``SIGTERM`` it will shutdown all processes in an orderly fashion.


Note that when a command is specified on the chaperone command line, chaperone starts a ``CONSOLE`` service internally.
This service can be managed just like any other service, and shows up in service listings when using the :ref:`telchap <ref.telchap>`
command.   If chaperone is started in an interactive environment (has a pseudo-tty as ``stdin``), it uses
``SIGHUP`` to terminate the process. Otherwise, it uses ``SIGTERM`` as usual.   This is to accommodate login
shells such ``bash`` and ``sh``, which expect this behavior.


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
   configuration.   To understand how Chaperone handles directives which occur in multiple
   files, see :ref:`config.file-format`.

   If not specified, defaults to ``/etc/chaperone.d``, or uses the default option set in
   the ``_CHAP_OPTIONS`` (see :ref:`ch.env`) environment variable.

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

.. _option.exitkills:

.. option:: --exitkills

   This option works in conjunction with an ``initial-command`` specified on the command line, and will cause
   the entire container to shut down when the command completes.

   Chaperone attempts to anticipate what is needed automatically, and if run in an interactive container,
   will default to ``--exitkills`` or when run as a daemon defaults to ``--no-exitkills``.  For example,
   the following docker command will cause an exit after ``bash`` completes::

     docker run -t -i --rm=true chapdev/chaperone-baseimage /bin/bash

   whereas the following command will not exit upon bash's completion::

     docker run -d chapdev/chaperone-baseimage /bin/bash

   Both this option as well as :ref:`--no-exitkills <option.no-exitkills>` are provided when Chaperone's
   default behavior is not desired.

.. _option.no-exitkills:

.. option:: --no-exitkills

   Will not shutdown the system when the ``initial-command`` exits.  See :ref:`--exitkills <option.exitkills>`.

.. _option.force:

.. option:: --force

   This option can be used to force Chaperone to attempt an operation even though it typically
   would refuse.  At present, there are not many situations where this command is useful, but that may
   change.  In cases where it can be used, Chaperone will display an alert, for example::

     wheezy:~$ chaperone
     Normally, chaperone expects to run as PID 1 in the 'init' role.
     If you want to go ahead anyway, use --force.
     wheezy:~$

.. _option.ignore-failures:

.. option:: --ignore-failures

   Running with this option causes Chaperone to run as if the global setting :ref:`ignore_failures <settings.ignore_failures>` were
   set to "true".

   This can be useful when a service is failing on startup and causes sytem failure (as described in the :ref:`table.service-types` table).
   In such situations, troubleshooting can be difficult since the container may be transient and failure information may be lost.

   For example, to run a shell in a container even if it is failing on startup::

     docker run -t -i --rm=true chapdev/chaperone-lamp --ignore-failures /bin/bash

 
.. _option.log-level:

.. option:: --log-level level-name

   Normally, Chaperone should be configured to do logging with :ref:`logging directives <logging>`.  However, at times, more
   detail is needed in the logs for troubleshooting purposes.  

   This option should be followed by one of the log levels: **emerg**, **alert**, **crit**, **err**, **warn**, **notice**,
   **info**, or **debug**.  When specified, it forces the logging system to behave as if *all* log definitions have a minimum
   severity of ``level-name``.

   For example, ``--log-level info`` assures that all types messages except debugging messages will be displayed in all logs;
   ``--log-level debug`` assures that all types of messages are displayed.

   Note that logging still must be configured so that syslog messages have some destination.  By default, log messages
   are captured but not directed to 'stdout' or a file.  Most configurations include at least a simple logging directive like this::

     console.logging: {
       selector: '*.warn',
       stdout: true,
     }

   which tells Chaperone to direct any messages of warning level or greater severity to 'stdout'.  Including ``--log-level info``,
   for example, would cause Chaperone to behave as if the declaration looked like this::

     console.logging: {
       selector: '*.info',
       stdout: true,
     }

   Note also that using the :ref:`--debug <option.debug>` switch automatically sets the log level to 'debug', so use of this
   switch in such cases is redundant.

.. _option.no-console-log:

.. option:: --no-console-log

   This switch unsets any :ref:`stdout <logging.stdout>` and :ref:`stderr <logging.stderr>` logging directives, thus disabling
   any logging to the console.

   Disabling console output can be useful in special-case situations, such as when a command-line command wishes to dump
   container internals to ``stdout`` in some format (such as ``gzip``) which may be corrupted if inadvertent console
   messages are produced.

.. _option.no-defaults:

.. option:: --no-defaults

   Using this switch causes Chaperone to ignore any configuration defaults set in the :ref:`_CHAP_OPTIONS <env._CHAP_OPTIONS>`
   environment variable.  Only the options provided on the command line itself will be recognized when this switch is used.

.. _option.user:

.. option:: --user name-or-number

   Normally, when Chaperone is started, it runs as the same user which executed the ``chaperone`` command (usually ``root``).
   However, in many cases, it is desirable to have Chaperone spawn all services and use permissions of a different user. 
   This switch specifies the user account under which Chaperone will start all processes and logging services.  For example, 
   assume you have an account within a container called ``appuser`` and all services should run under that user account.
   You would simply do this::

     docker run -d my_chaperone_image --user appuser

   Chaperone will automatically assure that ``HOME``, ``LOGIN`` and ``LOGNAME`` are set correctly so that the
   application make sure all files are located relative to the application home directory.

   Typically, a production container would be built with this switch incorporated into the built image itself.
   (Such as using Docker's ``CMD`` or ``ENTRYPOINT`` directives in a `Dockerfile <https://docs.docker.com/reference/builder/>`_.

   Note the user *must exist* already inside the container's configuration.  If not, you can 
   use :ref:`--create-user <option.create-user>` to dynamically create a new user inside the container upon startup.

.. _option.create-user:

.. option:: --create-user name[:uid[:gid]] or --create-user name:/path/to/file[:uid[:gid]]

   Often, a generic container can be designed to allow userspace mount points, isolating persistent data
   outside the container so that the container becomes entirely transient.   Because containers have a
   set of isolated user credentials, sharing files and permissions with the host volumes can often
   lead to difficulties.

   The ``--create-user`` switch allows you to "match" the host user (and optionally group) to the running
   process tree within the container so that file permissions are consistent.  

   This switch accepts the following:

   * A ``name`` parameter which should be the name of a user that will be created the first time
     the container runs.
   * An optional ``uid`` which must be the numeric user ID of the user to be created.  If omitted,
     a new user ID will be assigned.
   * An optional ``gid`` which can be the name or number of an existing group, or the number
     of a new group to be created specifically for the new user.
   * An optional format where the name is followed by the path to an *existing* file on the system
     whose ``uid`` and ``gid`` will be used to create the new user.

   The final alternative form is specified by including the path as follows::

     --create-user name:/path/to/file

   When ``uid`` and ``gid`` or the file option are omitted, Chaperone will use the container's installed OS policy
   to determine how to assign user credentials.

   This feature can be used to create generic start-up scripts for containers so that they
   share the credentials of whatever user created them.  Here is an example::

     #!/bin/bash
     # Extract host user UID/GID
     myuid=`id -u`
     mygid=`id -g`
     # Run the daemon
     docker run -d -v /home:/home my-app-image --create-user $USER:$myuid:$mygid

   Once started, the image can now be stopped and restarted while retaining
   the credential relationship with the host.

   .. note::
      Because containers are often *not* transient, and can be restarted, Chaperone is a bit
      smart about interpreting this switch, which usually be present both when the container
      is first started and when it is started again.  So, if the user name specified by
      ``--create-user`` already exists, Chaperone will check to assure that any
      ``uid`` or ``gid`` are correct, and proceed silently.

      If the user credentials are defined differently, then an error will occur.


.. _option.default-home:

.. option:: --default-home directory

   This option is meaningful only when used in combination with :ref:`--create-user <option.create-user>`
   and specifies the home directory to use if the user's home directory does not exist.

   This switch can be useful if a user's home directory may optionally be mounted as part
   of a volume mount, or if no such mount is provided, the user directory can default to an
   alternate location within the container itself.

   For example, assume that a container normally accepts a mount-point for ``/home``, where
   the specified user (in this case ``joebloggs``) has a pre-existing home directory,
   as follows::

     docker run -v /home:/home myimage --create-user joebloggs --config apps/chaperone.conf

   In this case, chaperone would find it's configuration in ``/home/joebloggs/apps/chaperone.conf``.

   But, if you wanted the container to be more versatile, you may want to create an
   application directory *inside* the container as well so that the container could run
   with either an internal configuration, or an external configuration to simplify
   development.

   So, the following could be used to provide a default home::

     docker run -v myimage --create-user joebloggs --default-home /defhome \
         --config apps/chaperone.conf

   The above command would instead find chaperone's configuration in ``/defhome/apps/chaperone.conf``,
   providing that no directory ``/home/joebloggs`` exists inside the container.

   Typically, when a container is first built, this switch is included in the
   :ref:`_CHAP_OPTIONS <env._CHAP_OPTIONS>` environment variable.  Doing so allows the container
   to be executed with a home directory mountpoint, or without.


.. _option.show-dependencies:

.. option:: --show-dependencies

   More complex service scenarios which use service directives :ref:`before <service.before>`,
   :ref:`after <service.after>` and :ref:`service_groups <service.service_groups>` can sometimes
   require debugging to assure the startup sequence is correct.

   This switch provides some assistance by creating an ASCII dependency graph which
   shows the relationship between services after Chaperone analyzes service
   dependencies.

   Here is how you can see a sample::

     $ docker run -i --rm=true chapdev/chaperone-lamp --show-dependencies
                 init | mysql | apache2 | logrotate | sample
     init      | ====
     mysql     |     ========
     apache2   |             ==========
     logrotate |             ======================
     sample    |                                   =========
     ----------> depends on...
     init      | 
     mysql     | init
     apache2   | mysql, init
     logrotate | mysql, init
     sample    | logrotate, apache2, mysql, init

   The output consists of two sections.  The top section shows the earliest
   start time for each service, relative to other defined services, rougly
   in the order Chaperone will start them.  The lower section contains
   the explicit dependencies after they have been resolved.

   You can also obtain this information from inside the container using
   the ":ref:`telchap dependencies <telchap.dependencies>`" command::

      rbunion@69c0e692d78c:~$ telchap dependencies
      telchap dependencies
                  init | mysql | apache2 | logrotate | sample | CONSOLE
      init      | ====
      mysql     |     ========
      apache2   |             ==========
      logrotate |             ======================
      sample    |                                   =========
      CONSOLE   |                                            ==========
      ----------> depends on...
      init      | 
      mysql     | init
      apache2   | init, mysql
      logrotate | init, mysql
      sample    | apache2, logrotate, init, mysql
      CONSOLE   | apache2, logrotate, init, mysql, sample

   If the container is running with a command-line command (such as ``bash``)
   you will also see the ``CONSOLE`` service listed, which is the service
   which was created internally to manage the interactive console.  Because
   the console is part of the :ref:`IDLE group <service.service_groups>`,
   you can see that it depends upon all other services before it will
   start.

.. _option.task:

.. option:: --task

   This is a convenience switch which is presently equivalent to combining:

     * :ref:`--no-console-log <option.no-console-log>`,
     * :ref:`--disable-services <option.disable-services>`, and
     * :ref:`--exitkills <option.exitkills>`.

   It is useful when the command provided on the command line does
   some utility task which circumvents the normal operation of the
   container.

   For example, imagine that you create a complex container with
   several internal components, and want to provide an easy way
   to report on the versions of software inside the container.
   You could write a simple script, perhaps called ``/app/bin/report-versions``
   then run it like this::

     $ docker run -i --rm=true my-app-image --task /app/bin/report-versions
     ngnnx: 1.9.1
     cluster-supervisor: git tag = 'production-1.22'
     replicator: 0.1
     $

   The ``--task`` switch attempts to silence any other output,
   and assure the container does nothing except start the command-line
   command (using the configured Chaperone environment), then exit.

   See the :ref:`get-chaplocal <get-chaplocal>` task for an example
   of how this switch has been used in practice.
