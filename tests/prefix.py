import sys
import os
import unittest

if sys.version_info < (3,):
    print("You must run tests with Python 3 only.  Python 2 distributions are not supported.")
    exit(1)

# Assure that packages in the same directory as ours (tests) can be used without concern for where
# we are installed
sys.path[0] = os.path.dirname(sys.path[0])

