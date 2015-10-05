This directory contains both Chaperone unit tests as well as more complex integration tests.  The `run-all-tests.sh` script runs them all.

However, integration tests in this directory have several requirements.  They will run both on Ubuntu as well as RHEL.   Docker 1.8.1 is required, since socket mount permissions have problems with SELinux for earlier versions.

For both, you'll need everything Chaperone itself requires, and may need to install them manually since Chaperone may not be installed on the development system:

    pip3 install docopt
    pip3 install PyYAML
    pip3 install voluptuous
    pip3 install croniter

You will also need a working `chapdev/chaperone-lamp` image.  This is the image that is used for all of the tests in this directory and you can simply pull it if it isn't already available.

Wait, there's more.

For Ubuntu, you'll then need:

    apt-get install expect-lite
    apt-get install nc # should already be there

For CentOS/RHEL, it is a bit more complicated.  You'll need:

    yum install expect
    yum install nc

and then you'll need to manually install `expect-lite` using the instructions [on the developer website](http://expect-lite.sourceforge.net/expect-lite_install.html).  (It's pretty easy actually, and foolproof).
