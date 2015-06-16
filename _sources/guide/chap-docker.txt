
.. include:: /includes/incomplete.rst

.. _chap.docker:

Using Chaperone with Docker
===========================

While Chaperone is a general-purpose program that can be used to manage any small hierarchy of
processes, it was designed specifically to solve problems encountered when creating containers.

While the goal is to keep containers streamlined and small, ideally containing only one
process, the reality is that in many real-world applications, existing daemons may need
to be exploited for use within a container to save time or provide commonly-available
functionality.  Some applications also benefit from greater modularity by breaking up
functionality into multiple processes to better exploit CPU resources.

The moment a container contains even two cooperating proceses, the problem of management
arises, and ``chaperone`` was designed to solve multi-process management simple
and well-contained.
