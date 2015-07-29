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
