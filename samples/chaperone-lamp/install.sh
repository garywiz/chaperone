#!/bin/bash

MYSQL_ROOT_PW='ChangeMe'

# Assumes there is an "optional" apt-get proxy running on our HOST
# on port 3142.  You can run one by looking here: https://github.com/sameersbn/docker-apt-cacher-ng
# Does no harm if nothing is running on that port.
/setup-bin/ct_setproxy

# Normal install steps
apt-get install -y apache2

debconf-set-selections <<< "debconf debconf/frontend select Noninteractive"

debconf-set-selections <<< "mysql-server mysql-server/root_password password $MYSQL_ROOT_PW"
debconf-set-selections <<< "mysql-server mysql-server/root_password_again password $MYSQL_ROOT_PW"
debconf-set-selections <<< "phpmyadmin phpmyadmin/dbconfig-install boolean true"
debconf-set-selections <<< "phpmyadmin phpmyadmin/app-password password $MYSQL_ROOT_PW"
debconf-set-selections <<< "phpmyadmin phpmyadmin/app-password-confirm password $MYSQL_ROOT_PW"
debconf-set-selections <<< "phpmyadmin phpmyadmin/mysql/app-pass password $MYSQL_ROOT_PW"
debconf-set-selections <<< "phpmyadmin phpmyadmin/mysql/admin-pass password $MYSQL_ROOT_PW"
debconf-set-selections <<< "phpmyadmin phpmyadmin/reconfigure-webserver multiselect apache2"

apt-get install -y mysql-server
/usr/bin/mysqld_safe &

# Install phpmyadmin.  Actual setup occurs at first boot, since it depends on what user we run the container
# as.
apt-get install -y phpmyadmin
php5enmod mcrypt
