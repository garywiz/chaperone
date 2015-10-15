
.. _intro:

Introduction to Chaperone
=========================

Overview
--------

Container technologies like Docker and Rocket have changed dramatically the way
we bundle and distribute applications. While many containers are built with
a single contained process in mind, other applications require a small suite
of processes bundled into the "black box" that containers provide.  When this
happens, the need arises for a container control system, but the available
technologies such as ``systemd`` or ``upstart`` are both too modular and
too heavy, resulting in "fat containers" which introduce the very kinds of
overhead container technologies are designed to eliminate.

Chaperone is designed to solve this problem by providing a single, self-contained
"caretaker" process which provides the following capabilities within the container:

* Dependency-based parallel start-up of services.
* A robust process manager with service types for forking, oneshot, simple,
  and notify service types modelled after systemd.
* Port-triggered services inside the container using the inetd service type.
* A "cron" service type to schedule periodic tasks.
* A built-in highly configurable syslog service which can direct syslog
  messages to multiple output files and duplicate selected streams or severities
  to the container stdout as well.
* Control capabilities so that services can be stopped, started, or restarted easily
  at the command line or within application programs.
* Emulation of systemd's ``sd_notify`` capability, allocating notify sockets
  for each service so that cgroups and other privileges are not needed
  within the container.  Chaperone also recognizes a passed-in ``NOTIFY_SOCKET``
  and will inform the host systemd of final container readiness and status.
* Features to support the creation of "mini-systems" within a single directory
  so that system services can run in userspace, or be mounted on host shares
  to keep development processes and production processes as close to identical
  as possible (see ``chaperone-lamp`` for an example of how this can be realized).
  
In addition, many incidental features are present, such as process monitoring and
zombie clean-up, clean shutdown and container restarts, and interactive console
process detection so that applications know when they are being run interactively.

