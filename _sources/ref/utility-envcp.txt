.. chaperone documentation n
   command line documentation

.. _ref.envcp:

Utility: ``envcp``
==================

Overview
--------

The ``envcp`` utility is a simple method to create template and expand them using the contents of the environment.

Basic usage is as follows::

  envcp [options] FILE1 ... FILEn DESTINATION

Where:

``FILE1`` ... ``FILEn``
  A list of one or more files to be copied to the destination.  If the destination is a directory, then
  one or more files will be copied.  If the destination does not exist, then only a single file
  can be specified and the destination will be the name of the result file.

``DESTINATION``
  A directory to contain the result files, or a single file which should be the result of the copy.

The following options can be specified:

  ============================= ================================================================================
  Option
  ============================= ================================================================================
  -v / --verbose		Echo file operations to ``stdout`` as files are copied.
  -a / --archive		Attempt to preserve file permissions, ownership, access and modification times.
  --overwrite			Overwrite destination files.  If not specified, ``envcp``
  				will terminate with an error when any destination file already exists.
  --strip *suffix*		When files are copied, strip off the specified filename suffix to derive
  	  			the filename that should be used in the destination directory.
  --shell-enable		Enables backtick expansion features.
  --xprefix *char*		Specify the introductory prefix used for variable expansions.
  	    			Defaults to the dollar-sign character (`$`).
  --xgrouping *charlist*	Specify a list of opening brace types.  Defaults to the left curly brace
  	      			and the left parenthesis (``{(``).
  ============================= ================================================================================

The special option character ``-`` can be used to tell ``envcp`` that input should be taken from ``stdin``
and output should be written to ``stdout``::

  $ envcp - <input.txt >output.txt


Applications
------------

The ``envcp`` utility is usually used as a "poor-man's macro processor", similar to the 
way `GNU M4 <http://www.gnu.org/software/m4/m4.html>`_ is often employed, but much simpler.  Using a simple
bash-like syntax, you can create template files and then customize them based upon the current set
of environment variables.

For example, the `nginx <http://nginx.org>`_ web server unfortunately does not support environment
variables inside configuration files.  So, configuration lines like the following give an error::

  ##
  # Logging Settings
  ##
  access_log ${NGINX_LOG_DIR}/access.log;

However, if the ``NGINX_LOG_DIR`` environment variable is found, then the following command can be used
to reprocess a template file to create the true ``nginx`` configuration, like this::

  $ envcp /apps/templates/nginx.conf.tpl /apps/config/nginx.conf

You can even process a complete set of templates by telling ``envcp`` to strip off the template
suffix when it makes the copy::

  $ envcp --strip .tpl /apps/templates/*.tpl /apps/config


Advanced Templates
------------------

Any files copied by ``envcp`` can support the full Chaperone :ref:`environment variable expansion syntax <env.expansion>`.  However,
it is important to note that Chaperone environment variable expansions can span multiple lines, making it possible to
create reasonably complicated conditional macro expansions.

For example, this excerpt from a `bind9 <http://www.bind9.net/>`_ configuration file demonstrates how the ``forwarders`` section can be included only
if the ``CONFIG_FWD_HOST`` variable is set::

    $(CONFIG_FWD_HOST:+
        forwarders { 
	  $(CONFIG_FWD_HOST); 
        };

	forward only;
    )

You can also match the contents of variables using the *if-then-else* construct::

  $(ENABLE_ADMIN_PANEL:|T*|
     Alias /admin/ /apps/www/admin_panel_live
  |
     Alias /admin/ /apps/www/errors/admin_dead/
  )

In some situations, you may be creating shell-scripts which themselves are templates.  In this case, you may
want to customize the ``envcp`` variable prefix so that you can be sure any shell syntax is not interpreted
by ``envcp``.  So, for example, if you have a shell script template like this::

  #!/bin/bash
  BASENAME=%%(IMAGE_BASENAME)
  FULLNAME=${PWD:-/home}/${BASENAME}

you can tell ``envcp`` to use ``%%`` as the expansion prefix when you do the copy::

  $ envcp --xprefix '%%' script.sh.tpl script.sh


Backtick Syntax
---------------

Chaperone has built-in support for shell-escapes
using :ref:`backtick expansion syntax <env.backtick>`.   While this is normally enabled
in Chaperone configuration files, it is *disabled* by default in ``envcp`` to minimize
the chance of accidental (or malicious) shell injection within template scripts.

So, for example, if you have a file ``test.txt`` which contains::

  The date is ... $(`date;echo yes`)
  `ls -l`

Then, you will see the following by default using ``envcp``::

  $ envcp - <test.txt
  The date is ... $(`date;echo yes`)
  `ls -l`
  $

However, you can enable shell expansion if desired::

  $ envcp --shell-escapes <test.txt
  Tue Aug  4 01:35:07 UTC 2015 yes
  `ls -l`
  $

Note that backticks are only expanded when they occur as part of variable expansion
syntax, and are never expanded elsewhere.  Since templates are often shell scripts,
this prevents any confusion between ``envcp`` expansions and syntax which is
part of the script template itself.

See :ref:`env.expansion` for more information on how variables are expanded and
how backticks work.

