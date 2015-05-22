#!/bin/bash

/setup/ct_setproxy
apt-get update
apt-get -y install python3-pip
pip3 install setuptools
