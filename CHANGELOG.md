## 0.2.40 (2015-09-08)

Enhancements:

- Both `uid` and `gid` can be specified using the path-format of the [--create-user](http://garywiz.github.io/chaperone/ref/command-line.html#option-create-user) command-line switch.

Refinements:

- The `${ENV:-foo}` expansion format now behaves like `bash` where 'foo' is the result if the variable `ENV` is undefined or null (blank).  Previously, it required that the variable be undefined.  This behavior is now consistent throughout all expansion operators.
- Improved the environment expansion code to handle outlying cases, as well as be signfiicantly more readable.  Used coverage analysis to improve unit test coverage for complex expansions involving recursion.

Bug fixes:

- Newer versions of Python's `asyncio` (present in some distros) could hang when starting an **inetd**-style socket process.

## 0.2.37 (2015-08-24)

Enhancements:

- Add support for **inetd**-compatible dynamic TCP socket connections.  See the description of the [port configuration parameter](http://garywiz.github.io/chaperone/ref/config-service.html#service-port) for a complete description of this feature.
- Added [_CHAP_SERVICE_SERIAL](http://garywiz.github.io/chaperone/ref/env.html#env-chap-service-serial) and [_CHAP_SERVICE_TIME](http://garywiz.github.io/chaperone/ref/env.html#env-chap-service-time) environment variables to provide useful information to 'cron' and 'inetd' services which may execute multiple times.
- Added the ability to add a `gid` number to the path-based format of the [--create-user](http://garywiz.github.io/chaperone/ref/command-line.html#option-create-user) command-line switch.

Bug Fixes:

- Fixed `telchap stop` so that it no longer would cause service restarts to occur.
- Improved the service restart logic to handle a wider variety of service failure situations.

## 0.2.31 (2015-08-11)

Enhancements:

- Add support for --create-user name:/path so that user identity can be based upon
  the permissions set for a given path.  This helps workaround the file permissions
  issues under OSX/VirtualBox where you can't really modify the mounted file
  permissions and instead "get what you get".

## 0.2.30 (2015-08-07)

Enhancements:

- Add support for --archive/-a to envcp.

## 0.2.29 (2015-08-05)

Refinements:

- Allow backslash-escaping of VBAR construct contents in environment variable
  if-then-else construct.

## 0.2.28 (2015-08-03)

Refinements:

- Create a special-case syntax for shell escapes: ``$(`shell-command`)`` mainly to
  assure that such syntaxes are propery supported instead of being expanded as a
  side-effect.  Previously, the syntax above would treat the result of the command
  as the name of an environment variable, and since it was not found, would insert
  the results.   Since it was a useful trick, formalizing the use and eliminating
  edge cases was important.
- Disabled shell escapes by default in ``envcp`` and added the ``--shell-enable``
  switch to enable them.
- Added further documentation about shell escapes to clarify exactly how they
  work and how they should be used.
  
## 0.2.27 (2015-08-01)

Enhancements:

- Added documentation for ``envcp`` in the new utilities section of the documentation.
- Enhanced environment-variable expansions so they are smart about nesting.
- Fixed syslog receiver so that trailing newlines are stripped (programs like ``sudo``
  and ``openvpn`` terminate their log lines this way, even though it is a questionable
  practice).

## 0.2.26 (2015-07-28)

Enhancements:

- Added the ``:/`` regex substitution expansion option, which provides a more extensive and useful
  feature set than the bash-compatible options.
- Updated the documentation to reflect the new expansion option and added a footnote about
  bash compatibility.

## 0.2.25 (2015-07-27)

Enhancements:

 - Added the ``:?`` and ``:|`` environemnt variable expansion options.  The first works similarly
   to bash and raises an error if a variable is not defined.  The second adds more versatility to
   expansions by allowing the expansion to depend upon the particular value of a variable.
-  Added documntation for the above.

## 0.2.24 (2015-07-27)

Bug Fixes:

 - Made `setproctitle` an optional install so that `--no-install-recommends` can be used
   on `apt-get` installs to streamline image size ([#1, @mc0e](https://github.com/garywiz/chaperone/issues/1))

Other:

 - PyPi distribution is no longer done in "wheel" format, since that limits the ability
   to include optional dependencies.  Source format is used instead.
