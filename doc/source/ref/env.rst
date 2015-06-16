.. _ch.env:

Environment Variables
=====================

Overview and Quick Reference
----------------------------

Chaperone-specific environment variables are descirbed here.  Because environment variables
are an important configuration component for many applications, Chaperone tries to make
sure any Chaperone-specific variables do not automatically pollute the environment, and
yet are available when needed.

So, with few exceptions, Chaperone environment variables start with
the prefix ``_CHAP_``, but are not automatically passed down to
services.  If you want to make these available to services, simply
define an environment variable in your configuration which expands to
one of the internal variables::

  settings: {
    env_set: {
      # Make the relevant service name available to all processes
      'SERVICE_NAME': '$(_CHAP_SERVICE)',
    }
  }

.. _table.env-quick:

.. table:: Environment Variable Quick Reference

   ================================================  =====================================================================
   environment variable                              meaning
   ================================================  =====================================================================
   :ref:`_CHAP_CONFIG_DIR <env._CHAP_CONFIG_DIR>`    Will be set to the full path to the directory containing the
			  			     configuration file or directory.
   :ref:`_CHAP_INTERACTIVE <env._CHAP_INTERACTIVE>`  Will be set to "1" if chaperone is running with a controlling tty.
   :ref:`_CHAP_OPTIONS <env._CHAP_OPTIONS>`          Recognized during start-up and contains any default command-line
   		       				     options.
   :ref:`_CHAP_SERVICE <env._CHAP_SERVICE>`          Contains the name of the current service.
   :ref:`_CHAP_TASK_MODE <env._CHAP_TASK_MODE>`      Will be set to "`" if chaperone was invoked with the
   			 			     :ref:`--task <option.task>` option.
   :ref:`NOTIFY_SOCKET <env.NOTIFY_SOCKET>`          Set to the per-service systemd-compatible notify socket for
		       				     service started with :ref:`type=notify <service.type>`.
   ================================================  =====================================================================


Managing Environment Variables
------------------------------

Environment Inheritance
***********************

Chaperone provides extensive control over environment variables as they are passed from the parent (often the
container technology, like Docker), and eventually down to individual services.

.. _figure.env:

.. figure:: /images/env_inherit.svg
   :align: center

   Chaperone Environment Management

As shown in :numref:`figure.env`, Chaperone controls the environment at two levels, and with three separate directives:

1. Chaperone creates a "global" settings environment which consists of environment variables inherited from
   the parent environment, modified by the three environment directives :ref:`env_inherit <settings.env_inherit>`, 
   :ref:`env_set <settings.env_set>`, and :ref:`env_unset <settings.env_unset>`.
2. Each service can further modify the resulting environment using the same directives, and the changes apply
   only to the environment of the selected service.

In each case, Chaperone processes each set of directives in the same way:

1. The new environment is initialized based upon the setting of :ref:`env_inherit <settings.env_inherit>`,
   a list of patterns.  If not specified, Chaperone assumes all environment variables will be inherited.
2. Then, Chaperone sets any new environment variables specified by :ref:`env_set <settings.env_set>`.
3. Finally, any environment variables specified by :ref:`env_unset <settings.env_unset>` are removed
   if they exist.

.. _env.expansion:

Environment Variable Expansion
******************************

Environment variable directives (as well as some others), can contain environment variable expansions, as indicated below:

``$(ENVVAR)`` or ``${ENVVAR}``
  Expands to the specified environment variable.  If the environment variable is not defined, the expansion text
  is not replace and will appear as is.

``$(ENVVAR:-default)``
  Inserts the environment variable if it is present, otherwise, expands to the string specified by ``default`` (which can
  be blank).

``$(ENVVAR:+ifpresent)``
  Inserts ``ifpresent`` if the environment variable *is defined*, otherwise inserts the empty string.

The second two forms are borrowed from ``bash`` and can be useful in cases where defaults are required.  For example,
if you wanted to specify the user for a service in the event no user was otherwise specified::

  sample.service: {
    uid: "$(USER:-www-data)"
    ...
  }

The above would expand to the value of ``USER`` if it exists, otherwise would expand to ``www-data``.  Not all directives
support environment expansion.  When it is supported, it will be explicitly indicated in the reference documentation for
the directive (for example, the :ref:`service directory <service.directory>` directive).

.. note::

   Environment variables are expanded *as late as possible* so that declarations defined at the global level can, if desired,
   be filled in automatically at lower levels.  For example, consider this globally set environment variable declaration::

     settings: {
       env_set: {
	 'MY_NAME': '$(_CHAP_SERVICE)',
	 'HAS_NOTIFY_SOCKET': '$(NOTIFY_SOCKET:+1)',
	 'PATH': '/service-bins/$(MY_NAME):$(PATH)',
       }
     }

   In the above case, note that all environment variables are dependent upon values which will *not exist*
   until later when a service is executed.  Specifically ``_CHAP_SERVICE`` is set to the service name, and
   ``NOTIFY_SOCKET`` will be set only if a socket is allocated when the process is run.  However, Chaperone
   assures that such environment variables use late-expansion so that templates such as the above can
   be created and inherited by both logging and service declarations.

Variable Reference
------------------

.. _env._CHAP_CONFIG_DIR:

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

.. _env._CHAP_OPTIONS:

.. envvar:: _CHAP_OPTIONS

   When Chaperone starts, it reads options both from the command line and from this environment
   variable.  The environment variable provides defaults which should be used if they are 
   not present on the command line.

   For example, in the ``chaperone-baseimage`` image configuration, the default value
   for ``--config`` is set::

	    ENV _CHAP_OPTIONS --config apps/chaperone.d
	    ENTRYPOINT ["/usr/local/bin/chaperone"]

Notify Socket
-------------

.. _env.NOTIFY_SOCKET:

.. envvar:: NOTIFY_SOCKET

   Chaperone attempts to emulate ``systemd`` behavior by providing a
   :ref:`"forking" service type <service.type>`.   Processes created by this type
   will have the additional variable ``NOTIFY_SOCKET`` set in their environment,
   which is the path to a UNIX domain socket created privately within the
   container.  The service should use this environment variable to trigger
   notifications compatible with
