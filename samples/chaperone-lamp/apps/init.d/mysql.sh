#!/bin/bash

distdir=/var/lib/mysql
appdbdir=$APPS_PATH/mysql

function dolog() { logger -t mysql.sh -p info $*; }

if [ "$APPS_INIT" == "0" ] ; then
  exit
fi

dolog "hiding distribution mysql files in /etc so no clients see them"

su -c "cd /etc; mv my.cnf my.cnf-dist; mv mysql mysql-dist"

dolog "copying distribution $distdir to $appdbdir"

# Do this as su because we normally don't have access to the mysql directory
# Note that root has no password during initialization, but will be locked down
# on subsequent restarts (see init.sh)

su -c "cp -a $distdir $appdbdir; chown -R $USER: $appdbdir"
