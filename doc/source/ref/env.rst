.. _ch.env:

.. include:: /includes/defs.rst

Environment Variables
=====================

Overview and Quick Reference
----------------------------

Chaperone-specific environment variables are described here.  Because environment variables
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

Environment variable directives (as well as some others), can contain bash-inspired [#f1]_ environment variable expansions, as indicated below:

``$(ENVVAR)`` or ``${ENVVAR}``
  Expands to the specified environment variable.  If the environment variable is not defined, the expansion text
  is not replace and will appear as is.

``$(ENVVAR:-default)``
  Inserts the environment variable if it is present, otherwise, expands to the string specified by ``default`` (which can
  be blank).

``$(ENVVAR:+ifpresent)``
  Inserts ``ifpresent`` if the environment variable *is defined*, otherwise inserts the empty string.

``$(ENVVAR:_default)``
  Inserts the empty string if the environment variable *is defined*, otherwise inserts ``ifpresent``.
  (This is the opposite of the previous ``:+`` operation.)

``$(ENVVAR:?error-message)``
  Inserts the environment variable, or stops Chaperone with the specified ``error-message`` if the variable
  is not defined.

``$(ENVVAR:|present-val|absent-val)``
  If the environment variable is defined, then inserts the expansion of ``present-val``, otherwise
  inserts the expansion of ``absent-val``.

``$(ENVVAR:|check-val|equal|notequal)``
  Compares the expanded value of ``ENVVAR`` to ``check-val`` using case-insensitive comparison.  If they are
  equal, then inserts ``equal`` otherwise inserts ``notequal``.

``$(ENVVAR/regex/repl/[i])``
  Expands the named environment variable, then performs a regular expression substitution using ``regex`` with
  the replacement string ``repl``.   If either contains slashes, they must be escaped using a backslash.
  The optional flags can be set to ``i`` if case-insensitive matching is required.  Parenthesized groups
  in ``regex`` can be referred to in the replacement as ``\n`` where 'n' is zero to refer to the entire 
  matched string, or 1-n to specify the group number.

The forms above are patterned after ``bash`` and can be useful in cases where defaults are required.  For example,
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

Backtick Expansion
******************

Chaperone supports backtick expansion similar to most command shells.  Backtick expansion can be used wherever
environment variables can be used (denoted by the |ENV| symbol in the directive documentation).   Any valid
system command can be included, and the output will be substituted for the backtick expression.   For example,
to set an environment variable to the default gateway (normally the Docker bridged network)::

    settings: {
      env_set: {
        "GATEWAY_IP": "`ip route | awk '/default/ { print $3 }'`"
      }
   }

Backtick expansions are not intended to be a general-purpose shell escape, but intended for situations (like the
example) where some system information needs to be collected for configuration purposes.    Specifically,
backtick expansion have the following characteristics:

* Backticks will be processed *after* all dependent environment variables are expanded.
* Expansions are done only once, even if they are present in multiple locations.  Thus, the backtick
  expression `\`date\`` will expand to the same value no matter how many times it is used.
* The environment passed to the backtick command will be *the initial chaperone environment* before
  any directives are processed.
* Backtick expansions will be performed as the user specified by the `uid` and `gid` relevant to the
  section where the backtick expansion is used.

However, note that backtick expansions may include references to other environment variables, such as::

  settings: {
    env_set: {
      "LOCALDATE": "`TZ=${TZ} date`",
      "TZ": "America/Los_Angeles",
    }

Note in the above that the `TZ` variable will be expanded first (if necessary) before the backtick
expression.


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

.. _env._CHAP_INTERACTIVE:

.. envvar:: _CHAP_INTERACTIVE

   This variable will always be set by Chaperone to either "0" or "1".  A "1" value
   indicates that Chaperone detected a controlling terminal (pseudo-tty).  For example::

     $ docker run -t -i chapdev/chaperone-baseimage --task /bin/echo '$(_CHAP_INTERACTIVE)'
     1
     $ docker run -i chapdev/chaperone-baseimage --task /bin/echo '$(_CHAP_INTERACTIVE)'
     0
     $

   Exporting this value to services can allow services to detect interactive
   vs. daemon containers in order to tailor their operation.

.. _env._CHAP_SERVICE:

.. envvar:: _CHAP_SERVICE

   For each :ref:`service definition <service>`, this variable will be set to the name
   of the service itself, including the ``.service`` suffix.  So, the service::

     mydata.service: {
       command: "/bin/bash -c '/bin/echo $(_CHAP_SERVICE) >/tmp/service.txt'"
     }

   will write ``mydata.service`` to the file ``/tmp/service.txt`` (not particularly useful).

   Note that even the main command runs as a conventional service named "CONSOLE"::

     $ docker run -i chapdev/chaperone-baseimage --task /bin/echo '$(_CHAP_SERVICE)'
     CONSOLE
     $

.. _env._CHAP_TASK_MODE:

.. envvar:: _CHAP_TASK_MODE

   This variable will be defined and set to "1" whenever Chaperone was run with the
   :ref:`--task <option.task>` command-line option.

   It can be used within scripts or applications to tailor behavior, if desired.


Notify Socket
-------------

.. _env.NOTIFY_SOCKET:

.. envvar:: NOTIFY_SOCKET

   Chaperone attempts to emulate ``systemd`` behavior by providing a
   :ref:`"forking" service type <service.sect.type>`.   Processes created by this type
   will have the additional variable ``NOTIFY_SOCKET`` set in their environment,
   which is the path to a UNIX domain socket created privately within the
   container.  The service should use this environment variable to trigger
   notifications compatible with

.. rubric:: Notes

.. [#f1]

   Originally, the intent was to duplicate ``bash`` environment variable expansion syntax as compatibly as possible.
   Over time, however, it became clear that pattern matching replacements such as ``${NAME/*.jpg/something}`` relied
   upon many arcane ``bash`` details such as arrays and filename globbing.  Therefore, while the basic environment
   tests (such as those for defaults as in ``$(HOME:-/home)``) are compatible, a more useful set of regex-based
   features were added to eliminate the need for many ``bash`` substitution options.
