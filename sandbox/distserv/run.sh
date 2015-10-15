#!/bin/bash
#Developer's startup script
#Created by chaplocal on Thu Oct 15 03:47:31 UTC 2015

IMAGE="chapdev/chaperone-apache"
INTERACTIVE_SHELL="/bin/bash"

# You can specify the external host and ports for your webserver here.  These variables
# are also passed into the container so that any application code which does redirects
# can use these if need be.

EXT_HOSTNAME=localhost
EXT_HTTP_PORT=9980
EXT_HTTPS_PORT=9943

# Uncomment to enable SSL and specify the certificate hostname
#EXT_SSL_HOSTNAME=secure.example.com

PORTOPT="-p $EXT_HTTP_PORT:8080 -e CONFIG_EXT_HTTP_PORT=$EXT_HTTP_PORT \
         -p $EXT_HTTPS_PORT:8443 -e CONFIG_EXT_HTTPS_PORT=$EXT_HTTPS_PORT"

usage() {
  echo "Usage: run.sh [-d] [-p port#] [-h] [extra-chaperone-options]"
  echo "       Run $IMAGE as a daemon or interactively (the default)."
  echo "       First available port will be remapped to $EXT_HOSTNAME if possible."
  exit
}

if [ "$CHAP_SERVICE_NAME" != "" ]; then
  echo run.sh should be executed on your docker host, not inside a container.
  exit
fi

cd ${0%/*} # go to directory of this file
APPS=$PWD
cd ..

options="-t -i -e TERM=$TERM --rm=true"
shellopt="/bin/bash"

while getopts ":-dp:n:" o; do
  case "$o" in
    d)
      options="-d"
      shellopt=""
      ;;
    n)
      options="$options --name $OPTARG"
      ;;
    p)
      PORTOPT="-p $OPTARG"
      ;;      
    -) # first long option terminates
      break
      ;;
    *)
      usage
      ;;
  esac
done
shift $((OPTIND-1))

# Run the image with this directory as our local apps dir.
# Create a user with a uid/gid based upon the file permissions of the chaperone.d
# directory.

MOUNT=${PWD#/}; MOUNT=/${MOUNT%%/*} # extract user mountpoint
SELINUX_FLAG=$(sestatus 2>/dev/null | fgrep -q enabled && echo :z)

docker run --name distserv $options -v $MOUNT:$MOUNT$SELINUX_FLAG $PORTOPT \
   -e CONFIG_EXT_HOSTNAME="$EXT_HOSTNAME" \
   -e CONFIG_EXT_SSL_HOSTNAME="$EXT_SSL_HOSTNAME" \
   $IMAGE \
   --create $USER:$APPS/chaperone.d --config $APPS/chaperone.d $* $shellopt
