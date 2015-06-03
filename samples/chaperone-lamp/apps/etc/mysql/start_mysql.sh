#!/bin/bash

# For a general query log, include the following:
#   --general-log-file=$APPS_DIR/log/mysqld-query.log
#   --general-log=1

exec /usr/sbin/mysqld \
   --defaults-file=$APPS_DIR/etc/mysql/my.cnf \
   --user ${USER:-mysql} \
   --datadir=$APPS_DIR/var/mysql \
   --socket=$APPS_DIR/var/run/mysqld.sock \
   --pid-file=$APPS_DIR/var/run/mysqld.pid \
   --log-error=$APPS_DIR/var/log/mysqld-error.log \
   --plugin-dir=/usr/lib/var/mysql/plugin
