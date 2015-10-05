# This file is designed to be used as a package module, but also as a main program runnable
# by Python2 or Python3 which will print the version.  Used in setup.py

VERSION = (0,3,2)
DISPLAY_VERSION = ".".join([str(v) for v in VERSION])

LICENSE = "Apache License, Version 2.0"

MAINTAINER = "Gary Wisniewski <garyw@blueseastech.com>"

LINK_PYPI = "https://pypi.python.org/pypi/chaperone"
LINK_DOC = "http://garywiz.github.io/chaperone"
LINK_SOURCE = "http://github.com/garywiz/chaperone"
LINK_QUICKSTART = "http://github.com/garywiz/chaperone-baseimage"
LINK_LICENSE = "http://www.apache.org/licenses/LICENSE-2.0"

import sys
import os

VERSION_MESSAGE = """
This is '{1}' version {0.DISPLAY_VERSION}.

Documentation and source is available at {0.LINK_SOURCE}.
Licensed under the {0.LICENSE}.
""".format(sys.modules[__name__], os.path.basename(sys.argv[0]))

if __name__ == '__main__':
    print(DISPLAY_VERSION)
