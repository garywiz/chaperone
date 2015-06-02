#!/bin/bash

# For a general query log, include the following:
#   --general-log-file=$APPS_DIR/log/mysqld-query.log
#   --general-log=1

exec /usr/sbin/mysqld \
   --defaults-file=$APPS_DIR/etc/mysql/my.cnf \
   --user ${USER:-mysql} \
   --datadir=$APPS_DIR/mysql \
   --socket=$APPS_DIR/run/mysqld.sock \
   --pid-file=$APPS_DIR/run/mysqld.pid \
   --log-error=$APPS_DIR/log/mysqld-error.log \
   --plugin-dir=/usr/lib/mysql/plugin
