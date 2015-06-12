.. chapereone documentation
   configuration directives

Configuration: Logging Declarations
===================================

Chaperone has its own internal ``syslog`` service which listens on the ``/dev/log`` socket.  Hoewver, by default,
none of the messages sent to the syslog will be stored or output unless logging declarations are made.

The simplest logging directive tells chaperone what to do with log entries using a superset of the familiar
`syslogd configuration format <http://linux.die.net/man/5/syslog.conf>`_.  For example, the following will
direct all messages at the warning level (or greater) to ``stdout``::

  console.logging: {
    filter: '*.warn',
    stdout: true,
  }

You can define as many different logging entries, and all will be respected as individual output targets.  If you
have services which do significant syslog output, you can decide on a per-service basis which logs go where,
what aspects are sent to ``stdout`` and which go to log files.

An overview of logging directives follow, then detailed reference information.

=================  =============================================================================
logging keyword    meaning
=================  =============================================================================
filter		   Specifies the syslog-compatible selection filter for this logging entry.
file		   Specifies an optional file for output.
stderr		   Directs output to ``stderr`` (can be used with ``file``).
stdout		   Directs output to ``stdout`` (can be used with ``file``).
enabled		   Can be set to ``false`` to disable this logging entry.
overwrite	   If ``file`` is provided, then setting this to ``true`` will overwrite
		   the file upon opening.  By default, log files operate in append mode.
extended	   Prefixes log entries with their facility and priority (useful primarily
		   for debugging).
uid		   The uid (name or number) for permissions on created files and directories.
gid		   The gid (name or number) for permissions on created files and directories.
=================  =============================================================================
