#!/bin/bash

# Assumes there is an "optional" apt-get proxy running on our HOST
# on port 3142.  You can run one by looking here: https://github.com/sameersbn/docker-apt-cacher-ng
# Does no harm if nothing is running on that port.
/setup-bin/ct_setproxy

# Normal install steps
apt-get install -y apache2
