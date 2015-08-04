
.. _chap.example-docker:

A Simple Docker Example
=======================

The following example creates a simple Docker container running an Apache daemon and an SSH server, both
managed by Chaperone. 

In this example, we'll use Chaperone to run both processes as ``root``, configured to work exactly
as they were configured in the Ubuntu distribution.  This example is based upon a 
`similar example from docker.com <https://docs.docker.com/articles/using_supervisord/>`_ which 
uses `Supervisor <http://supervisord.org>`_ as it's process manager.  Chaperone provides a far
more powerful featureset than 'supervisor' with a much smaller container footprint.

Creating a Dockerfile
---------------------

We'll start by creating a basic ``Dockerfile`` for our new image::

    FROM ubuntu:14.04
    MAINTAINER garyw@blueseastech.com

Now, we can install ``openssh-server``, ``apache2``, and ``python3-pip``, then use
``pip3`` to install Chaperone itself.  We also need to create a few directories
that will be needed by the installed software::

    RUN apt-get update && \
	apt-get install -y openssh-server apache2 python3-pip && \
	pip3 install chaperone
    RUN mkdir -p /var/lock/apache2 /var/run/apache2 /var/run/sshd /etc/chaperone.d

Adding Chaperone's Configuration File
-------------------------------------

Now, let's add a configuration file for Chaperone.   Chaperone looks in
``/etc/chaperone.d`` by default and will read any configuration files it finds there.
So, we'll copy our single configuration there so Chaperone reads it upon startup::

    COPY chaperone.conf /etc/chaperone.d/chaperone.conf

Let's take a look at what's inside ``chaperone.conf``::

    sshd.service: { 
      command: "/usr/sbin/sshd -D"
    }

    apache2.service: {
      command: "bash -c 'source /etc/apache2/envvars && exec /usr/sbin/apache2 -DFOREGROUND'",
    }

    console.logging: {
      selector: '*.warn',
      stdout: true,
    }

The above is a complete configuration file with three sections.  the first two start up
both ``sshd`` and ``apache2``.  The third section tells Chaperone to intercept all ``syslog``
messages and redirect them to ``stdout``.  That way, we'll be able to use the ``docker logs``
command to inspect the status of the running container.

The above is really a simple configuration, but you can use the complete :ref:`set of service directives <service>`
to control how each service behaves.

Exposing Ports and Running Chaperone
------------------------------------

Let's finish our ``Dockerfile`` by exposing some required ports and specifying Chaperone
as the ``ENTRYPOINT`` so that Chaperone will start first and manage our container::

    EXPOSE 22 80
    ENTRYPOINT ["/usr/local/bin/chaperone"]

Here, we've exposed ports 22 and 80 on the container and we're running the
``/usr/local/bin/chaperone`` binary when the container launches.

Building the Image
------------------

We can now build our new image::

   $ docker build -t <yourname>/chap-sample .

Running the Container
---------------------

Once you've built an image, you can launch a container from it::

  $ docker run -p 22 -p 80 -t -i <yourname>/chap-sample

  Jul 21 04:08:19 6d3e4eee4265 apache2[6]: AH00558: apache2: Could not reliably determine the server's fully qualified domain name, using 172.17.0.90. Set the 'ServerName' directive globally to suppress this message

And when you want to stop it, just use ``Ctrl-C``::

  C-c C-c^C
  Ctrl-C ... killing chaperone.
  Jul 21 04:08:23 6d3e4eee4265 chaperone[1]: Request made to kill system. (forced)
  Jul 21 04:08:23 6d3e4eee4265 chaperone[1]: sshd.service terminated abnormally with <ProcStatus signal=2>

What's Next?
------------

You can build upon the above simple sample if you want.  That gives you maximum flexibility to design
your container service environmetn exactly as you want.  If so, we recommend you scan the 
:ref:`reference` section so you know what features are available.

If you want, you can also use the complete set of pre-built Chaperone images
`available here on Docker Hub <https://registry.hub.docker.com/repos/chapdev/>`_.  These images
are excellent examples of complete Chaperone-managed development and production environments.
You can learn more by reading the introduction to these 
images `on their GitHub page <https://github.com/garywiz/chaperone-docker>`_.
