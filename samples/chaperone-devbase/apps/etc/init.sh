#!/bin/bash
# A quick script to initialize the system

first_init="$APPS_PATH/etc/firstinit.done"

rm -rf $first_init

function dolog() { logger -t init.sh -p info $*; }

if [ -f $first_init ]; then
    dolog "$APPS_PATH already initialized... APPS_INIT=0"
    export APPS_INIT=0
else
    dolog "initializing $APPS_PATH directory... APPS_INIT=1"
    export APPS_INIT=1
    date >$first_init
fi

if [ -d $APPS_PATH/init.d ]; then
  for initf in $( find $APPS_PATH/init.d -type f -executable ); do
    dolog "running $initf..."
    $initf
  done
fi

if [ "$SECURE_ROOT" == "1" -a "$APPS_INIT" == "1" ]; then
  dolog locking down root account
  su -c 'passwd -l root'
fi
