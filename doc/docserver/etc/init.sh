#!/bin/bash
# A quick script to initialize the system

# We publish two variables for use in startup scripts:
#
#   CONTAINER_INIT=1   if we are initializing the container for the first time
#   APPS_INIT=1        if we are initializing the $APPS_DIR for the first time
#
# Both may be relevant, since it's possible that the $APPS_DIR may be on a mount point
# so it can be reused when starting up containers which refer to it.

function dolog() { logger -t init.sh -p info $*; }

apps_init_file="$APPS_DIR/var/run/apps_init.done"
cont_init_file="/container_init.done"

export CONTAINER_INIT=0
export APPS_INIT=0

if [ ! -f $cont_init_file ]; then
    dolog "initializing container for the first time"
    CONTAINER_INIT=1
    su -c "date >$cont_init_file"
fi

if [ ! -f $apps_init_file ]; then
    dolog "initializing $APPS_DIR for the first time"
    APPS_INIT=1
    mkdir -p $APPS_DIR/var/run $APPS_DIR/var/log
    chmod 777 $APPS_DIR/var/run $APPS_DIR/var/log
    date >$apps_init_file
fi

if [ -d $APPS_DIR/init.d ]; then
  for initf in $( find $APPS_DIR/init.d -type f -executable \! -name '*~' ); do
    dolog "running $initf..."
    $initf
  done
fi

if [ "$SECURE_ROOT" == "1" -a $CONTAINER_INIT == 1 ]; then
  dolog locking down root account
  su -c 'passwd -l root'
fi
