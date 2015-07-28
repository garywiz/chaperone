#!/bin/bash

/setup-bin/ct_setproxy
apt-get update
apt-get -y install --no-install-recommends python3-pip
pip3 install setuptools
