"""
Copy text files and expand environment variables as you copy.

Usage:
    envcp [-v] [--overwrite] [--strip=<suffix>] FILE ...

Options:
        --strip suffix      If the destination is a directory, strip "suffix"
                            off source files.
        --overwrite         Overwrite destination files rather than exiting
                            with an error.
        -v                  Display progress.

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
            oldf = open(curpair[0], 'r')
        except Exception as ex:
            print("error: cannot open input file {0}: {1}".format(curpair[0], ex))
            exit(1)
        try:
            newf = open(destfile, 'w')
        except Exception as ex:
            print("error: cannot open output file {0}: {1}".format(destfile, ex))

        newf.write(env.expand(oldf.read()))
        newf.close()
        oldf.close()
        
        if options['-v']:
            print("envcp {0} {1}".format(curpair[0], destfile))

        destfile = None
