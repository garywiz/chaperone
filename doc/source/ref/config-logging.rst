.. chapereone documentation
   configuration directives

.. include:: /includes/defs.rst

.. _logging:

Configuration: Logging Declarations
===================================

Logging Quick Reference
-----------------------

Chaperone has its own internal ``syslog`` service which listens on the ``/dev/log`` socket.  Hoewver, by default,
none of the messages sent to the syslog will be stored or output unless logging declarations are made.

The simplest logging directive tells chaperone what to do with log entries using a superset of the familiar
`syslogd configuration format <http://linux.die.net/man/5/syslog.conf>`_.  For example, the following will
direct all messages at the warning level (or greater) to ``stdout``::

  console.logging: {
    selector: '*.warn',
    stdout: true,
  }

You can define as many different logging entries, and all will be respected as individual output targets.  If you
have services which do significant syslog output, you can decide on a per-service basis which logs go where,
what aspects are sent to ``stdout`` and which go to log files.

An overview of logging directives follow, then detailed reference information.  Entries below
marked with |ENV| support :ref:`environment variable expansion <env.expansion>`.


.. _table.logging-quick:

.. table:: Logging Directives Quick Reference

   =====================================  =============================================================================
   logging keyword                        meaning
   =====================================  =============================================================================
   :ref:`selector <logging.selector>`     Specifies the syslog-compatible selection filter for this logging entry.
		  			  |ENV|
   :ref:`file <logging.file>`             Specifies an optional file for output. |ENV|
   :ref:`stderr <logging.stderr>`         Directs output to ``stderr`` (can be used with ``file``).
   :ref:`stdout <logging.stdout>`         Directs output to ``stdout`` (can be used with ``file``).
   :ref:`enabled <logging.enabled>`       Can be set to ``false`` to disable this logging entry.
   :ref:`overwrite <logging.overwrite>`   If ``file`` is provided, then setting this to ``true`` will overwrite
                                          the file upon opening.  By default, log files operate in append mode.
   :ref:`extended <logging.extended>`     Prefixes log entries with their facility and priority (useful primarily
                                          for debugging).
   :ref:`uid <logging.uid>`               The uid (name or number) for permissions on created files and directories. 
   	     				  |ENV|
   :ref:`gid <logging.gid>`               The gid (name or number) for permissions on created files and directories.
      	     				  |ENV|
   =====================================  =============================================================================

.. _logging.sect.selectors:

Syslog Selectors
----------------

