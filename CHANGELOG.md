## 0.2.24 (2015-07-27)

Bug Fixes:

 - Made `setproctitle` an optional install so that `--no-install-recommends` can be used
   on `apt-get` installs to streamline image size ([#1, @mc0e](https://github.com/garywiz/chaperone/issues/1))

Other:

 - PyPi distribution is no longer done in "wheel" format, since that limits the ability
   to include optional dependencies.  Source format is used instead.
