#!/bin/bash

# Assumes there is an "optional" apt-get proxy running on our HOST
# on port 3142.  You can run one by looking here: https://github.com/sameersbn/docker-apt-cacher-ng
# Does no harm if nothing is running on that port.
/setup-bin/ct_setproxy

# Normal install steps
apt-get update
apt-get -y install python3-pip

# We install from the local directory rather than pip so we can test and develop.
cd /setup-bin/chaperone
python3 setup.py install
