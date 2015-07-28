#!/bin/bash
# Used to start up a bare chaperone test image using ubuntu:latest.  Helps for streamlining installation
# and startup issues for new users.

echo Bare Ubuntu startup
# Start up an apt-get proxy which runs on our host in another container, if it's present
/setup/ct_setproxy
cd $SANDBOX/../dist
pip3 install chaperone-*.tar.gz
exec bash -i
