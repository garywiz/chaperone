.. chapereone documentation
   configuration directives

.. _config.file-format:

Configuration File Format
=========================

Chaperone's configuration is contained either in a single file, or a directory of configuration.
You specify the configuration with the :ref:`--config <option.config>` switch on the command line.
If none is specified, the default `/etc/chaperone.d` is used.  If a directory is chosen, then only the
top-level of the directory will be searched, and only files ending in ``.conf`` or ``.yaml`` will be
recognised and read in alphabetic order.

Configuration files are written using `YAML Version 2 <http://www.yaml.org/spec/1.2/spec.html>`_.  For example, you can
define two chaperone services like this::

  mysql.service:
    command: "/etc/init.d/mysql start"

  apache2.service:
    command: "/etc/init.d/apache2 start"
    after: mysql.service
    
While the above works perfectly fine, we prefer to use the `YAML "flow style" <http://yaml.org/spec/1.2/spec.html#Flow>`_ which
looks very similar to JSON.  In flow format, the above looks like this::

  mysql.service: {
    command: "/etc/init.d/mysql start"
  }

  apache2.service: {
    command: "/etc/init.d/apache2 start",
    after: mysql.service,
  }

The flow style is both easy to read, and works better when configurations become more complex.  So, throughout
the chaperone documentation, we'll stick to the flow format.

Comments can be included both between lines and at the end of lines using the hash symbol (``#``).  Here is a complete well-commented
configuration section for a sample service that's included with the ``chaperone-baseimage`` docker image::

  # This is a sample oneshot service that runs at IDLE time, just before 
  # the console app, if present. It will output something so at least
  # something appears on the screen.

  sample.service: {
    # This is a oneshot service, but most likely a real applicaton will be another type
    # such as 'simple', or 'forking'.
    type: oneshot,
    enabled: true,   # CHANGE TO 'false' so this app doesn't run any more

    # Command output goes directly to stdout instead of to the syslog.
    # Note that you normally want to have services output to the syslog, because
    # chaperone's logging directives allow you to echo syslog data to stdout.  That's
    # a better place to control things (see 010-start.conf).
    command: "$(APPS_DIR)/bin/sample_app",
    stdout: inherit,

    # Because we're in the IDLE group, we will run only after all system services have
    # started.  However, if there is a command line program, like /bin/bash, we want to
    # run before that one.  All upper-case group names have special meanings.  However,
    # You can define your own service groups, then use them to declare startup
    # dependencies.
    service_groups: "IDLE",
    before: "CONSOLE",

    # These environment variables will be added only for your service
    env_set: {
      'INTERACTIVE': '$(_CHAP_INTERACTIVE)',
    }
  }
