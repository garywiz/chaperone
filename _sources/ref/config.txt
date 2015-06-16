.. chapereone documentation
   configuration directives

.. _config:

Chaperone Configuration
=======================

Chaperone has a versatile configuration language that can be quick and easy to use, or can comprise many services
and dependencies.  For example, the following user appllication plus MySQL database server along with syslog
redirection could be defined simply in just a few lines::

  mysql.service:  { command: "/etc/init.d/mysql start",
                    type: forking }
  myapp.service:  { command: "/opt/apps/bin/my_application", 
                    restart: true, after: mysql.service }
  syslog.logging: { filter: "*.info", stdout: true }

Configurations can be as sophisticated as desired, including cron-type scheduling, multiple types of jobs, and
complex job trees.   These sections provide a complete reference to how the chaperone configuration directives.

.. toctree::

   config-format.rst
   config-global.rst
   config-service.rst
   config-logging.rst
