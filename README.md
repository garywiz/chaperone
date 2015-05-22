Chaperone: A lean init-style startup manager for Docker-like containers
-----------------------------------------------------------------------

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

As of Friday, 22-May-2014...

THIS PROJECT IS IN PRE-RELEASE PHASE, and has been uploaded here and to PyPi to
prepare for a more formal release.  I advise you do not use it yet.  However,
the released version does work in most of my test cases, and should install
properly from PyPi.

Watch this space for announcements as final touches and documentation
are added in the next few weeks.

Downloading and Installing
--------------------------

The easiest way to install `chaperone`` is using `pip` from the https://pypi.python.org/pypi/chaperone package:

    # Ubuntu or debian prerequisites...
    apt-get install python3-pip

    # chaperone installation (may be all you need)
    pip3 install chaperone

License
-------

This software is distributed under the BSD License.

Copyright (c) 2013, Gary J. Wisniewski,
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer:

   Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the
   distribution.  Neither the name of the author, the author's
   organization, nor the names of its contributors may be used to
   endorse or promote products derived from this software without
   specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
