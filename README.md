Chaperone: A lean init-style startup manager for Docker-like containers
-----------------------------------------------------------------------

*IMPORTANT*:  This project has just begun and is is pre-Beta phase.  Check the status section
below for release information and progress.

This is a lean, full-featured process which runs at the root of a docker
container tree.  It provides:

* Monitoring for all processes in the container, automatically shutting down the
  container when the last process exits.
* A complete, configurable syslog facility built in and provided on /dev/log
  so daemons and other services can have output captured.  Configurable
  to handle log-file rotation, duplication to stdout/stderr, and full Linux
  logging facility, severity support.  No syslog daemon is required in your
  container.
* The ability to start up system services, with options for per-service
  environment variables, restart options, and stdout/stderr capture either
  to the log service or stdout.
* A built-in cron scheduling service.
* Emulation of systemd notifications (sd_notify) so services can post
  ready and status notifications to chaperone.
* Process monitoring and zombie elimination, along with organized system
  shutdown to assure all daemons shut-down gracefully.
* The ability to have an optional controlling process, specified on the 
  docker command line, to simplify creating containers which have development
  mode vs. production mode.
* Complete configuration using a ``chaperone.d`` directory which can be located
  in various places, and even allows different configurations
  within the container, triggered based upon which user is selected at start-up.
* Default behavior designed out-of-the-box to work with simple Docker containers
  for quick start-up for lean containers.
* More...

There is some debate about whether docker containers should be transformed into
complete systems (so-called "fat containers").  However, it is clear that many
containers contain one or more services to provide a single "composite feature",
but that such containers need a special, more streamlined approach to managing
a number of common daemons.  

Chaperone is the best answer I've come up with so far, and was inspired by
The [Phusion baseimage-docker](http://phusion.github.io/baseimage-docker/) approach.
However, unlike the Phusion image, it does not require adding daemons for logging,
system services (such as runit).  Chaperone is designed to be self-contained.

Status
------

As of Saturday, 06-Jun-2015...

THIS PROJECT IS IN PRE-RELEASE PHASE, and has been uploaded here and to PyPi to
prepare for a more formal release.  I advise you do not use it yet.  However,
the released version does work in most of my test cases, and should install
properly from PyPi.

Some status notes:

* We are using this ourselves now in our pre-production containers, and very
  happy with the simplicity of container setup and so far chaperone is quite
  stable.
* We're working to release two images, ``chaperone-baseimage`` as a instructive
  example and starting point for chaperone containers as well as ``chaperone-lamp``
  for a full LAMP stack designed to simplify development and production with
  all needed features. Both will appear soon on github in source form and on
  Docker Hub as usable images.
* Documentation is in progress both for chaperone as well as the docker
  images.

Watch this space for announcements as final touches and documentation
are added in the next few weeks.

Downloading and Installing
--------------------------

The easiest way to install `chaperone`` is using ``pip`` from the https://pypi.python.org/pypi/chaperone package:

    # Ubuntu or debian prerequisites...
    apt-get install python3-pip

    # chaperone installation (may be all you need)
    pip3 install chaperone

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
