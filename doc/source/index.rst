.. chapereone documentation master file, created by
   sphinx-quickstart on Mon May  6 17:19:12 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Chaperone: A lightweight, all-in-one process manager for lean containers
========================================================================

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

* A robust process manager with service types for forking, oneshot, simple, and
  notify service types modelled after systemd.
* Dependency-based parallel start-up of services.
* A "cron" service type to schedule periodic tasks.
* A built-in highly configurable syslog service which can direct syslog
  messages to multiple output files and duplicate selected streams or severities
  to the container stdout as well.
* Control capabilities so that services can be stopped, started, or restarted easily
  at the command line or within application programs.
* Emulation of systemd's ``sd_notify`` capability, allocating notify sockets
  for each service so that cgroups and other privileges are not needed
  within the container.
* Features to support the creation of "mini-systems" within a single directory
  so that system services can run in userspace, or be mounted on host shares
  to keep development processes and production processes as close to identical
  as possible (see ``chaperone-lamp`` for an example of how this can be realized).
  
In addition, many incidental features are present, such as process monitoring and
zombie clean-up, clean shutdown and container restarts, and interactive console
process detection so that applications know when they are being run interactively.

Any bugs should be reported as issues at https://github.com/garywiz/chaperone/issues.


Contents
--------

.. toctree::
   :maxdepth: 2

   ch/command-line.rst
   ch/config.rst

Downloading and Installing
--------------------------

The easiest way to install ``chaperone`` is using ``pip`` from the https://pypi.python.org/pypi/chaperone package::

    # Ubuntu or debian prerequisites...
    apt-get install python3-pip

    # chaperone (may be all you need)
    pip3 install chaperone

If you're interested in the source code, or contributing, you can find the ``chaperone`` source code 
at https://github.com/garywiz/chaperone.
    

License
-------

Copyright (c) 2015, Gary J. Wisniewski <garyw@blueseastech.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
