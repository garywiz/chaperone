
.. include:: /includes/incomplete.rst

.. _chap.other:

Other Uses for Chaperone
========================

Chaperone was designed for container use in scenarios such as Docker containers.  However,
it has also been designed to operate as a non-root process manager, though this has not
been tested very well.

If runnnig as a non-root user, observe the following:

* The :ref:`--force <option.force>` switch will need to be used at startup.
* Chaperone will not create it's ``syslog`` service at ``/dev/log``.
* Chaperone will not create the ``telchap`` command socket at ``/dev/chaperone.sock``.
* Process cleanup will not occur if processes are reparented, since they will be
  reparented to PID 1.

Other than these notes, Chaperone *should* work as a process manager within userspace
for managing small groups of related processes.  If you find use cases outside
of container management, let me know.
