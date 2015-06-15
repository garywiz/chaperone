.. _ch.env:

Environment Variables
=====================

Chaperone uses environment variables in two ways:

1.  When the `chaperone` command first executes, environment variables are read and passed
    to the environment of any running services.  While this is the default, this can be
    changed using the :ref:`config.settings` section.
2.  Chaperone also sets "internal" environment variables which can be used within
    configuration files, but are not passed down to services.  Internal environment
    variables start with an underscore (`_`) character. 

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

Notify Socket
*************

.. _env.NOTIFY_SOCKET:

.. envvar:: NOTIFY_SOCKET

   Chaperone attempts to emulate ``systemd`` behavior by providing a
   :ref:`"forking" service type <service.type>`.   Processes created by this type
   will have the additional variable ``NOTIFY_SOCKET`` set in their environment,
   which is the path to a UNIX domain socket created privately within the
   container.  The service should use this environment variable to trigger
   notifications compatible with
