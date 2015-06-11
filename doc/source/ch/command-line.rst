.. chapereone documentation n
   command line documentation

Chaperone Command Reference
===========================

.. program:: chaperone

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


     
