.. chapereone documentation master file, created by
   sphinx-quickstart on Mon May  6 17:19:12 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Chaperone: A lightweight, all-in-one process manager for lean containers
========================================================================

Chaperone is a lightweight alternative to process environment managers
like ``systemd`` or ``upstart``.   While chaperone provides an extensive
feature set, including dependency-based startup, syslog logging, zombie harvesting,
and job scheduling, it does all of this in a single self-contained process that can
run as a "system init" daemon or can run in userspace.   

This makes Chaperone an ideal tool for managing "small" process spaces like Docker
containers while still providing the system services many daemons expect.

If you are using Chaperone with Docker, we suggest reading the XXXX.

Any bugs should be reported as issues at https://github.com/garywiz/chaperone/issues.

Contents
--------

.. toctree::
   :maxdepth: 2

   chap-intro.rst
   chap-docker.rst
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
