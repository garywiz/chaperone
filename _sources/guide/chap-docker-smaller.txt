
.. _chap.small-docker:

Creating Small Docker Images
============================

The default official Docker images are not always very compact.  For example, the official Ubuntu image
is about 180MB, and the official Java image is a whopping 810MB!

This is made worse by some distributions (like Ubuntu and Debian) which have defaults which don't cater
to small image sizes and prefer to assure that things you *might* need are installed.   So, for example,
installing Python's package manager ``pip`` will cause about 200MB of extra packages to be installed just
"in case" some package requires the full compiler toolchain (which most Python packages, including Chaperone, do not).

Chaperone, including all its dependences, need take up no more than 35-40MB maximum, including Python3.

So, here is a quick guide to creating small Chaperone packages with a minimum of effort.


Eliminating Ubuntu/Debian Recommended Packages
----------------------------------------------

The simplest thing you can do when installing packages under Ubuntu or Debian is use the ``--no-install-recommends`` switch
when you run ``apt-get``.  For example, the :ref:`Simple Docker Example <chap.example-docker>` section recommends you install Chaperone, Apache and SSH like this::

    RUN apt-get update && \
	apt-get install -y openssh-server apache2 python3-pip && \
	pip3 install chaperone
    RUN mkdir -p /var/lock/apache2 /var/run/apache2 /var/run/sshd /etc/chaperone.d

If you do, you end up with a docker image which is 451MB::

    $ docker images
    REPOSITORY           TAG        IMAGE ID        CREATED          VIRTUAL SIZE
    sample-simple        latest     328d42703323    34 minutes ago   451.8 MB
    $

However, if you change the install commands to::

    RUN apt-get update && \
	apt-get install -y --no-install-recommends openssh-server apache2 python3-pip && \
	pip3 install chaperone

The functionally equivalent image is only 242MB::

    sample-simple        latest     8839acc1e4ef    24 minutes ago   242 MB

A Small Ubuntu Base Image with Chaperone
----------------------------------------

The sample image above contains both SSH as well as Apache.  However, let's assume that you want
to create the simplest Chaperone base image possible.   Here is the ``Dockerfile`` to start with::

    FROM ubuntu:14.04
    RUN apt-get update && \
	apt-get install -y --no-install-recommends python3-pip && \
	pip3 install chaperone
    RUN mkdir -p /etc/chaperone.d
    COPY chaperone.conf /etc/chaperone.d/chaperone.conf
    ENTRYPOINT ["/usr/local/bin/chaperone"]

The following ``chaperone.conf`` can serve as your starting point::

    your.service: {
      command: "logger -p warn 'Replace this with your service'",
    }

    console.logging: {
      selector: '*.warn',
      stdout: true,
    }

If you build the above image, it will be just 226MB, only 38MB larger than the Ubuntu image::

    $ docker images
    REPOSITORY           TAG        IMAGE ID        CREATED            VIRTUAL SIZE
    base-ubuntu          latest     182521cfa43e    About an hour ago  226 MB


A 53MB Alpine Image with Chaperone
----------------------------------

If you really care about keeping your images as minimal as possible, consider using 
`Alpine Linux <http://www.alpinelinux.org/>`_ as your base image.   Alpine is a simple,
stripped down distribution that is ideal for creating lean, mean containers.

Here's a ``Dockerfile`` that will create small Alpine Linux image, complete with both
Chaperone as well as Python3::

    FROM alpine:3.2
    RUN apk add --update python3 && pip3 install chaperone
    RUN mkdir -p /etc/chaperone.d
    COPY chaperone.conf /etc/chaperone.d/chaperone.conf
    ENTRYPOINT ["/usr/bin/chaperone"]

The resulting image is less than 53MB::

    $ docker images
    REPOSITORY           TAG        IMAGE ID        CREATED            VIRTUAL SIZE
    base-alpine          latest     1c9d85d9bb67    About an hour ago  52.59 MB


Pre-Built Images
----------------

When building our official Chaperone base images (`located here on Docker Hub <https://hub.docker.com/u/chapdev/dashboard/>`_),
we used the techniques above to create versatile images with reasonably sophisticated start-ups.  They may be
overkill for most applications, but they may also serve as good configuration examples.

Notably, the `chaperone-alpinejava <https://hub.docker.com/r/chapdev/chaperone-alpinejava/>`_ image is a good
example of what's possible.   It contains a complete Oracle 8 production environment, Python 3, Chaperone, and
it's a remarkably small 216MB!

Hopefully the above information is a useful way to get started at streamlining images.


