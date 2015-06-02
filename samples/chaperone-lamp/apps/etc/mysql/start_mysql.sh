#!/bin/bash

mkdir -p $APPS_PATH/run

exec /usr/sbin/mysqld \
   --defaults-file=$APPS_PATH/etc/mysql/my.cnf \
   --user $USER \
   --datadir=$APPS_PATH/mysql \
   --socket=$APPS_PATH/run/mysqld.sock \
   --pid-file=$APPS_PATH/run/mysqld.pid \
   --plugin-dir=/usr/lib/mysql/plugin
