"""
Copy text files and expand environment variables as you copy.

Usage:
    envcp [options] FILE ...

Options:
        --strip suffix      If the destination is a directory, strip "suffix"
                            off source files.
        --overwrite         Overwrite destination files rather than exiting
                            with an error.
        -v --verbose        Display progress.
        -a --archive        Preserve permissions when copying.
        --shell-enable      Enable shell escapes using backticks, as in $(`ls`)
        --xprefix char      The leading string to identify a variable.  Defaults to '$'
        --xgrouping chars   Grouping types which are recognized, defaults to '({'

Copies a file to a destination file (two arguments), or any number of files to a destination
directory.  As files are copied, environment variables will be expanded.   If the destination
is a directory, then --strip can be used to specify a file suffix to be stripped off.

Formats allowed: are $(ENV) or ${ENV}.  The bareword $ENV is not recognized.
"""

# perform any patches first
import chaperone.cutil.patches

# regular code begins
import sys
import os
import asyncio
import shlex
from docopt import docopt

from chaperone.cproc.version import VERSION_MESSAGE
from chaperone.cutil.env import Environment

def check_canwrite(flist, overok):
    for f in flist:
        if os.path.exists(f) and not overok:
            print("error: file {0} exists, won't overwrite".format(f))
            exit(1)

def main_entry():
    options = docopt(__doc__, version=VERSION_MESSAGE)

    files = options['FILE']

    start = options['--xprefix']
    braces = options['--xgrouping']

    if braces:
        if any([b not in '{([' for b in braces]):
            print("error: --xgrouping can accept one or more of '{{', '[', or '(' only.  Not this: '{0}'.".format(braces))
            exit(1)
    
    # Enable or disable, but don't cache them if enabled
    Environment.set_backtick_expansion(bool(options['--shell-enable']), False)

    Environment.set_parse_parameters(start, braces)

    env = Environment()

    # Support stdin/stdout behavior if '-' is the only file specified on the command line

    if '-' in files:
        if len(files) > 1:
            print("error: '-' for stdin/stdout cannot be combined with other filename arguments")
            exit(1)
        sys.stdout.write(env.expand(sys.stdin.read()))
        sys.stdout.flush()
        exit(0)
        
    if len(files) < 2:
        print("error: must include two or more filename arguments")
        exit(1)

    destdir = os.path.abspath(files[-1]);
    destfile = None

    if os.path.isdir(destdir):
        if not os.access(destdir, os.W_OK|os.X_OK):
            print("error: directory {0} exists but is not writable".format(destdir))
        st = options['--strip']
        if st:
            files = [(f, os.path.basename(f).rstrip(st)) for f in files[:-1]]
        else:
            files = [(f, os.path.basename(f)) for f in files[:-1]]
        check_canwrite([os.path.join(destdir, p[1]) for p in files], options['--overwrite'])
    elif len(files) != 2:
        print("error: destination is not a directory and more than 2 files specified")
        exit(1)
    else:
        destfile = files[1]
        files = [(files[0], files[0])]
        check_canwrite([destfile], options['--overwrite'])

    # files is now a list of pairs [(source, dest-basename), ...]

    for curpair in files:
        if not os.path.exists(curpair[0]):
            print("error: file does not exist, {0}".format(curpair[0]))
            exit(1)
        if not os.access(curpair[0], os.R_OK):
            print("error: file is not readable, {0}".format(curpair[0]))
            exit(1)

    for curpair in files:
        if not destfile:
            destfile = os.path.join(destdir, curpair[1])
        try:
            oldstat = os.stat(curpair[0])
            oldf = open(curpair[0], 'r')
        except Exception as ex:
            print("error: cannot open input file {0}: {1}".format(curpair[0], ex))
            exit(1)
        try:
            newf = open(destfile, 'w')
        except Exception as ex:
            print("error: cannot open output file {0}: {1}".format(destfile, ex))
            exit(1)

        newf.write(env.expand(oldf.read()))
        oldf.close()
        newf.close()

        if options['--archive']:
            # ATTEMPT to retain permissions
            try:
                os.chown(destfile, oldstat.st_uid, oldstat.st_gid);
            except PermissionError:
                # Try them separately.  User first, then group.
                try:
                    os.chown(destfile, oldstat.st_uid, -1);
                except PermissionError:
                    pass
                try:
                    os.chown(destfile, -1, oldstat.st_gid);
                except PermissionError:
                    pass
            try:
                os.chmod(destfile, oldstat.st_mode);
            except PermissionError:
                pass
            try:
                os.utime(destfile, times=(oldstat.st_atime, oldstat.st_mtime))
            except PermissionError:
                pass

        if options['--verbose']:
            print("envcp {0} {1}".format(curpair[0], destfile))

        destfile = None