The method used for selecting which log entries are sent to which logging services are specified using a selector
format similar to the one used by the standard ``syslogd`` daemon. [#f1]_  Chaperone includes some extensions to
the standard format to introduce greater flexiblity without deviating too far from the well-known syntax.

In the absence of a selector, Chaperone will direct all syslog output to the given location, so this entry
echoes literally every ``syslog`` message to the container's ``stdout``::

  everything.logging: { stdout: true }

While this may be alright for simple applications, or for debugging, most applications require more nuanced
control of what goes where.  This is done by using *selectors*.  For example, the following includes
a selector which echoes only messages which have 'err' severity or greater to ``stdout``::

  badstuff.logging { stdout:true, selector: '*.err' }

Selector Format
***************

The general format for selectors is:

   [!] *<facility>* . [!][=] *<priority>* ; ...

where

*<facility>*
   Describes the subsystem where the syslog message originated.  It is a comma-separated list of one of
   the following, with the last two options being Chaperone extensions:

   1. An asterisk (``*``) indicating all facilities.
   2. One of the keywords **kern**, **user**, **mail**, **daemon**, **auth**, **syslog**, **lpr**, **news**,
      **uucp**, **clock**, **authpriv**, **ftp**, **ntp**, **audit**, **alert**, **cron**, or **local0**
      through **local7**.
   3. A program identifier enclosed in brackets, such as ``[httpd]`` or ``[chaperone]``.
   4. A regular expression which will match any text within the message, such as ``/error/`` or ``/seg.*fault/``.

*<priority>*
   Describes the priority of the message, and is either an asterisk (``*``) or
   one of the following keywords in ascending order
   of severity: **debug**, **info**, **notice**, **warn** (or **warning**), **err** (or **error**),
   **crit**, **alert**, **emerg**.

Selectors including an exclamation mark are *negative* selectors, omitting otherwise included log entries.  A selector
*must* include positive selectors or no log entries will be selected.  For example::

  # Select all errors (or more severe) except those sent to the auth subsystem
  selector: '*.err;auth,authpriv.!*'

However, the following selector will select nothing because there is no positive component::

  # Does nothing
  selector: 'auth,authpriv.!*'

Facility Selection
******************

Chaperone includes a more versatile set of options for selecting the facility where the message
originated.  You can include the classic ``syslog`` facility indication, or a program name (in brackets)
or even a regular expression to match.  

For example, assume a syslog message from ``sshd``::

  Jun  3 19:40:16 weevil sshd[1642]: Accepted publickey for root from ::1 port 48488 ssh2: RSA 24:2d:95:ec:09:fb:49:fa:e9:ff:e0:9e:c2:4d:13:42

Since ``sshd`` defaults to logging to the ``auth`` subsystem, the following would select the above message::

  selector: 'auth,authpriv.*'

You could also specify the program name::

  selector: '[sshd].*'

You could even use a regular expression to match arbitrary strings to select the message (assuming the above message is written
at priority 'info' or greater::

  selector: '/publickey/.info'

You could also select all info messages which did not contain the word "publickey" like this::

  selector: '*.info;!/publickey/.*'

Priority Selection
******************

Priority selection is simpler, but it's important to notice that choosing a priority means that messages
of that level *or greater severity* are selected::

  selector: '*.err'

will select messages of **err**, **crit**, **alert**, or **emerge**, whereas::

  selector: '*.*;*.!err'

will select messages of **debug**, **info**, **notice** or **warn**.   If you want to specify a priority
which is exact (either for exclusion or inclusion), use the `=` prefix.  The following selector
includes log entries *only* if they are at level 'debug'::

  selector: '*.=debug'


Logging Config Reference
------------------------

.. _logging.selector:

.. describe:: selector: "selector; [selector; ...]"

   Specifies the logging entries which will be selected for reporting by this service.  Multiple selectors can be provided,
   separated by semicolons.  If no selector option is provided, Chaperone assumes a selector of ``*.*``.

   See the separate section above :ref:`on syslog selectors <logging.sect.selectors>` for more details.

.. _logging.file:

.. describe:: file: "filepath"

   Indicates that output should be written to ``filepath``, which must be a full pathname or a pathname relative
   to the home directory of the logging user (implicitly defined, or defined by the :ref:`uid <logging.uid>` directive.

   *Note*: this should be an actual file, not a system file such as ``/dev/stdout``.  You can use the :ref:`stdout <logging.stdout>`
   directive to cause syslog output to be directed to ``stdout``.

   Chaperone supports two special features for logging filenames:

   1.  You can include substitutions within a log filename using the '%' substituion set compatible 
       with `strftime <http://man7.org/linux/man-pages/man3/strftime.3.html>`_.  If so, Chaperone will close and
       reopen the log file whenever the name changes.  For example::

	 filename: "$(APPS_DIR)/var/log/app-messages-%a.log"

       would create log files for each day of the week with names ``app-messages-sun.log``, ``app-messages-mon.log``. 

       Sometimes, this allows you to eliminate the need for log rotation.

   2.  If Chaperone notices that the file's 'inode' or mountpoint has changed, it will close and reopen the file
       automatically.  This means you can create jobs to do log-rotation, or manually rename or move the existing logfile
       and Chaperone will take notice and assure a new log file is opened.

   Note that you can combine this directive with :ref:`stdout <logging.stdout>` and :ref:`stderr <logging.stderr>`.  Output will
   be simultaneously written to all chosen locations.

.. _logging.stdout:

.. describe:: stdout ( false | true )

   If this is 'true', then all selected syslog records will be copied to the 'stdout' of the container.  Defaults to 'false'.

   Note that you can combine this directive with :ref:`stderr <logging.stderr>` and :ref:`file <logging.file>`.  Output will
   be simultaneously written to all chosen locations.

.. _logging.stderr:

.. describe:: stderr ( false | true )

   If this is 'true', then all selected syslog records will be copied to the 'stderr' of the container.  Defaults to 'false'.

   Note that you can combine this directive with :ref:`stdout <logging.stdout>` and :ref:`file <logging.file>`.  Output will
   be simultaneously written to all chosen locations.

.. _logging.enabled:

.. describe:: enabled ( true | false )

   Set this to 'false' to disable all logging to this logging service.

.. _logging.overwrite:

.. describe:: overwrite ( false | true )

   By default, Chaperone will append logs to any existing log file which matches the :ref:`file <logging.file>` directive.
   Setting this to 'true' will overwrite any log file.  Note that log files are opened when Chaperone starts running, so
   any overwrite will be immediate.

.. _logging.extended:

.. describe:: extended ( false | true )

   This option prefixes every output syslog line with the facility and priority which was used to write to the syslog.
   Normally, this is not desirable, since often people rely upon the format of a log file line, which typically
   looks like this::

     Jun 15 02:09:33 su [27]: pam_unix(su:session): session opened for user root by (uid=1000)

   If you set ``extended=true``, then log output lines will look like this::

     authpriv.info Jun 15 02:09:33 su [27]: pam_unix(su:session): session opened for user root by (uid=1000)

   Note that ``authpriv.info`` is at the beginning of the line, and indicates the facility and priority.

   This is primarily useful for debugging and fine-tuning logging output, as there is no good way to determine
   the exact facility and priority used by some daemons if they do not clearly document it.

.. _logging.uid:

.. describe:: uid user-name-or-number

   Chaperone will create and manage log files as the user specified by ``uid``.  If ``uid`` is not specified,
   the :ref:`settings uid <settings.uid>` will be used, and finally the user specified on the command
   line with :option:`--user <chaperone --user>` or :option:`--create-user <chaperone --create-user>`.

   If none of the above are specified, the Chaperone runs the service normally under its own account
   without specifying a new user.

   Specifying a user requires root privileges.  Within containers like Docker, chaperone usually runs
   as root, so service configurations can specify alternate users even if they are run under a
   different user account.

   For example, if Chaperone were run from docker using the :ref:`chaperone-baseimage` image like this::

     docker run -d chapdev/chaperone-baseimage \
                 --user wwwuser --config /home/wwwuser/chaperone.conf
      
   there is no reason that ``chaperone.conf`` could not contain the following logging definitions::

     mysql.logging: {
       uid: root,
       selector: "[mysql].*",
       file: "/var/log/mysql-%d.log",
     }

   In this case, "mysql.logging" would be written as 'root', regardless of what the user configuration
   is for other services.

   Typically, when using a :ref:`userspace development model <guide.UDM>`, you want daemon log
   files to be written under the development user's ID for easy management.

.. _logging.gid:

.. describe:: gid group-name-or-number

   When :ref:`uid <logging.uid>` is specified (either explicitly or implicitly inherited), the ``gid``
   directive can be used to specify an alternate group to be used for logging.  If not specified,
   then the user's primary group will be used.

   As with :ref:`uid <logging.uid>` specifying a group requires root priviliges.

.. rubric:: Notes

.. [#f1]

   The "standard" ``syslogd``, for our purposes, is the one authored by `Wettstein and Schulze <http://linux.die.net/man/5/syslog.conf>`_.
   While it has been in use for decades, there are also many variations and some inconsistencies in the way selectors are
   interpreted.
