#!/bin/bash
#Created by chaplocal on Wed Jun 10 16:08:42 EST 2015

cd ${0%/*} # go to directory of this file
APPS=$PWD
cd ..

options="-t -i -e TERM=$TERM --rm=true"
shellopt="/bin/bash"
if [ "$1" == '-d' ]; then
  shift
  options="-d"
  shellopt=""
fi

if [ "$1" == "-h" ]; then
  echo "Usage: run.sh [-d] [-h] [extra-chaperone-options]"
  echo "       Run chapdev/chaperone-baseimage:latest as a daemon or interactively (the default)."
  exit
fi

# Extract our local UID/GID
myuid=`id -u`
mygid=`id -g`

# Run the image with this directory as our local apps dir.
# Create a user with uid=$myuid inside the container so the mountpoint permissions
# are correct.

docker run $options -v /home:/home -p 8088:8080 chapdev/chaperone-lamp:latest \
   --create $USER:$myuid --config $APPS/chaperone.d $* $shellopt
