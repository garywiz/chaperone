import sys
import os
import unittest

# Assure that packages in the same directory as ours (tests) can be used without concern for where
# we are installed
sys.path[0] = os.path.join(os.path.dirname(sys.path[0]), "chaperone")

